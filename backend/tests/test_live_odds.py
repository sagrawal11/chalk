"""Live NBA odds provider (sports/nba/live_odds.py) — hermetic: team-name
mapping + fail-soft behavior with no API key (never raises, returns empty)."""
from sports.nba.live_odds import _to_code, fetch_nba_lines, market_provider


def test_team_name_mapping():
    assert _to_code("Los Angeles Lakers") == "LAL"
    assert _to_code("Boston Celtics") == "BOS"
    assert _to_code("LA Clippers") == "LAC"
    assert _to_code("Philadelphia 76ers") == "PHI"
    assert _to_code(None) is None
    assert _to_code("Nonexistent FC") is None


def test_no_key_degrades_gracefully(monkeypatch):
    monkeypatch.delenv("ODDS_API_KEY", raising=False)
    assert fetch_nba_lines(api_key=None) == {}          # no network call, empty
    prov = market_provider()                            # cached lookup callable
    assert prov("LAL", "BOS", "2026-10-30") is None     # -> team-model fallback
