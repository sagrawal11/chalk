"""NHL team feature engine leakage + shape (sports/nhl/team_features.py).
Hermetic: synthetic team-game rows, no NHL API / MoneyPuck fetch."""
import pandas as pd
import pytest

from sports.nhl.team_features import (
    TEAM_FEATURE_COLS,
    XG_COLS,
    _team_timeline,
    latest_team_features,
    matchup_features,
)


def _tg():
    rows = []
    dates = ["2024-10-10", "2024-10-13", "2024-10-16"]
    tor_goals = [2, 4, 6]
    for i, d in enumerate(dates):
        gid = 2024020000 + i
        rows.append({"game_id": gid, "season": 2024, "game_date": d, "team": "TOR",
                     "opponent": "BOS", "is_home": 1, "goals": tor_goals[i], "opp_goals": 2})
        rows.append({"game_id": gid, "season": 2024, "game_date": d, "team": "BOS",
                     "opponent": "TOR", "is_home": 0, "goals": 2, "opp_goals": tor_goals[i]})
    return pd.DataFrame(rows)


def test_offense_is_prior_only():
    tl = _team_timeline(_tg())
    tor = tl[tl["team"] == "TOR"].sort_values("game_date")
    assert tor.iloc[0]["OFF"] == pytest.approx(3.1)      # first game -> league fill (no prior)
    assert tor.iloc[2]["OFF"] == pytest.approx(3.0)      # mean(2, 4), excludes current 6
    assert tor.iloc[2]["OFF"] != pytest.approx((2 + 4 + 6) / 3)  # not through-current (no leak)


def test_xg_is_prior_only():
    # TOR rows at even indices: xGF 2.0, 4.0, 9.0 ; xGA 1.0, 3.0, 2.0.
    xg = pd.DataFrame({
        "game_id": [2024020000, 2024020000, 2024020001, 2024020001, 2024020002, 2024020002],
        "team": ["TOR", "BOS", "TOR", "BOS", "TOR", "BOS"],
        "XGF_G": [2.0, 2.5, 4.0, 2.5, 9.0, 2.5],
        "XGA_G": [1.0, 2.0, 3.0, 4.0, 2.0, 9.0],
    })
    tl = _team_timeline(_tg(), xg)
    tor = tl[tl["team"] == "TOR"].sort_values("game_date")
    assert tor.iloc[0]["OFF_XG"] == pytest.approx(2.9)              # first game -> neutral fill
    assert tor.iloc[2]["OFF_XG"] == pytest.approx((2.0 + 4.0) / 2)  # excludes current 9.0 (no leak)
    assert tor.iloc[2]["OFF_XG"] != pytest.approx((2.0 + 4.0 + 9.0) / 3)  # not through-current
    assert tor.iloc[2]["DEF_XG"] == pytest.approx((1.0 + 3.0) / 2)


def test_absent_xg_feed_is_neutral():
    # No xG frame -> OFF_XG/DEF_XG fall back to the neutral fill (engine offline-safe).
    tl = _team_timeline(_tg())
    assert (tl["OFF_XG"] == 2.9).all()
    assert (tl["DEF_XG"] == 2.9).all()


def test_matchup_features_shape():
    latest = latest_team_features(_team_timeline(_tg()))
    X = matchup_features("TOR", "BOS", latest)
    assert list(X.columns) == TEAM_FEATURE_COLS and len(X) == 1
    assert all(c in X.columns for c in XG_COLS)
    assert X["NET_DIFF"].iloc[0] == pytest.approx(
        (X["HOME_OFF"].iloc[0] - X["HOME_DEF"].iloc[0]) - (X["AWAY_OFF"].iloc[0] - X["AWAY_DEF"].iloc[0])
    )
