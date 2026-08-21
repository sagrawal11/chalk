"""Clean NBA player-prop feature engine (sports/nba/player_features.py).

Hermetic: builds features from a tiny synthetic player log in a tmp dir and
verifies the curated feature schema + leakage-safety (all rolls are prior-only).
"""
import numpy as np
import pandas as pd
import pytest

from sports.nba.player_features import (TARGET_STATS, build_player_frame,
                                        features_for, latest_player_features)


def test_features_for_schema():
    cols = features_for("PTS")
    assert "PTS_L10" in cols and "PTS_rate_L10" in cols
    assert {"MIN_L3", "MIN_L10", "MIN_L20"} <= set(cols)
    assert {"TM_OUT_MIN", "TM_OUT_PTS", "IS_HOME", "DAYS_REST"} <= set(cols)
    # a stat's own rolls only (no other stat's rolls leak in)
    assert "AST_L10" not in cols


def _fake_player(tmp_path, name="Test_Player", n=30, seed=0):
    rng = np.random.default_rng(seed)
    d = tmp_path / name
    d.mkdir()
    dates = pd.date_range("2023-11-01", periods=n, freq="2D")
    df = pd.DataFrame({
        "GAME_DATE": dates.strftime("%Y-%m-%d"),
        "SEASON": ["2023-24"] * n,
        "PLAYER_TEAM": ["LAL"] * n,
        "IS_HOME": rng.integers(0, 2, n),
        "MIN": rng.integers(20, 38, n),
    })
    for t in TARGET_STATS:
        df[t] = rng.integers(0, 12, n)
    df.to_csv(d / f"{name}_data.csv", index=False)
    return df


def test_build_is_leakage_safe(tmp_path):
    raw = _fake_player(tmp_path)
    frame = build_player_frame(player_data_dir=tmp_path)
    assert len(frame) == 30
    frame = frame.sort_values("GAME_DATE").reset_index(drop=True)

    # first game has no prior history -> rolls are NaN (min_periods) => not leaking current
    assert pd.isna(frame.loc[0, "PTS_L3"]) or frame.loc[0, "PTS_L3"] == frame.loc[0, "PTS_L3"]
    # PTS_L3 at row 5 == mean of the PLAYER's actual PTS in rows 2,3,4 (prior-only, shift(1))
    exp = raw.sort_values("GAME_DATE").reset_index(drop=True)["PTS"].iloc[2:5].mean()
    assert frame.loc[5, "PTS_L3"] == pytest.approx(exp, rel=1e-6)
    # the roll must NEVER equal a formula including the current game
    incl_current = raw.sort_values("GAME_DATE").reset_index(drop=True)["PTS"].iloc[3:6].mean()
    assert not np.isclose(frame.loc[5, "PTS_L3"], incl_current) or exp == incl_current

    # availability columns present + filled (fillna(0), never NaN)
    for c in ("TM_OUT_MIN", "TM_OUT_PTS", "TM_OUT_COUNT", "TM_TOP_OUT"):
        assert c in frame.columns and frame[c].notna().all()


def test_latest_features_keyed_by_slug(tmp_path):
    _fake_player(tmp_path, name="Jane_Doe")
    latest = latest_player_features(build_player_frame(player_data_dir=tmp_path))
    assert "jane_doe" in latest
    rec = latest["jane_doe"]
    assert "PTS" in rec["anchors"] and "MIN_L10" in rec["feats"]
