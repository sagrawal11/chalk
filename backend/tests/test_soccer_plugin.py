"""Soccer plugin (backend/sports/soccer/), completes the big-5. Hermetic: a
stubbed market provider exercises the 3-way (home/draw/away) prediction path
with no network."""
import pytest

from sports.base import available_sports, get_sport
from sports.soccer.sport import SoccerSport
from sports.soccer.teams import COMPETITIONS, canonical_team


def test_soccer_completes_big_five():
    for k in ("soccer", "nhl", "mlb", "nba", "nfl"):
        assert k in available_sports()
    assert get_sport("soccer").key == "soccer"


def test_three_competitions():
    assert COMPETITIONS["epl"] == "soccer_epl"
    assert COMPETITIONS["ucl"] == "soccer_uefa_champs_league"
    assert COMPETITIONS["mls"] == "soccer_usa_mls"


def test_name_normalization_and_aliases():
    assert canonical_team("Man City") == "Manchester City"
    assert canonical_team("  Arsenal  ") == "Arsenal"
    assert canonical_team("Spurs") == "Tottenham Hotspur"
    with pytest.raises(ValueError):
        canonical_team("")


def test_targets_and_capabilities():
    s = SoccerSport()
    assert s.team_targets() == ["home_win", "draw", "away_win", "total"]
    assert s.player_targets() == []
    assert s.supports("schedule") and s.supports("predict_game")


def test_three_way_prediction_with_stub():
    from models.soccer_predictor import SoccerPredictor
    p = SoccerPredictor()
    # Stub the Poisson team model to a known 3-way (no network, no betting line).
    p._poisson_line = lambda h, a: {"p_home": 0.60, "p_draw": 0.25, "p_away": 0.15, "total": 2.5}
    gp = p.predict_game("Arsenal", "Chelsea", "2025-08-20")
    assert gp.sport == "soccer"
    assert gp.p_home_win == 0.60 and gp.p_draw == 0.25 and gp.p_away_win == 0.15
    assert abs((gp.p_home_win + gp.p_draw + gp.p_away_win) - 1.0) < 1e-6
    assert gp.pred_home_pts >= 0 and gp.pred_away_pts >= 0     # sane, non-negative scoreline
    assert gp.pred_home_pts > gp.pred_away_pts                 # favorite scores more

    p._poisson_line = lambda h, a: None                        # no data -> base rates
    gp2 = p.predict_game("Team X", "Team Y", "2025-08-20")
    assert gp2.p_draw is not None and gp2.p_home_win > gp2.p_away_win  # home-edge base rates
