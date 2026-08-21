"""Track record: lock immutability + tamper detection, grading, aggregation.
Hermetic (tmp lock dir + ledger)."""
import json

import pandas as pd
import pytest

import track_record.grade as grade
import track_record.lock as lock
from track_record.aggregate import headline, summarize
from picks.best_bet import Pick
from predictions.schema import GamePrediction

GK = "nba:2025-01-15:BOS@LAL"


def _gp(date="2025-01-15"):
    return GamePrediction(sport="nba", game_date=date, home="LAL", away="BOS",
                          mu_total=224.0, sigma_total=20.0, mu_margin=6.0, sigma_margin=14.0,
                          pred_home_pts=115.0, pred_away_pts=109.0, p_home_win=0.66)


def _picks(date="2025-01-15", spread_line=-3.5, game_key=GK):
    common = dict(sport="nba", game_date=date, game_key=game_key,
                  model_prob=0.55, fair_prob=0.5, edge=0.05, confidence="medium")
    return [
        Pick(market_family="spread", subject="LAL", side="home", line=spread_line, odds_american=-110, **common),
        Pick(market_family="moneyline", subject="LAL", side="home", line=None, odds_american=-200, **common),
        Pick(market_family="game_total", subject="GAME", side="over", line=224.0, odds_american=-110, **common),
    ]


def test_lock_immutable_and_verifiable(tmp_path, monkeypatch):
    monkeypatch.setattr(lock, "LOCKED_DIR", tmp_path / "locked")
    p = lock.lock_predictions("nba", "2025-01-15", [_gp()], _picks())
    assert p.exists()
    assert lock.verify_lock("nba", "2025-01-15")
    with pytest.raises(FileExistsError):
        lock.lock_predictions("nba", "2025-01-15", [_gp()], _picks())  # immutable
    doc = lock.load_lock("nba", "2025-01-15")
    assert len(doc["picks"]) == 3 and len(doc["game_predictions"]) == 1


def test_verify_detects_tampering(tmp_path, monkeypatch):
    monkeypatch.setattr(lock, "LOCKED_DIR", tmp_path / "locked")
    lock.lock_predictions("nba", "2025-01-15", [_gp()], _picks())
    path = lock.lock_path("nba", "2025-01-15")
    d = json.loads(path.read_text())
    d["picks"][0]["edge"] = 0.99  # tamper after the fact
    path.write_text(json.dumps(d))
    assert lock.verify_lock("nba", "2025-01-15") is False


def test_grade_team_markets(tmp_path, monkeypatch):
    monkeypatch.setattr(lock, "LOCKED_DIR", tmp_path / "locked")
    monkeypatch.setattr(grade, "RESULTS_LEDGER", tmp_path / "ledger.parquet")
    lock.lock_predictions("nba", "2025-01-15", [_gp()], _picks())
    res = grade.grade_date("nba", "2025-01-15", {GK: {"home_pts": 120, "away_pts": 110}})
    by = {r["market_family"]: r for r in res.to_dict("records")}
    assert by["spread"]["result"] == "win"        # margin 10, line -3.5 -> 6.5 > 0
    assert by["moneyline"]["result"] == "win"      # home won
    assert by["game_total"]["result"] == "win"     # 230 > 224
    assert by["spread"]["units"] == pytest.approx(0.909, abs=1e-2)
    assert by["moneyline"]["units"] == pytest.approx(0.5)
    assert grade.append_ledger(res) == 3


def test_grade_spread_push(tmp_path, monkeypatch):
    monkeypatch.setattr(lock, "LOCKED_DIR", tmp_path / "locked")
    lock.lock_predictions("nba", "2025-01-16", [_gp("2025-01-16")], _picks("2025-01-16", spread_line=-10.0))
    res = grade.grade_date("nba", "2025-01-16", {GK: {"home_pts": 120, "away_pts": 110}})
    spread = [r for r in res.to_dict("records") if r["market_family"] == "spread"][0]
    assert spread["result"] == "push" and spread["units"] == 0.0


def test_grade_prop(tmp_path, monkeypatch):
    monkeypatch.setattr(lock, "LOCKED_DIR", tmp_path / "locked")
    prop = Pick(sport="nba", game_date="2025-01-17", market_family="player_prop",
                subject="lebron_james", side="over", line=24.5, stat="PTS", odds_american=None,
                model_prob=0.6, fair_prob=0.5, edge=0.1, confidence="high")
    lock.lock_predictions("nba", "2025-01-17", [], [prop])
    res = grade.grade_date("nba", "2025-01-17", {}, prop_actuals={("lebron_james", "PTS"): 27.0})
    assert res.iloc[0]["result"] == "win"


def test_aggregate_headline_and_summary():
    df = pd.DataFrame([
        {"sport": "nba", "game_date": "2025-01-15", "market_family": "spread", "subject": "LAL",
         "side": "home", "line": -3.5, "stat": None, "odds_american": -110, "edge": 0.05, "result": "win", "units": 0.909},
        {"sport": "nba", "game_date": "2025-01-16", "market_family": "moneyline", "subject": "LAL",
         "side": "home", "line": None, "stat": None, "odds_american": -200, "edge": 0.05, "result": "win", "units": 0.5},
        {"sport": "nba", "game_date": "2025-01-17", "market_family": "game_total", "subject": "GAME",
         "side": "over", "line": 224.0, "stat": None, "odds_american": -110, "edge": 0.05, "result": "loss", "units": -1.0},
    ])
    h = headline(df)
    assert h["record"] == "2-1"
    assert h["win_pct"] == pytest.approx(0.6667, abs=1e-3)
    assert h["streak"] == -1              # most recent (01-17) is a loss
    assert h["units"] == pytest.approx(0.409, abs=1e-2)
    assert not summarize(df, ["market_family"]).empty
