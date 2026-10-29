"""NFL team feature engine leakage + shape (sports/nfl/team_features.py).
Hermetic: synthetic team-game rows, no nflverse fetch."""
import pandas as pd
import pytest

from sports.nfl.team_features import (
    TEAM_FEATURE_COLS,
    _team_timeline,
    latest_team_features,
    matchup_features,
)


def _tg():
    rows = []
    dates = ["2024-09-08", "2024-09-15", "2024-09-22"]
    kc_pts = [20, 27, 31]
    for i, d in enumerate(dates):
        rows.append({"game_id": f"g{i}", "season": 2024, "game_date": d, "team": "KC",
                     "opponent": "BUF", "is_home": 1, "pts": kc_pts[i], "opp_pts": 20})
        rows.append({"game_id": f"g{i}", "season": 2024, "game_date": d, "team": "BUF",
                     "opponent": "KC", "is_home": 0, "pts": 20, "opp_pts": kc_pts[i]})
    return pd.DataFrame(rows)


def test_offense_is_prior_only():
    tl = _team_timeline(_tg())
    kc = tl[tl["team"] == "KC"].sort_values("game_date")
    assert kc.iloc[0]["OFF"] == pytest.approx(22.0)     # first game -> league fill (no prior)
    assert kc.iloc[2]["OFF"] == pytest.approx(23.5)     # mean(20, 27), excludes current 31
    assert kc.iloc[2]["OFF"] != pytest.approx((20 + 27 + 31) / 3)  # not through-current (no leak)


def test_matchup_features_shape():
    latest = latest_team_features(_team_timeline(_tg()))
    X = matchup_features("KC", "BUF", latest)
    assert list(X.columns) == TEAM_FEATURE_COLS and len(X) == 1
    assert X["NET_DIFF"].iloc[0] == pytest.approx(
        (X["HOME_OFF"].iloc[0] - X["HOME_DEF"].iloc[0]) - (X["AWAY_OFF"].iloc[0] - X["AWAY_DEF"].iloc[0])
    )
