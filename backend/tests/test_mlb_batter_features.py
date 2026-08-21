"""MLB batter hitting-prop features (sports/mlb/batter_features.py).
Hermetic: synthetic batter-games through the pure feature builder verify
leakage-safe rolling (prior games only) and the id-keyed latest-features."""
import numpy as np
import pandas as pd

from sports.mlb.batter_features import (ANCHOR_COLS, PROP_TARGETS,
                                        add_batter_features,
                                        latest_batter_features)


def _games(bid=1, hits=(1, 2, 0, 3, 1, 2, 0, 1, 2, 1, 0, 3),
           tb=(1, 4, 0, 4, 2, 2, 0, 1, 5, 1, 0, 3), hr=(0, 1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0)):
    n = len(hits)
    return pd.DataFrame({
        "batter_id": [bid] * n, "season": [2024] * n,
        "date": pd.date_range("2024-04-01", periods=n, freq="1D"),
        "hits": list(hits), "totalBases": list(tb), "homeRuns": list(hr),
        "atBats": [4.0] * n, "is_home": [i % 2 for i in range(n)],
    })


def test_rolling_is_prior_only():
    f = add_batter_features(_games()).sort_values("date").reset_index(drop=True)
    # hits_L5 at game #6 (index 6) = mean of the 5 PRIOR games' hits (never the current one)
    assert abs(f.loc[6, "hits_L5"] - np.mean([2, 0, 3, 1, 2])) < 1e-6
    # TB_L5 at the same row uses prior totalBases only
    assert abs(f.loc[6, "TB_L5"] - np.mean([4, 0, 4, 2, 2])) < 1e-6
    assert pd.isna(f.loc[0, "hits_L5"])        # first game: no history -> NaN
    assert pd.isna(f.loc[1, "hits_L5"])        # min_periods=3 -> still NaN at row 1
    assert int(f.loc[11, "_n_prior"]) == 11    # prior-game counter


def test_hr_rate_is_prior_only():
    f = add_batter_features(_games()).sort_values("date").reset_index(drop=True)
    # HR_rate_L10 at game #10 (index 10) = prior-10 HR sum / prior-10 AB sum
    prior_hr = np.sum([0, 1, 0, 0, 0, 0, 0, 0, 1, 0])   # rows 0..9
    prior_ab = 4.0 * 10
    assert abs(f.loc[10, "HR_rate_L10"] - prior_hr / prior_ab) < 1e-6


def test_latest_features_keyed_by_id_multi_target():
    latest = latest_batter_features(add_batter_features(_games(bid=42)))
    assert 42 in latest
    rec = latest[42]
    assert set(rec["anchors"]) == set(PROP_TARGETS) and ANCHOR_COLS["hits"] == "hits_L5"
    # anchor = recent avg over the last-5 ACTUAL games entering the (unseen) next game
    assert abs(rec["anchors"]["hits"] - np.mean([1, 2, 1, 0, 3])) < 1e-9         # last 5 of hits tuple
    assert abs(rec["anchors"]["totalBases"] - np.mean([1, 5, 1, 0, 3])) < 1e-9   # last 5 of tb tuple
    assert rec["n_prior"] == 12 and "feats" in rec


def test_latest_features_carry_team_and_name():
    g = _games(bid=7)
    g["team"] = "NYY"
    g["name"] = "Aaron Judge"
    rec = latest_batter_features(add_batter_features(g))[7]
    assert rec["team"] == "NYY" and rec["name"] == "Aaron Judge"   # for slate filtering / cards


def test_latest_features_default_team_name_when_absent():
    # Older cached frames predate the team/name columns -> empty strings, no error.
    rec = latest_batter_features(add_batter_features(_games(bid=8)))[8]
    assert rec["team"] == "" and rec["name"] == ""
