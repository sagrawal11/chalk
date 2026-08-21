"""Best-bet selection (backend/picks/best_bet.py). Hermetic."""
from statistics import NormalDist

import pytest

from models.distribution import PoissonNBHead
from odds.schema import OddsLine
from picks.best_bet import game_market_picks, prop_picks, select_best_bets
from predictions.schema import GamePrediction


def _game():
    mu_margin, sig = 6.0, 14.0
    p_home = 1.0 - NormalDist(mu_margin, sig).cdf(0.0)  # ~0.665
    return GamePrediction(
        sport="nba", game_date="2025-01-15", home="LAL", away="BOS",
        mu_total=224.0, sigma_total=20.0, mu_margin=mu_margin, sigma_margin=sig,
        pred_home_pts=115.0, pred_away_pts=109.0, p_home_win=p_home,
    )


def _team_lines():
    common = dict(sport="nba", game_date="2025-01-15", home="LAL", away="BOS", source="test")
    return [
        OddsLine(market_family="moneyline", subject="LAL", side="home", odds_american=-200, **common),
        OddsLine(market_family="moneyline", subject="BOS", side="away", odds_american=170, **common),
        OddsLine(market_family="spread", subject="LAL", side="home", line=-3.5, odds_american=-110, **common),
        OddsLine(market_family="spread", subject="BOS", side="away", line=3.5, odds_american=-110, **common),
        OddsLine(market_family="game_total", subject="GAME", side="over", line=224.0, odds_american=-110, **common),
        OddsLine(market_family="game_total", subject="GAME", side="under", line=224.0, odds_american=-110, **common),
    ]


def test_game_market_picks_finds_spread_value():
    picks = game_market_picks(_game(), _team_lines())
    # spread home (+6 expected margin vs a -3.5 line) is the value side.
    spread = [p for p in picks if p.market_family == "spread"]
    assert spread and spread[0].side == "home" and spread[0].subject == "LAL"
    assert spread[0].edge > 0.05 and spread[0].model_prob > 0.55
    # total sits on the mean -> ~0 edge -> not a pick.
    assert not any(p.market_family == "game_total" for p in picks)


def test_prop_picks_projection_line():
    lines = [
        OddsLine(sport="nba", game_date="2025-01-15", market_family="player_prop",
                 subject="lebron_james", side="over", line=24.5, stat="PTS", odds_american=None, source="prizepicks"),
        OddsLine(sport="nba", game_date="2025-01-15", market_family="player_prop",
                 subject="lebron_james", side="under", line=24.5, stat="PTS", odds_american=None, source="prizepicks"),
    ]
    dist = {("lebron_james", "PTS"): PoissonNBHead(mu=27.0, dispersion=8.0)}
    picks = prop_picks(lines, lambda s, st: dist.get((s, st)))
    over = [p for p in picks if p.side == "over"]
    assert over and over[0].edge >= 0.03  # a value pick (model P(over)~0.55 vs 0.5 fair)
    assert over[0].fair_prob == pytest.approx(0.5)  # projection line -> 50/50 fair


def test_select_best_bets_ranked():
    gp = _game()
    prop_lines = [
        OddsLine(sport="nba", game_date="2025-01-15", market_family="player_prop",
                 subject="lebron_james", side="over", line=20.5, stat="PTS", odds_american=None),
        OddsLine(sport="nba", game_date="2025-01-15", market_family="player_prop",
                 subject="lebron_james", side="under", line=20.5, stat="PTS", odds_american=None),
    ]
    dist = {("lebron_james", "PTS"): PoissonNBHead(mu=27.0, dispersion=8.0)}
    picks = select_best_bets([gp], _team_lines(), prop_lines, lambda s, st: dist.get((s, st)))
    assert len(picks) >= 2
    # sorted by edge descending
    assert all(picks[i].edge >= picks[i + 1].edge for i in range(len(picks) - 1))
