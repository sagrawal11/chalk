"""Champion schema + feature resolution (experiments/champion.py). Hermetic.

Also checks the shared harness's new winner_logloss on a tiny synthetic frame,
so the M1 eval path is covered in CI without any NFL data / network.
"""
import numpy as np
import pandas as pd
import pytest

from experiments.champion import (ChampionConfig, load_champion,
                                   resolve_feature_cols, save_champion)


def test_nfl_rung1_resolves_expected_cols():
    cols = resolve_feature_cols("nfl", ["NFL-01", "NFL-02", "NFL-03", "NFL-04", "NFL-05"])
    assert cols == ["HOME_OFF", "AWAY_OFF", "HOME_DEF", "AWAY_DEF", "NET_DIFF",
                    "HOME_WINPCT", "AWAY_WINPCT", "HOME_PRIOR_DIFF", "AWAY_PRIOR_DIFF"]
    assert not any("MARKET" in c for c in cols)  # champion is market-blind


def test_unknown_builder_raises():
    with pytest.raises(ValueError):
        resolve_feature_cols("nfl", ["NFL-99"])


def test_new_validates_and_resolves():
    c = ChampionConfig.new("nfl", "nfl-v1", 1, ["NFL-01", "NFL-03"])
    assert c.feature_cols == ["HOME_OFF", "AWAY_OFF", "NET_DIFF"]


def test_rung_must_be_positive_int():
    with pytest.raises(ValueError):
        ChampionConfig.new("nfl", "nfl-v1", 0, ["NFL-01"])


def test_feature_cols_out_of_sync_raises():
    c = ChampionConfig("nfl", "nfl-v1", 1, ["NFL-01"], feature_cols=["WRONG"])
    with pytest.raises(ValueError):
        c.validate()


def test_save_load_roundtrip(tmp_path, monkeypatch):
    import experiments.champion as champ_mod
    monkeypatch.setattr(champ_mod, "CHAMPION_DIR", tmp_path)
    save_champion(ChampionConfig.new("nfl", "nfl-v1", 1, ["NFL-01", "NFL-02"],
                                     cumulative_metrics={"su_acc": 0.61}))
    loaded = load_champion("nfl")
    assert loaded.model_version == "nfl-v1"
    assert loaded.feature_cols == ["HOME_OFF", "AWAY_OFF", "HOME_DEF", "AWAY_DEF"]
    assert loaded.cumulative_metrics["su_acc"] == 0.61


def test_walk_forward_backtest_emits_winner_logloss():
    # Tiny synthetic multi-season frame: home team is stronger, so SU acc > 0.5
    # and winner_logloss is a finite positive number. Covers the harness change.
    from backtest.team_backtest import summarize, walk_forward_backtest

    rng = np.random.RandomState(0)
    rows = []
    for season in range(2015, 2021):
        for g in range(120):
            strength = rng.normal(3.0, 6.0)  # home edge
            margin = strength + rng.normal(0, 10)
            total = 44 + rng.normal(0, 8)
            rows.append({
                "season": season, "game_date": f"{season}-09-{(g % 27) + 1:02d}",
                "home": f"H{g%8}", "away": f"A{g%8}",
                "y_margin": margin, "y_total": total,
                "F_STRENGTH": strength, "F_NOISE": rng.normal(0, 1),
            })
    frame = pd.DataFrame(rows)
    bt = walk_forward_backtest(frame, sport="nfl", feature_cols=["F_STRENGTH", "F_NOISE"],
                               params={"random_state": 42, "n_jobs": 1, "verbose": -1})
    assert not bt.empty
    assert "winner_logloss" in bt.columns
    assert (bt["season"].str.match(r"^\d{4}$")).all()   # NFL single-year labels
    agg = summarize(bt)
    assert agg["winner_logloss"] is not None and agg["winner_logloss"] > 0
    assert 0.0 <= agg["su_acc"] <= 1.0
