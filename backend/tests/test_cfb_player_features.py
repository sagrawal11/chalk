"""CFB player-prop feature engine (sports/cfb/player_features.py).

Hermetic: monkeypatches the CFBD loader with a tiny synthetic player frame and
verifies the curated feature schema + leakage-safety (all rolls are prior-only).
"""
import pandas as pd
import pytest

import sports.cfb.player_features as pf
from sports.cfb.player_features import (FEATURE_COLS, PROP_TARGETS, STATS,
                                        build_player_frame, latest_player_features)
from utils.names import player_slug


def _synthetic_frame():
    """One passer with a strictly increasing passing_yards sequence (so the
    prior-only roll is easy to verify) plus one receiver, over six games."""
    rows = []
    dates = pd.to_datetime(["2024-08-31", "2024-09-07", "2024-09-14",
                            "2024-09-21", "2024-09-28", "2024-10-05"])
    qb_yds = [100.0, 200.0, 300.0, 400.0, 500.0, 600.0]
    for i, d in enumerate(dates):
        qb = {c: 0.0 for c in STATS}
        qb.update({"game_id": f"g{i}", "season": 2024, "week": i + 1, "game_date": d,
                   "team": "Georgia", "opponent": "Alabama", "is_home": 1,
                   "player_id": "qb1", "player_name": "Carson Beck",
                   "passing_yards": qb_yds[i], "attempts": 30.0, "completions": 20.0})
        rows.append(qb)
        wr = {c: 0.0 for c in STATS}
        wr.update({"game_id": f"g{i}", "season": 2024, "week": i + 1, "game_date": d,
                   "team": "Georgia", "opponent": "Alabama", "is_home": 1,
                   "player_id": "wr1", "player_name": "Jane Receiver",
                   "receptions": 5.0, "receiving_yards": 80.0})
        rows.append(wr)
    return pd.DataFrame(rows)


def test_feature_schema_curated():
    # 20 cols: L3 + STD for each of the 10 box stats, and NO position feature.
    assert len(FEATURE_COLS) == 2 * len(STATS)
    assert "passing_yards_L3" in FEATURE_COLS and "passing_yards_STD" in FEATURE_COLS
    assert not any("position" in c for c in FEATURE_COLS)
    assert PROP_TARGETS == ["passing_yards", "rushing_yards", "receiving_yards", "receptions"]


def test_build_is_leakage_safe(monkeypatch):
    monkeypatch.setattr(pf, "load_player_games", lambda years: _synthetic_frame())
    frame = build_player_frame([2024])
    qb = frame[frame["player_id"] == "qb1"].sort_values("game_date").reset_index(drop=True)
    # L3 at game 4 (value 400) == mean(100,200,300) == 200, excludes the current game.
    assert qb.loc[3, "passing_yards_L3"] == pytest.approx(200.0)
    # a roll that INCLUDED the current game would be mean(200,300,400)==300: must not.
    assert qb.loc[3, "passing_yards_L3"] != pytest.approx(300.0)
    # first game has no prior history -> roll filled to 0.0 (never the current value).
    assert qb.loc[0, "passing_yards_L3"] == 0.0
    # STD == season-to-date expanding (prior-only) mean; at game 4 == mean(100,200,300).
    assert qb.loc[3, "passing_yards_STD"] == pytest.approx(200.0)


def test_latest_features_keyed_by_slug(monkeypatch):
    monkeypatch.setattr(pf, "load_player_games", lambda years: _synthetic_frame())
    latest = latest_player_features(build_player_frame([2024]))
    key = player_slug("Carson Beck")
    assert key in latest
    rec = latest[key]
    # next-game anchor == mean of the last 3 ACTUAL games (400,500,600) == 500.
    assert rec["anchors"]["passing_yards"] == pytest.approx(500.0)
    assert set(rec["feats"]) == set(FEATURE_COLS)
    assert rec["team"] == "Georgia"
