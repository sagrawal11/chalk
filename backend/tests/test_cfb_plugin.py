"""CFB plugin: feature-engine leakage + shape and registry wiring.
Hermetic: synthetic team-game rows, no CFBD fetch."""
import pandas as pd
import pytest

from sports.base import available_sports, get_sport
from sports.cfb.sport import CFBSport
from sports.cfb.team_features import (
    TEAM_FEATURE_COLS,
    _team_timeline,
    latest_team_features,
    matchup_features,
)


def _tg():
    rows = []
    dates = ["2024-08-31", "2024-09-07", "2024-09-14"]
    uga_pts = [31, 42, 35]
    for i, d in enumerate(dates):
        rows.append({"game_id": f"g{i}", "season": 2024, "game_date": d, "team": "Georgia",
                     "opponent": "Alabama", "is_home": 1, "pts": uga_pts[i], "opp_pts": 21})
        rows.append({"game_id": f"g{i}", "season": 2024, "game_date": d, "team": "Alabama",
                     "opponent": "Georgia", "is_home": 0, "pts": 21, "opp_pts": uga_pts[i]})
    return pd.DataFrame(rows)


def test_offense_is_prior_only():
    tl = _team_timeline(_tg())
    uga = tl[tl["team"] == "Georgia"].sort_values("game_date")
    assert uga.iloc[0]["OFF"] == pytest.approx(28.0)        # first game -> league fill (no prior)
    assert uga.iloc[2]["OFF"] == pytest.approx((31 + 42) / 2)  # excludes current 35 (no leak)
    assert "OFF_ADJ" in tl.columns


def test_matchup_features_shape():
    latest = latest_team_features(_team_timeline(_tg()))
    X = matchup_features("Georgia", "Alabama", latest)
    assert list(X.columns) == TEAM_FEATURE_COLS and len(X) == 1
    assert "HOME_OFF_ADJ" in X.columns and "HOME_DEF_ADJ" not in X.columns  # offense-only served


def test_registry_and_identity():
    assert "cfb" in available_sports()
    s = get_sport("cfb")
    assert s.key == "cfb" and isinstance(s, CFBSport)
    assert s.canonical_team("  Ohio State ") == "Ohio State"
    assert s.team_targets() == ["margin", "total"]
    assert s.player_targets() == ["passing_yards", "rushing_yards", "receiving_yards", "receptions"]
