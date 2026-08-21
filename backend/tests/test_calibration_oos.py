"""Out-of-sample calibration eval-model (the honesty fix in
``model_training.evaluate_calibration._oos_holdout_predictions``).

Hermetic: synthetic multi-season team-game frames, no network / no artifacts.
Verifies (1) the eval-model holds out the LAST season and never trains on it
(a leakage probe), (2) predictions are returned on the level scale, and (3) the
NFL market-anchor path reconstructs the level as ``model_residual + anchor``.
"""
import numpy as np
import pandas as pd
import pytest

from model_training.evaluate_calibration import _oos_holdout_predictions

_FAST_PARAMS = dict(n_estimators=60, learning_rate=0.1, num_leaves=15, min_child_samples=5)


def _synth_frame(seasons=("2019", "2020", "2021", "2022"), per_season=200, seed=0):
    """A few seasons of games with a learnable signal (y_margin ~ NET_DIFF).

    ``anchor`` is a deliberately biased proxy of y_margin so we can prove the
    anchored path adds the anchor back (level != raw model output)."""
    rng = np.random.default_rng(seed)
    rows = []
    day = pd.Timestamp("2019-01-01")
    for s in seasons:
        for _ in range(per_season):
            net = float(rng.normal(0, 6))
            pace = float(rng.normal(100, 4))
            y_margin = 1.5 * net + float(rng.normal(0, 5))
            y_total = 2.0 * pace + float(rng.normal(0, 8))
            rows.append({
                "season": s, "game_date": day,
                "NET_DIFF": net, "PACE_SUM": pace,
                "y_margin": y_margin, "y_total": y_total,
                # biased anchor: y minus a big constant so level reconstruction is testable
                "MARKET_SPREAD": y_margin - 40.0,
            })
            day += pd.Timedelta(days=1)
    return pd.DataFrame(rows)


def test_holdout_is_last_season_and_level_scale():
    df = _synth_frame()
    seasons, dates = df["season"], df["game_date"]
    hs, mu, y_true, sigma = _oos_holdout_predictions(
        df, ["NET_DIFF", "PACE_SUM"], "y_margin", seasons, dates, _FAST_PARAMS)
    assert hs == "2022"                                  # last season is the holdout
    assert len(mu) == len(y_true) == (df["season"] == "2022").sum()
    assert y_true == pytest.approx(df.loc[df["season"] == "2022", "y_margin"].to_numpy())
    assert sigma > 0
    # A model that learned the NET_DIFF signal beats a mean-only baseline OOS.
    mae = float(np.mean(np.abs(mu - y_true)))
    base = float(np.mean(np.abs(df.loc[df["season"] != "2022", "y_margin"].mean() - y_true)))
    assert mae < base


def test_holdout_season_never_trained_on():
    """Leakage probe: make the holdout target a constant unrelated to features.
    An eval-model that (wrongly) trained on the holdout could match that
    constant; one trained on prior seasons only cannot — its predictions must
    stay near the prior-season signal, far from the injected constant."""
    df = _synth_frame()
    hold = df["season"] == "2022"
    df.loc[hold, "y_margin"] = 500.0  # absurd level only present in the holdout

    hs, mu, y_true, _ = _oos_holdout_predictions(
        df, ["NET_DIFF", "PACE_SUM"], "y_margin", df["season"], df["game_date"], _FAST_PARAMS)
    assert hs == "2022"
    assert y_true == pytest.approx(np.full(hold.sum(), 500.0))
    # If the holdout had leaked into training, mu would be pulled toward 500.
    assert mu.mean() < 100.0                              # nowhere near the injected 500
    assert abs(mu.mean()) < 60.0                          # stays in the prior-season margin range


def test_anchor_path_reconstructs_level():
    """NFL path: the model learns ``y - anchor``; the returned mu must be the
    LEVEL (mu = model_residual + anchor), so it tracks y_margin, not the residual."""
    df = _synth_frame()
    hs, mu, y_true, _ = _oos_holdout_predictions(
        df, ["NET_DIFF", "PACE_SUM"], "y_margin", df["season"], df["game_date"],
        _FAST_PARAMS, anchor_col="MARKET_SPREAD")
    # anchor = y - 40, and residual (=+40) is nearly constant => level ~ y_margin.
    assert float(np.mean(np.abs(mu - y_true))) < 8.0     # good level fit
    # Sanity: the reconstructed level is ~40 above the anchor it was built from.
    anchor = df.loc[df["season"] == hs, "MARKET_SPREAD"].to_numpy()
    assert float(np.mean(mu - anchor)) == pytest.approx(40.0, abs=6.0)


def test_requires_two_seasons():
    df = _synth_frame(seasons=("2021",), per_season=120)
    with pytest.raises(ValueError):
        _oos_holdout_predictions(df, ["NET_DIFF"], "y_margin",
                                 df["season"], df["game_date"], _FAST_PARAMS)
