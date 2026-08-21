"""Free odds ingestion: schema, providers, and store (backend/odds/). Hermetic —
tmp CSVs, a synthetic PrizePicks payload, and monkeypatched store paths.
"""
import pandas as pd
import pytest

from odds.provider import MultiProvider
from odds.providers.csv_backfill import CSVBackfillProvider
from odds.providers.manual import ManualProvider
from odds.providers.prizepicks import parse as pp_parse
from odds.schema import OddsLine


def test_oddsline_validate_id_and_game_key():
    ln = OddsLine(sport="nba", game_date="2025-01-15", market_family="spread",
                  subject="LAL", side="home", line=-4.5, odds_american=-110,
                  home="LAL", away="BOS")
    ln.validate()
    assert ln.game_key == "nba:2025-01-15:BOS@LAL"
    assert "spread" in ln.odds_id and "LAL" in ln.odds_id
    with pytest.raises(ValueError):
        OddsLine(sport="nba", game_date="d", market_family="spread", subject="X", side="over", line=1).validate()
    with pytest.raises(ValueError):
        OddsLine(sport="nba", game_date="d", market_family="player_prop", subject="x", side="over", line=1).validate()  # no stat


def _csv(tmp_path):
    p = tmp_path / "hist.csv"
    pd.DataFrame([{
        "game_date": "2025-01-15", "home": "BRK", "away": "BOS",
        "moneyline_home": -150, "moneyline_away": 130, "spread_home": -4.5, "total": 224.5,
    }]).to_csv(p, index=False)
    return p


def test_csv_backfill_expands_all_team_markets(tmp_path):
    prov = CSVBackfillProvider(_csv(tmp_path))
    lines = prov.fetch_game_markets("nba", "2025-01-15")
    fams = sorted({ln.market_family for ln in lines})
    assert fams == ["game_total", "moneyline", "spread"]
    # BRK canonicalizes to BKN
    ml = {ln.side: ln for ln in lines if ln.market_family == "moneyline"}
    assert ml["home"].subject == "BKN" and ml["home"].odds_american == -150
    assert ml["away"].subject == "BOS" and ml["away"].odds_american == 130
    sp = {ln.side: ln for ln in lines if ln.market_family == "spread"}
    assert sp["home"].line == pytest.approx(-4.5) and sp["away"].line == pytest.approx(4.5)
    tot = {ln.side: ln for ln in lines if ln.market_family == "game_total"}
    assert tot["over"].line == pytest.approx(224.5) and tot["under"].line == pytest.approx(224.5)
    assert len(prov.all_lines("nba")) == len(lines)


def test_manual_provider(tmp_path):
    p = tmp_path / "manual.csv"
    pd.DataFrame([
        {"sport": "nba", "game_date": "2025-01-15", "market_family": "player_prop",
         "subject": "lebron_james", "side": "over", "line": 24.5, "stat": "PTS", "odds_american": -115},
        {"sport": "nba", "game_date": "2025-01-15", "market_family": "player_prop",
         "subject": "lebron_james", "side": "under", "line": 24.5, "stat": "PTS", "odds_american": -105},
    ]).to_csv(p, index=False)
    props = ManualProvider(p).fetch_player_props("nba", "2025-01-15")
    assert len(props) == 2
    assert {pr.side for pr in props} == {"over", "under"}
    assert props[0].stat == "PTS"


def test_prizepicks_parse():
    payload = {
        "data": [
            {"type": "projection", "attributes": {"stat_type": "Points", "line_score": 24.5,
             "start_time": "2025-01-15T00:00:00Z"}, "relationships": {"new_player": {"data": {"id": "p1"}}}},
            {"type": "projection", "attributes": {"stat_type": "Assists", "line_score": 6.5},
             "relationships": {"new_player": {"data": {"id": "p1"}}}},
            {"type": "projection", "attributes": {"stat_type": "Fantasy Score", "line_score": 40.5},
             "relationships": {"new_player": {"data": {"id": "p1"}}}},  # unmapped -> skipped
        ],
        "included": [{"type": "new_player", "id": "p1", "attributes": {"name": "LeBron James"}}],
    }
    lines = pp_parse(payload, game_date="2025-01-15")
    assert len(lines) == 4  # 2 mapped stats x over/under
    assert {ln.stat for ln in lines} == {"PTS", "AST"}
    assert all(ln.subject == "lebron_james" and ln.odds_american is None for ln in lines)


def test_store_roundtrip_and_idempotent(tmp_path, monkeypatch):
    import odds.store as store

    monkeypatch.setattr(store, "ODDS_LIVE_DIR", tmp_path / "live")
    monkeypatch.setattr(store, "ODDS_HISTORY_PARQUET", tmp_path / "history" / "odds_history.parquet")

    lines = CSVBackfillProvider(_csv(tmp_path)).fetch_game_markets("nba", "2025-01-15")
    store.write_live_snapshot("nba", "2025-01-15", lines)
    live = store.load_live("nba", "2025-01-15")
    assert len(live) == len(lines)

    added1 = store.append_history(lines)
    added2 = store.append_history(lines)  # same capture -> idempotent
    assert added1 == len(lines)
    assert added2 == 0
    assert len(store.load_history(sport="nba", market_family="moneyline")) == 2


def test_multiprovider_combines_and_survives_failure(tmp_path):
    class _Boom:
        markets = frozenset({"player_prop"})
        def fetch_game_markets(self, s, d): return []
        def fetch_player_props(self, s, d): raise RuntimeError("scraper down")

    multi = MultiProvider([CSVBackfillProvider(_csv(tmp_path)), _Boom()])
    assert len(multi.fetch_game_markets("nba", "2025-01-15")) == 6
    # the failing prop provider is swallowed, not fatal
    assert multi.fetch_player_props("nba", "2025-01-15") == []
