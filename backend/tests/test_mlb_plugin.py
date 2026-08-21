"""MLB plugin identity + registry (backend/sports/mlb/). Hermetic — no StatsAPI
fetch, no models; proves the sport-agnostic core accepts a 3rd sport."""
import pytest

from sports.base import available_sports, get_sport
from sports.mlb.sport import MLBSport
from sports.mlb.teams import CANONICAL_TEAMS, canonical_team


def test_mlb_registered_alongside_nba_nfl():
    for k in ("mlb", "nba", "nfl"):
        assert k in available_sports()
    assert get_sport("mlb").key == "mlb"


def test_thirty_teams():
    assert len(CANONICAL_TEAMS) == 30


def test_alias_and_fullname_folding():
    assert canonical_team("ARI") == "AZ"
    assert canonical_team("OAK") == "ATH"      # Athletics relocation
    assert canonical_team("CHW") == "CWS"
    assert canonical_team("New York Yankees") == "NYY"
    assert canonical_team("St. Louis Cardinals") == "STL"
    with pytest.raises(ValueError):
        canonical_team("ZZZ")


def test_season_is_calendar_year():
    mlb = MLBSport()
    assert mlb.season_from_date("2025-08-07") == "2025"
    assert mlb.season_from_date("2025-04-01") == "2025"


def test_targets_ranges_capabilities():
    mlb = MLBSport()
    assert mlb.team_targets() == ["margin", "total", "home_runs", "away_runs"]
    assert mlb.player_targets() == ["hits", "totalBases", "homeRuns"]  # batter props
    assert mlb.score_ranges()["total"] == (4.0, 25.0)
    assert mlb.supports("schedule") and mlb.supports("predict_game")
    assert mlb.supports("predict_player")
