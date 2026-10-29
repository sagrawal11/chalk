"""Seed writer: market-blind walk-forward predictions -> graded, ROI-ineligible ledger
rows. Hermetic (synthetic preds + tmp ledger)."""
import pandas as pd
import pytest

import track_record.grade as grade
from track_record.aggregate import headline, score_mae
from track_record.seed_writer import build_seed_rows, write_seed


def _preds():
    return pd.DataFrame([
        # home favored & wins
        {"sport": "nba", "game_date": "2025-01-15", "home": "LAL", "away": "BOS",
         "mu_margin": 6.0, "mu_total": 220.0, "pred_home_pts": 113.0, "pred_away_pts": 107.0,
         "actual_home_pts": 118.0, "actual_away_pts": 100.0},
        # away favored & wins
        {"sport": "nba", "game_date": "2025-01-16", "home": "MIA", "away": "NYK",
         "mu_margin": -4.0, "mu_total": 210.0, "pred_home_pts": 103.0, "pred_away_pts": 107.0,
         "actual_home_pts": 99.0, "actual_away_pts": 110.0},
        # home favored but loses
        {"sport": "nba", "game_date": "2025-01-17", "home": "GSW", "away": "DEN",
         "mu_margin": 3.0, "mu_total": 230.0, "pred_home_pts": 116.5, "pred_away_pts": 113.5,
         "actual_home_pts": 100.0, "actual_away_pts": 120.0},
    ])


def test_build_seed_rows_grades_and_is_roi_ineligible():
    rows = build_seed_rows(_preds())
    assert len(rows) == 3
    assert (rows["source"] == "seed_backtest").all()
    assert {"home", "away"} <= set(rows.columns)
    assert {"home_pts_err", "away_pts_err"} <= set(rows.columns)
    r0, r1, r2 = rows.iloc[0], rows.iloc[1], rows.iloc[2]
    assert r0["side"] == "home" and r0["subject"] == "LAL" and r0["result"] == "win"
    assert r1["side"] == "away" and r1["subject"] == "NYK" and r1["result"] == "win"
    assert r2["result"] == "loss"                      # favored home lost


def test_headline_over_seed_is_accuracy_only(tmp_path, monkeypatch):
    monkeypatch.setattr(grade, "RESULTS_LEDGER", tmp_path / "ledger.parquet")
    assert write_seed(_preds()) == 3
    led = pd.read_parquet(grade.RESULTS_LEDGER)
    h = headline(led)
    assert h["record"] == "2-1"
    assert h["win_pct"] == pytest.approx(0.6667, abs=1e-3)
    assert score_mae(led) is not None                  # predicted-score error available
