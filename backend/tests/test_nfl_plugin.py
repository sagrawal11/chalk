"""NFL plugin identity + registry (backend/sports/nfl/). Hermetic: no nflverse
fetch, no models; proves the sport-agnostic core accepts a second sport."""
import pytest

from sports.base import available_sports, get_sport
from sports.nfl.sport import NFLSport
from sports.nfl.teams import CANONICAL_TEAMS, canonical_team


def test_nfl_registered_alongside_nba():
    assert "nfl" in available_sports() and "nba" in available_sports()
    assert get_sport("nfl").key == "nfl"


def test_thirty_two_teams():
    assert len(CANONICAL_TEAMS) == 32


def test_relocations_and_variants():
    assert canonical_team("OAK") == "LV"
    assert canonical_team("SD") == "LAC"
    assert canonical_team("STL") == "LAR"
    assert canonical_team("LA") == "LAR"
    assert canonical_team("WSH") == "WAS"
    assert canonical_team("JAC") == "JAX"
    assert canonical_team("kc") == "KC"
    with pytest.raises(ValueError):
        canonical_team("ZZZ")


def test_season_named_by_start_year():
    nfl = NFLSport()
    assert nfl.season_from_date("2024-09-10") == "2024"   # regular season
    assert nfl.season_from_date("2025-01-15") == "2024"   # playoffs -> prior season
    assert nfl.season_from_date("2025-02-09") == "2024"   # Super Bowl
    assert nfl.season_from_date("2025-09-05") == "2025"   # next season kicks off


def test_targets_ranges_capabilities():
    nfl = NFLSport()
    assert "passing_yards" in nfl.player_targets() and "receiving_yards" in nfl.player_targets()
    assert nfl.team_targets() == ["margin", "total", "home_pts", "away_pts"]
    assert nfl.score_ranges()["total"] == (20.0, 100.0)
    assert nfl.supports("schedule") and nfl.supports("predict_game") and nfl.supports("predict_player")
