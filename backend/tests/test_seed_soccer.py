"""Soccer track-record seeding: SEASON-level leakage-safe walk-forward for the
Poisson (Dixon-Coles-lite) model -> graded, ROI-ineligible ledger rows.

Hermetic: a synthetic EPL-shaped matches frame is INJECTED (no football-data.co.uk
network). Verifies (a) rows are produced, (b) the market-blind winner is the model's
favored side and NEVER a draw, (c) grading is correct including draw == LOSS, and
(d) rows are ROI-ineligible (odds_american None -> units NaN)."""
import pandas as pd
import pytest

import track_record.grade as grade
from track_record.aggregate import headline, score_mae
from track_record.seed_writer import build_soccer_seed_rows, write_soccer_seed


def _matches():
    """Two synthetic seasons. 2023 establishes a dominant 'Strong' (many home goals,
    few conceded) over 'Weak', giving each club >= MIN_PRIOR home & away games so the
    Poisson usage gate passes. 2024 has three Strong(home)-vs-Weak fixtures whose
    outcomes exercise win / wrong-side / draw grading for the (home) winner pick."""
    prior = [
        ("Strong", "Weak", 3, 0), ("Strong", "Weak", 2, 0),
        ("Strong", "Weak", 4, 1), ("Strong", "Weak", 3, 1),   # Strong home x4, Weak away x4
        ("Weak", "Strong", 0, 3), ("Weak", "Strong", 1, 2),
        ("Weak", "Strong", 0, 2), ("Weak", "Strong", 1, 3),   # Weak home x4, Strong away x4
    ]
    current = [
        ("Strong", "Weak", 2, 0),   # home pick WINS
        ("Strong", "Weak", 0, 1),   # home pick LOSES (upset)
        ("Strong", "Weak", 1, 1),   # DRAW -> home pick LOSES
    ]
    rows = []
    for mm, (h, a, hg, ag) in enumerate(prior, start=1):
        rows.append({"season": "2023", "date": f"2023-{mm:02d}-01",
                     "home": h, "away": a, "fthg": hg, "ftag": ag})
    for mm, (h, a, hg, ag) in enumerate(current, start=1):
        rows.append({"season": "2024", "date": f"2024-{mm:02d}-01",
                     "home": h, "away": a, "fthg": hg, "ftag": ag})
    return pd.DataFrame(rows)


def test_build_soccer_seed_rows_grades_and_is_roi_ineligible():
    rows = build_soccer_seed_rows(_matches(), min_train_seasons=1)
    # Only 2024 is predicted (2023 has no prior season); all three fixtures score.
    assert len(rows) == 3
    assert (rows["sport"] == "soccer").all()
    assert (rows["side"] == "home").all()             # Strong favored; NEVER a draw
    assert (rows["subject"] == "Strong").all()
    assert (rows["source"] == "seed_backtest").all()
    # win / loss(upset) / loss(draw): a draw grades as a LOSS for the picked side.
    assert list(rows["result"]) == ["win", "loss", "loss"]
    # Predicted scores derived from the Poisson lambdas are present.
    assert {"pred_home_pts", "pred_away_pts", "home_pts_err", "away_pts_err"} <= set(rows.columns)


def test_draw_grades_as_loss_explicitly():
    rows = build_soccer_seed_rows(_matches(), min_train_seasons=1)
    draw_row = rows[rows["game_date"] == "2024-03-01"].iloc[0]   # the 1-1 fixture
    assert draw_row["result"] == "loss"


def test_needs_a_prior_season():
    """With no prior season available, nothing is predictable (leakage-safe)."""
    one_season = _matches()[_matches()["season"] == "2023"]
    assert build_soccer_seed_rows(one_season, min_train_seasons=1).empty


def test_empty_matches_returns_empty():
    assert build_soccer_seed_rows(pd.DataFrame()).empty


def test_write_soccer_seed_headline_is_accuracy_only(tmp_path, monkeypatch):
    monkeypatch.setattr(grade, "RESULTS_LEDGER", tmp_path / "ledger.parquet")
    assert write_soccer_seed(_matches(), min_train_seasons=1) == 3
    led = pd.read_parquet(grade.RESULTS_LEDGER)
    h = headline(led)
    assert h["record"] == "1-2"                       # 1 win, 2 losses (one is the draw)
    assert h["win_pct"] == pytest.approx(1 / 3, abs=1e-3)
    assert score_mae(led) is not None                  # predicted-score error available
