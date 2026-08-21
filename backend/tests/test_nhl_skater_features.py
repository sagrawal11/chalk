"""NHL skater points/shots prop features (sports/nhl/skater_features.py).
Hermetic: synthetic game logs through the pure feature builder verify
leakage-safe rolling (prior games only) and the per-target inference anchors."""
import numpy as np
import pandas as pd

from sports.nhl.skater_features import (ANCHOR_COLS, PROP_TARGETS,
                                        add_skater_features, latest_skater_features)


def _games(pid=1, pts=(1, 0, 2, 1, 0, 3, 1, 2), shots=(3, 2, 5, 4, 1, 6, 3, 4)):
    n = len(pts)
    return pd.DataFrame({
        "player_id": [pid] * n, "season": [2023] * n,
        "date": pd.date_range("2023-10-10", periods=n, freq="2D"),
        "points": list(pts), "shots": list(shots), "toi": [18.0] * n,
        "is_home": [i % 2 for i in range(n)], "opp": [""] * n,
    })


def test_rolling_is_prior_only():
    f = add_skater_features(_games()).sort_values("date").reset_index(drop=True)
    # points_L5 at game #6 = mean points of the 5 PRIOR games (never the current)
    assert abs(f.loc[6, "points_L5"] - np.mean([0, 2, 1, 0, 3])) < 1e-6
    assert abs(f.loc[6, "shots_L5"] - np.mean([2, 5, 4, 1, 6])) < 1e-6
    assert pd.isna(f.loc[0, "points_L5"])     # first game: no history -> NaN
    assert pd.isna(f.loc[1, "shots_L5"])      # 2nd game: <min_periods(3) prior -> NaN
    assert int(f.loc[7, "_n_prior"]) == 7     # prior-game counter


def test_latest_features_keyed_by_id_with_anchors():
    latest = latest_skater_features(add_skater_features(_games(pid=42)))
    assert 42 in latest
    rec = latest[42]
    assert set(PROP_TARGETS) == {"points", "shots"}
    assert "anchors" in rec and "feats" in rec
    assert ANCHOR_COLS == {"points": "points_L5", "shots": "shots_L5"}
    # anchors = the trailing-5 average entering the (unseen) next game
    assert abs(rec["anchors"]["points"] - np.mean([1, 0, 3, 1, 2])) < 1e-6  # last 5 of pts
    assert abs(rec["anchors"]["shots"] - np.mean([4, 1, 6, 3, 4])) < 1e-6   # last 5 of shots


def test_latest_features_carry_team_and_name():
    g = _games(pid=7)
    g["team"] = "TOR"
    g["name"] = "Auston Matthews"
    rec = latest_skater_features(add_skater_features(g))[7]
    assert rec["team"] == "TOR" and rec["name"] == "Auston Matthews"   # for slate filtering / cards


def test_latest_features_default_team_name_when_absent():
    # Older cached frames predate the team/name columns -> empty strings, no error.
    rec = latest_skater_features(add_skater_features(_games(pid=8)))[8]
    assert rec["team"] == "" and rec["name"] == ""
