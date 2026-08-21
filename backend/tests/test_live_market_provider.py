"""LiveMarketProvider: reuse each sport's anchor source as normalized spread/total
OddsLines so the automated daily run generates picks (-> public track record).
Hermetic: stub the NBA line fetch; assert shape + the home-spread SIGN (a flip
would make every spread pick backwards) + that run_day turns them into picks."""
import pandas as pd
import pytest

import sports.nba.live_odds as nba_odds
import track_record.grade as grade
import track_record.lock as lock
from odds.providers.live_market import LiveMarketProvider
from pipeline.daily_content import run_day
from predictions.schema import GamePrediction, make_game_key


def test_unsupported_sport_returns_empty():
    # MLB/NHL/soccer need real prices for moneyline/1X2 fair probs -> not wired yet.
    assert LiveMarketProvider().fetch_game_markets("mlb", "2025-01-15") == []


def test_nba_game_markets_shape_and_sign(monkeypatch):
    monkeypatch.setattr(nba_odds, "fetch_nba_lines",
                        lambda *a, **k: {("LAL", "BOS"): {"spread": 3.5, "total": 220.0}})
    lines = LiveMarketProvider().fetch_game_markets("nba", "2025-01-15")
    by = {(ln.market_family, ln.side): ln for ln in lines}
    assert len(lines) == 4
    # source "spread" is home-favored-positive (3.5) -> STANDARD home line -3.5 (favored)
    assert by[("spread", "home")].line == -3.5 and by[("spread", "away")].line == 3.5
    assert by[("game_total", "over")].line == 220.0 and by[("game_total", "under")].line == 220.0
    gk = make_game_key("nba", "2025-01-15", "BOS", "LAL")
    assert all(ln.game_key == gk for ln in lines)   # keyed exactly like the locked picks


def test_nfl_game_markets_from_schedule(monkeypatch):
    import pandas as pd
    import sports.nfl.data as nfl_data
    monkeypatch.setattr(nfl_data, "load_schedules", lambda years: pd.DataFrame([
        {"game_date": "2024-09-08", "home": "KC", "away": "BAL", "spread_line": 3.0, "total_line": 46.5},
        {"game_date": "2024-09-15", "home": "NYJ", "away": "SF", "spread_line": -2.0, "total_line": 43.0},
    ]))
    lines = LiveMarketProvider().fetch_game_markets("nfl", "2024-09-08")
    by = {(ln.market_family, ln.side): ln for ln in lines}
    assert len(lines) == 4                              # only the 2024-09-08 game
    assert by[("spread", "home")].line == -3.0         # nflverse +3 (home favored) -> standard -3
    assert by[("game_total", "over")].line == 46.5


class _StubTP:
    def predict_game(self, home, away, game_date, season=None):
        return GamePrediction(sport="nba", game_date=game_date, home=home, away=away,
                              mu_total=224.0, sigma_total=20.0, mu_margin=6.0, sigma_margin=14.0,
                              pred_home_pts=115.0, pred_away_pts=109.0, p_home_win=0.66)


def test_run_day_generates_and_locks_picks(tmp_path, monkeypatch):
    monkeypatch.setattr(lock, "LOCKED_DIR", tmp_path / "locked")
    monkeypatch.setattr(grade, "RESULTS_LEDGER", tmp_path / "ledger.parquet")
    monkeypatch.setattr(nba_odds, "fetch_nba_lines",
                        lambda *a, **k: {("LAL", "BOS"): {"spread": 3.5, "total": 220.0}})
    summary = run_day("nba", "2025-01-15", games=[{"home": "LAL", "away": "BOS"}],
                      team_predictor=_StubTP(), odds_provider=LiveMarketProvider(),
                      do_render=False, out_root=tmp_path / "c")
    # model margin +6 clears the home -3.5 line, and mu_total 224 > 220 -> value picks
    assert summary["picks"] >= 1
    assert lock.verify_lock("nba", "2025-01-15")   # picks are in the immutable snapshot


# --- TASK 1: forward closing-moneyline capture -> ROI settlement -----------

def test_fetch_nba_lines_parses_h2h_moneyline(monkeypatch):
    """fetch_nba_lines pulls the h2h market into moneyline_home/away (additive to
    the existing spread/total keys). Stub requests so it's hermetic."""
    class _Resp:
        def raise_for_status(self):
            pass
        def json(self):
            return [{
                "home_team": "Los Angeles Lakers", "away_team": "Boston Celtics",
                "bookmakers": [{"markets": [
                    {"key": "spreads", "outcomes": [
                        {"name": "Los Angeles Lakers", "point": -3.5},
                        {"name": "Boston Celtics", "point": 3.5}]},
                    {"key": "totals", "outcomes": [
                        {"name": "Over", "point": 220.0}, {"name": "Under", "point": 220.0}]},
                    {"key": "h2h", "outcomes": [
                        {"name": "Los Angeles Lakers", "price": -160},
                        {"name": "Boston Celtics", "price": 135}]},
                ]}],
            }]

    class _Req:
        @staticmethod
        def get(*a, **k):
            return _Resp()

    monkeypatch.setattr(nba_odds, "_get_key", lambda *a, **k: "TESTKEY")
    monkeypatch.setitem(__import__("sys").modules, "requests", _Req)
    lines = nba_odds.fetch_nba_lines()
    g = lines[("LAL", "BOS")]
    assert g["spread"] == 3.5 and g["total"] == 220.0     # spread/total unchanged
    assert g["moneyline_home"] == -160 and g["moneyline_away"] == 135


def test_fetch_nba_lines_backward_compat_no_h2h(monkeypatch):
    """A book quoting only spreads+totals still yields a game (no moneyline keys)."""
    class _Resp:
        def raise_for_status(self):
            pass
        def json(self):
            return [{
                "home_team": "Los Angeles Lakers", "away_team": "Boston Celtics",
                "bookmakers": [{"markets": [
                    {"key": "spreads", "outcomes": [{"name": "Los Angeles Lakers", "point": -3.5}]},
                    {"key": "totals", "outcomes": [{"name": "Over", "point": 220.0}]},
                ]}],
            }]

    class _Req:
        @staticmethod
        def get(*a, **k):
            return _Resp()

    monkeypatch.setattr(nba_odds, "_get_key", lambda *a, **k: "TESTKEY")
    monkeypatch.setitem(__import__("sys").modules, "requests", _Req)
    g = nba_odds.fetch_nba_lines()[("LAL", "BOS")]
    assert g["spread"] == 3.5 and g["total"] == 220.0
    assert "moneyline_home" not in g and "moneyline_away" not in g


def test_provider_emits_moneyline_oddslines(monkeypatch):
    """LiveMarketProvider emits priced moneyline OddsLines (line=None) for both
    sides alongside the four spread/total lines."""
    monkeypatch.setattr(nba_odds, "fetch_nba_lines", lambda *a, **k: {
        ("LAL", "BOS"): {"spread": 3.5, "total": 220.0,
                         "moneyline_home": -160, "moneyline_away": 135}})
    lines = LiveMarketProvider().fetch_game_markets("nba", "2025-01-15")
    ml = {ln.side: ln for ln in lines if ln.market_family == "moneyline"}
    assert set(ml) == {"home", "away"}
    assert ml["home"].odds_american == -160 and ml["away"].odds_american == 135
    assert ml["home"].line is None and ml["away"].line is None
    gk = make_game_key("nba", "2025-01-15", "BOS", "LAL")
    assert ml["home"].game_key == gk and ml["home"].subject == "LAL"
    # Spread/total still present (moneyline is additive).
    assert len([ln for ln in lines if ln.market_family == "spread"]) == 2


def test_provider_no_moneyline_when_h2h_absent(monkeypatch):
    """No h2h -> no moneyline lines, but spread/total still emit."""
    monkeypatch.setattr(nba_odds, "fetch_nba_lines",
                        lambda *a, **k: {("LAL", "BOS"): {"spread": 3.5, "total": 220.0}})
    lines = LiveMarketProvider().fetch_game_markets("nba", "2025-01-15")
    assert not [ln for ln in lines if ln.market_family == "moneyline"]
    assert len(lines) == 4


def test_run_day_settles_winner_pick_at_closing_moneyline(tmp_path, monkeypatch):
    """Under MARKET_BLIND=1, run_day attaches the captured closing moneyline to the
    locked winner pick, so grading yields real (non-NaN) units for that pick."""
    monkeypatch.setenv("MARKET_BLIND", "1")
    monkeypatch.setattr(lock, "LOCKED_DIR", tmp_path / "locked")
    monkeypatch.setattr(grade, "RESULTS_LEDGER", tmp_path / "ledger.parquet")
    # Home model favorite (p_home_win 0.66). Home moneyline -160 captured.
    monkeypatch.setattr(nba_odds, "fetch_nba_lines", lambda *a, **k: {
        ("LAL", "BOS"): {"spread": 3.5, "total": 220.0,
                         "moneyline_home": -160, "moneyline_away": 135}})
    run_day("nba", "2025-01-15", games=[{"home": "LAL", "away": "BOS"}],
            team_predictor=_StubTP(), odds_provider=LiveMarketProvider(),
            do_render=False, out_root=tmp_path / "c")

    doc = lock.load_lock("nba", "2025-01-15")
    assert lock.verify_lock("nba", "2025-01-15")
    winners = [p for p in doc["picks"] if p["market_family"] == "moneyline"]
    assert len(winners) == 1                       # one market-blind winner pick
    w = winners[0]
    assert w["side"] == "home" and w["subject"] == "LAL"
    assert w["odds_american"] == -160              # real captured closing price attached
    assert w["ev"] is not None

    # Grade the home winner at that price -> non-NaN units. Home wins 118-100.
    gk = make_game_key("nba", "2025-01-15", "BOS", "LAL")
    df = grade.grade_date("nba", "2025-01-15", {gk: {"home_pts": 118.0, "away_pts": 100.0}})
    row = df[df["market_family"] == "moneyline"].iloc[0]
    assert row["result"] == "win"
    assert row["units"] == pytest.approx(100.0 / 160.0, abs=1e-4)   # -160 win payout


def test_run_day_pick_without_moneyline_stays_roi_ineligible(tmp_path, monkeypatch):
    """A winner pick with NO captured moneyline keeps units=NaN (never fabricated)."""
    monkeypatch.setenv("MARKET_BLIND", "1")
    monkeypatch.setattr(lock, "LOCKED_DIR", tmp_path / "locked")
    monkeypatch.setattr(grade, "RESULTS_LEDGER", tmp_path / "ledger.parquet")
    monkeypatch.setattr(nba_odds, "fetch_nba_lines",       # spread/total only, no h2h
                        lambda *a, **k: {("LAL", "BOS"): {"spread": 3.5, "total": 220.0}})
    run_day("nba", "2025-01-15", games=[{"home": "LAL", "away": "BOS"}],
            team_predictor=_StubTP(), odds_provider=LiveMarketProvider(),
            do_render=False, out_root=tmp_path / "c")

    doc = lock.load_lock("nba", "2025-01-15")
    w = [p for p in doc["picks"] if p["market_family"] == "moneyline"][0]
    assert w["odds_american"] is None              # nothing captured -> unpriced
    gk = make_game_key("nba", "2025-01-15", "BOS", "LAL")
    df = grade.grade_date("nba", "2025-01-15", {gk: {"home_pts": 118.0, "away_pts": 100.0}})
    row = df[df["market_family"] == "moneyline"].iloc[0]
    assert row["result"] == "win"                  # winner accuracy still counts
    assert pd.isna(row["units"])                   # but ROI-ineligible
