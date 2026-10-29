"""Team feature builder leakage + correctness (backend/sports/nba/team_features.py).

Hermetic: writes a tiny synthetic team-games parquet to tmp and asserts the
targets are correct and the pre-game ratings are strictly prior-only (a team's
later game never sees its own current or future rating).
"""
import numpy as np
import pandas as pd
import pytest

from sports.nba.team_features import TEAM_FEATURE_COLS, build_team_game_frame, matchup_features


def _synthetic_parquet(path):
    # Three LAL-vs-BOS games on ascending dates. LAL off_rtg rises 100 -> 110 -> 130
    # so the prior-only (pre-g3) cumulative LAL off is mean(100,110)=105, NOT 130.
    dates = pd.to_datetime(["2023-11-01", "2023-11-03", "2023-11-05"])
    rows = []
    lal_off = [100.0, 110.0, 130.0]
    lal_pts = [100, 100, 120]
    bos_pts = [90, 105, 100]
    home_flags = [1, 0, 1]  # LAL home, LAL away, LAL home
    for gi, d in enumerate(dates):
        gid = gi + 1
        lal_home = home_flags[gi]
        # LAL row
        rows.append(dict(
            game_id=gid, season=2023, game_date=d, is_home_team=lal_home, team="LAL",
            team_id=1, pts=lal_pts[gi], plus_minus=lal_pts[gi] - bos_pts[gi],
            off_rtg=lal_off[gi], def_rtg=105.0, net_rtg=lal_off[gi] - 105.0, pace=99.0, is_playoff=0,
        ))
        # BOS row
        rows.append(dict(
            game_id=gid, season=2023, game_date=d, is_home_team=1 - lal_home, team="BOS",
            team_id=2, pts=bos_pts[gi], plus_minus=bos_pts[gi] - lal_pts[gi],
            off_rtg=112.0, def_rtg=108.0, net_rtg=4.0, pace=99.0, is_playoff=0,
        ))
    df = pd.DataFrame(rows)
    df.to_parquet(path, index=False)
    return path


def test_targets_and_prior_only_ratings(tmp_path):
    p = _synthetic_parquet(tmp_path / "kaggle_team_games.parquet")
    frame = build_team_game_frame(p)

    assert len(frame) == 3
    for _, r in frame.iterrows():
        assert r["y_margin"] == pytest.approx(r["home_pts"] - r["away_pts"])
        assert r["y_total"] == pytest.approx(r["home_pts"] + r["away_pts"])
    # no feature left NaN (fills applied)
    assert not frame[TEAM_FEATURE_COLS].isna().any().any()

    # Game 1 is each team's first game -> pre-game ratings are the league fills.
    g1 = frame[frame["game_date"] == pd.Timestamp("2023-11-01")].iloc[0]
    assert g1["home"] == "LAL"
    assert g1["HOME_OFF"] == pytest.approx(110.0)  # fill, no prior history

    # Game 3 (LAL home): LAL pre-game OFF must be mean(100,110)=105, prior-only,
    # NOT the current 130 and NOT the through-g3 cumulative 113.33 (leakage).
    g3 = frame[frame["game_date"] == pd.Timestamp("2023-11-05")].iloc[0]
    assert g3["home"] == "LAL"
    assert g3["HOME_OFF"] == pytest.approx(105.0)
    assert g3["HOME_OFF"] != pytest.approx(130.0)


def test_matchup_features_shape_and_parity(tmp_path):
    p = _synthetic_parquet(tmp_path / "kaggle_team_games.parquet")
    # A future matchup after all games -> LAL pre-game OFF = mean(100,110,130)=113.33
    X = matchup_features("LAL", "BOS", "2023-11-10", parquet_path=p)
    assert list(X.columns) == TEAM_FEATURE_COLS
    assert len(X) == 1
    assert X["HOME_OFF"].iloc[0] == pytest.approx((100 + 110 + 130) / 3.0)
    assert X["NET_DIFF"].iloc[0] == pytest.approx(X["HOME_NET"].iloc[0] - X["AWAY_NET"].iloc[0])
