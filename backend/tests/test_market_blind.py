"""Market-blind mode (config.settings.MARKET_BLIND): predictions ignore the betting
line and picks are generated odds-free. Hermetic — no network and no trained models
required (the one artifact-dependent check skips if the model is absent)."""
import pytest

from picks.best_bet import game_winner_picks, select_best_bets
from predictions.schema import GamePrediction


def _nba(p_home=0.677):
    return GamePrediction(sport="nba", game_date="2025-01-15", home="LAL", away="BOS",
                          mu_total=224.0, sigma_total=17.0, mu_margin=5.5, sigma_margin=12.0,
                          pred_home_pts=114.8, pred_away_pts=109.2, p_home_win=p_home)


def _soccer(p_home=0.34, p_draw=0.30, p_away=0.36):
    return GamePrediction(sport="soccer", game_date="2025-01-15", home="ARS", away="CHE",
                          mu_total=2.7, sigma_total=1.4, mu_margin=0.4, sigma_margin=1.3,
                          pred_home_pts=1.5, pred_away_pts=1.1,
                          p_home_win=p_home, p_draw=p_draw, p_away_win=p_away)


def test_flag_default_is_market_blind(monkeypatch):
    from config import settings
    monkeypatch.delenv("MARKET_BLIND", raising=False)  # no env + none in .env -> default
    assert settings.market_blind() is True
    monkeypatch.setenv("MARKET_BLIND", "0"); assert settings.market_blind() is False
    monkeypatch.setenv("MARKET_BLIND", "false"); assert settings.market_blind() is False
    monkeypatch.setenv("MARKET_BLIND", "1"); assert settings.market_blind() is True
    monkeypatch.setenv("MARKET_BLIND", "yes"); assert settings.market_blind() is True


def test_game_winner_pick_favors_home_2way():
    pk = game_winner_picks(_nba(0.677))[0]
    assert pk.market_family == "moneyline" and pk.side == "home" and pk.subject == "LAL"
    assert pk.model_prob == pytest.approx(0.677) and pk.line is None and pk.odds_american is None
    assert pk.edge == pytest.approx(0.177, abs=1e-3) and pk.confidence == "high"


def test_game_winner_pick_favors_away_2way():
    pk = game_winner_picks(_nba(0.40))[0]
    assert pk.side == "away" and pk.subject == "BOS" and pk.model_prob == pytest.approx(0.60)


def test_game_winner_pick_3way_never_draw():
    # away (0.36) edges home (0.34); the draw (0.30) is never a pick side.
    pk = game_winner_picks(_soccer(0.34, 0.30, 0.36))[0]
    assert pk.side == "away" and pk.subject == "CHE" and pk.model_prob == pytest.approx(0.36)


def test_select_best_bets_market_blind_routes_to_winner(monkeypatch):
    monkeypatch.setenv("MARKET_BLIND", "1")
    picks = select_best_bets([_nba(0.677), _soccer()], team_lines=[], prop_lines=[],
                             dist_lookup=lambda s, st: None)
    assert len(picks) == 2 and {p.market_family for p in picks} == {"moneyline"}
    assert all(p.odds_american is None for p in picks)
    assert picks[0].edge >= picks[1].edge  # ranked most-confident first


def test_soccer_predictor_blind_ignores_market_line(monkeypatch):
    from models.soccer_predictor import SoccerPredictor
    p = SoccerPredictor()
    p.market_provider = lambda h, a, d=None: {"p_home": 0.99, "p_draw": 0.005, "p_away": 0.005, "total": 3.0}
    monkeypatch.setattr(p, "_poisson_line",
                        lambda h, a: {"p_home": 0.50, "p_draw": 0.27, "p_away": 0.23, "total": 2.6})
    monkeypatch.setenv("MARKET_BLIND", "1")
    gp = p.predict_game("Arsenal", "Chelsea", "2025-08-20")
    assert gp.p_home_win == pytest.approx(0.50)   # used the model, ignored the 0.99 line
    monkeypatch.setenv("MARKET_BLIND", "0")
    gp2 = p.predict_game("Arsenal", "Chelsea", "2025-08-20")
    assert gp2.p_home_win == pytest.approx(0.99)  # anchored on the line


def test_nfl_blind_model_is_market_free():
    """If the blind NFL artifact is trained, its target/features must be line-free."""
    joblib = pytest.importorskip("joblib")
    from models.nfl_team_predictor import NFL_TEAM_BLIND_DIR
    f = NFL_TEAM_BLIND_DIR / "team_margin.joblib"
    if not f.exists():
        pytest.skip("nfl_team_blind not trained in this environment")
    art = joblib.load(f)
    assert art.get("anchor_col") is None
    assert not any("MARKET" in c for c in art["feature_cols"])
