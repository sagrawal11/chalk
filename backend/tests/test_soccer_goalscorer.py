"""Market-anchored soccer anytime-goalscorer props (sports/soccer/goalscorer_odds.py)
+ the daily_content soccer slate dispatch + the soccer prop-card render. Hermetic:
synthetic Odds-API payloads / monkeypatched fetch; no network."""
from PIL import Image

from content.render import render_props_card
from sports.soccer.goalscorer_odds import parse_goalscorer_event
from utils.odds_math import american_to_implied_prob


def _event(*outcomes):
    return {"bookmakers": [{"key": "bk", "markets": [
        {"key": "player_goal_scorer_anytime", "outcomes": list(outcomes)}]}]}


def test_parse_ranks_by_implied_prob_and_caps_top_k():
    ev = _event(
        {"name": "Yes", "description": "Haaland", "price": -140},   # strong favorite
        {"name": "Yes", "description": "Foden", "price": 200},
        {"name": "Yes", "description": "Gvardiol", "price": 650},
    )
    out = parse_goalscorer_event(ev, top_k=2)
    assert [p for p, _ in out] == ["Haaland", "Foden"]              # ranked; top-2 only
    assert abs(out[0][1] - american_to_implied_prob(-140)) < 1e-9   # raw implied (Yes-only)
    assert out[0][1] > out[1][1] > 0


def test_parse_devigs_when_no_side_present():
    ev = _event(
        {"name": "Yes", "description": "Messi", "price": -120},
        {"name": "No", "description": "Messi", "price": 100},
    )
    (player, prob), = parse_goalscorer_event(ev, top_k=5)
    assert player == "Messi"
    assert prob < american_to_implied_prob(-120)   # de-vig strips margin -> below raw implied
    assert 0.0 < prob < 1.0


def test_parse_empty_when_market_absent():
    assert parse_goalscorer_event({"bookmakers": [{"markets": [{"key": "h2h", "outcomes": []}]}]}) == []


def test_soccer_slate_props_builds_cards(monkeypatch):
    import sports.soccer.goalscorer_odds as gs
    monkeypatch.setattr(gs, "fetch_anytime_goalscorer",
                        lambda **k: [{"home": "Arsenal", "away": "Chelsea", "date": "2026-08-21",
                                      "competition": "epl", "scorers": [("Saka", 0.42), ("Jackson", 0.35)]}])
    from pipeline.daily_content import _sport_slate_props
    cards = _sport_slate_props("soccer", [], "2026")
    assert [c["player_name"] for c in cards] == ["Saka", "Jackson"]
    assert cards[0]["projections"] == {"anytime_scorer_pct": 42} and cards[0]["sport"] == "soccer"
    assert cards[0]["matchup"] == "Arsenal vs Chelsea"


def test_soccer_prop_card_renders(tmp_path):
    p = render_props_card("Saka", {"anytime_scorer_pct": 42}, tmp_path,
                          matchup="Arsenal vs Chelsea", sport="soccer")
    assert p.exists() and Image.open(p).size == (1080, 1350)
