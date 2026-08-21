"""NHL plugin identity + registry (backend/sports/nhl/). Hermetic — no NHL API
fetch, no models; proves the sport-agnostic core accepts a 4th sport."""
import pytest

from sports.base import available_sports, get_sport
from sports.nhl.sport import NHLSport
from sports.nhl.teams import CANONICAL_TEAMS, canonical_team


def test_nhl_registered_alongside_others():
    for k in ("nhl", "mlb", "nba", "nfl"):
        assert k in available_sports()
    assert get_sport("nhl").key == "nhl"


def test_thirty_two_teams():
    assert len(CANONICAL_TEAMS) == 32


def test_relocation_and_fullname_folding():
    assert canonical_team("ARI") == "UTA"      # Coyotes -> Utah
    assert canonical_team("PHX") == "UTA"
    assert canonical_team("ATL") == "WPG"      # Thrashers -> Winnipeg
    assert canonical_team("Toronto Maple Leafs") == "TOR"
    assert canonical_team("Utah Hockey Club") == "UTA"
    assert canonical_team("Montreal Canadiens") == "MTL"
    with pytest.raises(ValueError):
        canonical_team("ZZZ")


def test_season_named_by_start_year():
    nhl = NHLSport()
    assert nhl.season_from_date("2024-11-15") == "2024"   # Nov -> that season
    assert nhl.season_from_date("2025-03-01") == "2024"   # spring -> prior start year


def test_targets_ranges_capabilities():
    nhl = NHLSport()
    assert nhl.team_targets() == ["margin", "total", "home_goals", "away_goals"]
    assert nhl.player_targets() == ["points", "shots"]  # skater props
    assert nhl.score_ranges()["total"] == (2.0, 16.0)
    assert nhl.supports("schedule") and nhl.supports("predict_game")
    assert nhl.supports("predict_player")
