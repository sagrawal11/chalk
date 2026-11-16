"""MLB Statcast prior-season xwOBA prior (sports/mlb/statcast_data.py + the feature
wiring). Hermetic: the leaderboard fetch is monkeypatched, so no network is touched.
The one property that matters is leakage safety - a season-Y game may only see the
season-(Y-1) xwOBA - plus the neutral fallback that keeps the feature offline-safe."""
import pandas as pd

import sports.mlb.statcast_data as sc
from sports.mlb.statcast_data import NEUTRAL_XWOBA
from sports.mlb.batter_features import add_batter_features, latest_batter_features
from sports.mlb.pitcher_features import add_pitcher_features, latest_pitcher_features


def _fake_leaderboard(monkeypatch):
    # pid 1: xwOBA 0.300 in 2023, 0.320 in 2024. pid 2: only 2023 (0.400).
    lb = pd.DataFrame({"player_id": [1, 1, 2], "season": [2023, 2024, 2023],
                       "xwOBA": [0.300, 0.320, 0.400], "pa": [600, 600, 600]})
    monkeypatch.setattr(sc, "load_xwoba",
                        lambda kind, years: lb[lb["season"].isin(list(years))].copy())


def test_prior_join_is_strictly_prior_season(monkeypatch):
    _fake_leaderboard(monkeypatch)
    df = pd.DataFrame({"pitcher_id": [1, 1], "season": [2024, 2025],
                       "date": pd.to_datetime(["2024-05-01", "2025-05-01"])})
    out = sc.add_prior_xwoba(df, "pitcher", "pitcher_id")
    # 2024 game sees 2023 xwOBA (0.300); 2025 game sees 2024 xwOBA (0.320) - never same-season.
    assert abs(out.loc[out["season"] == 2024, "xwOBA_prior"].iloc[0] - 0.300) < 1e-9
    assert abs(out.loc[out["season"] == 2025, "xwOBA_prior"].iloc[0] - 0.320) < 1e-9


def test_missing_prior_row_gets_neutral_fill(monkeypatch):
    _fake_leaderboard(monkeypatch)
    # pid 2 has no 2024 row -> a 2025 game (needs 2024) falls to the neutral fill;
    # pid 99 is unknown entirely -> neutral. No NaN ever leaves the join.
    df = pd.DataFrame({"batter_id": [2, 99], "season": [2025, 2024],
                       "date": pd.to_datetime(["2025-05-01", "2024-05-01"])})
    out = sc.add_prior_xwoba(df, "batter", "batter_id")
    assert (out["xwOBA_prior"] == NEUTRAL_XWOBA).all()
    assert out["xwOBA_prior"].notna().all()


def test_pitcher_latest_features_neutral_without_column():
    # The pure synthetic path has no xwOBA_prior column; latest must still emit a
    # complete feats dict with the neutral prior (offline-safe inference).
    starts = pd.DataFrame({
        "pitcher_id": [7] * 6, "season": [2024] * 6,
        "date": pd.date_range("2024-04-01", periods=6, freq="5D"),
        "K": [6, 7, 5, 8, 6, 7], "IP": [6.0] * 6, "BF": [24.0] * 6,
        "opp": [""] * 6, "is_home": [0, 1, 0, 1, 0, 1]})
    rec = latest_pitcher_features(add_pitcher_features(starts))[7]
    assert abs(rec["feats"]["xwOBA_prior"] - NEUTRAL_XWOBA) < 1e-9


def test_batter_latest_features_carries_column_value():
    games = pd.DataFrame({
        "batter_id": [8] * 12, "season": [2024] * 12,
        "date": pd.date_range("2024-04-01", periods=12, freq="1D"),
        "hits": [1, 2, 0, 3, 1, 2, 0, 1, 2, 1, 0, 3],
        "totalBases": [1, 4, 0, 4, 2, 2, 0, 1, 5, 1, 0, 3],
        "homeRuns": [0, 1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0], "atBats": [4.0] * 12,
        "is_home": [i % 2 for i in range(12)]})
    f = add_batter_features(games)
    f["xwOBA_prior"] = 0.355   # as build_batter_frame would attach it
    rec = latest_batter_features(f)[8]
    assert abs(rec["feats"]["xwOBA_prior"] - 0.355) < 1e-9
