"""Track record: lock immutability + tamper detection, winner+score grading,
aggregation. Hermetic (tmp lock dir + ledger)."""
import json

import pandas as pd
import pytest

import track_record.grade as grade
import track_record.lock as lock
from track_record.aggregate import headline, summarize
from predictions.schema import GamePrediction

GK = "nba:2025-01-15:BOS@LAL"


def _gp(date="2025-01-15", home="LAL", away="BOS", mu_margin=6.0,
        pred_home=115.0, pred_away=109.0):
    return GamePrediction(sport="nba", game_date=date, home=home, away=away,
                          mu_total=224.0, sigma_total=20.0, mu_margin=mu_margin,
                          sigma_margin=14.0, pred_home_pts=pred_home,
                          pred_away_pts=pred_away, p_home_win=0.66)


def test_lock_immutable_and_verifiable(tmp_path, monkeypatch):
    monkeypatch.setattr(lock, "LOCKED_DIR", tmp_path / "locked")
    p = lock.lock_predictions("nba", "2025-01-15", [_gp()])
    assert p.exists()
    assert lock.verify_lock("nba", "2025-01-15")
    with pytest.raises(FileExistsError):
        lock.lock_predictions("nba", "2025-01-15", [_gp()])  # immutable
    doc = lock.load_lock("nba", "2025-01-15")
    assert len(doc["game_predictions"]) == 1


def test_verify_detects_tampering(tmp_path, monkeypatch):
    monkeypatch.setattr(lock, "LOCKED_DIR", tmp_path / "locked")
    lock.lock_predictions("nba", "2025-01-15", [_gp()])
    path = lock.lock_path("nba", "2025-01-15")
    d = json.loads(path.read_text())
    d["game_predictions"][0]["mu_margin"] = 99.0  # tamper after the fact
    path.write_text(json.dumps(d))
    assert lock.verify_lock("nba", "2025-01-15") is False


def test_grade_winner_and_score(tmp_path, monkeypatch):
    monkeypatch.setattr(lock, "LOCKED_DIR", tmp_path / "locked")
    monkeypatch.setattr(grade, "RESULTS_LEDGER", tmp_path / "ledger.parquet")
    lock.lock_predictions("nba", "2025-01-15", [_gp()])
    res = grade.grade_date("nba", "2025-01-15", {GK: {"home_pts": 120, "away_pts": 110}})
    r = res.iloc[0]
    assert r["result"] == "win" and r["side"] == "home" and r["subject"] == "LAL"
    assert r["home_pts_err"] == pytest.approx(5.0)   # pred 115 vs 120
    assert r["away_pts_err"] == pytest.approx(1.0)   # pred 109 vs 110
    assert grade.append_ledger(res) == 1


def test_grade_tie_is_loss(tmp_path, monkeypatch):
    monkeypatch.setattr(lock, "LOCKED_DIR", tmp_path / "locked")
    lock.lock_predictions("nba", "2025-01-16", [_gp("2025-01-16")])
    res = grade.grade_date("nba", "2025-01-16",
                           {"nba:2025-01-16:BOS@LAL": {"home_pts": 110, "away_pts": 110}})
    assert res.iloc[0]["result"] == "loss"           # a tie beats neither side


def test_aggregate_headline_and_summary():
    df = pd.DataFrame([
        {"sport": "nba", "game_date": "2025-01-15", "home": "LAL", "away": "BOS",
         "subject": "LAL", "side": "home", "result": "win",
         "home_pts_err": 2.0, "away_pts_err": 3.0},
        {"sport": "nba", "game_date": "2025-01-16", "home": "MIA", "away": "NYK",
         "subject": "NYK", "side": "away", "result": "win",
         "home_pts_err": 1.0, "away_pts_err": 4.0},
        {"sport": "nba", "game_date": "2025-01-17", "home": "GSW", "away": "DEN",
         "subject": "GSW", "side": "home", "result": "loss",
         "home_pts_err": 6.0, "away_pts_err": 5.0},
    ])
    h = headline(df)
    assert h["record"] == "2-1"
    assert h["win_pct"] == pytest.approx(0.6667, abs=1e-3)
    assert h["streak"] == -1              # most recent (01-17) is a loss
    assert h["score_mae"] is not None
    assert not summarize(df, ["sport"]).empty
