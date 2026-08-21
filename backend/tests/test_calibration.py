"""Calibration metrics (backend/model_training/evaluate_calibration.py). Hermetic."""
import numpy as np
import pytest

from model_training.evaluate_calibration import (
    brier_score,
    interval_coverage,
    log_loss,
    pit_uniformity,
    pit_values,
    reliability_bins,
)


def test_brier_and_logloss_basic():
    # Perfect predictions -> 0 Brier.
    assert brier_score([1.0, 0.0, 1.0], [1, 0, 1]) == pytest.approx(0.0)
    assert brier_score([0.5, 0.5], [1, 0]) == pytest.approx(0.25)
    # log_loss of a confident correct prediction is small; wrong is large.
    assert log_loss([0.99], [1]) < log_loss([0.5], [1]) < log_loss([0.01], [1])


def test_pit_uniform_for_well_calibrated_normal():
    rng = np.random.default_rng(0)
    n = 5000
    mu = np.zeros(n)
    sigma = np.ones(n)
    actual = rng.normal(0.0, 1.0, size=n)  # drawn from the SAME normal -> calibrated
    pit = pit_values(actual, mu, sigma)
    # ~80% of PIT mass should fall in the central 80% interval.
    assert interval_coverage(pit, 0.8) == pytest.approx(0.8, abs=0.05)
    assert interval_coverage(pit, 0.5) == pytest.approx(0.5, abs=0.05)
    # Uniform PIT -> low chi-square (10 bins, 5000 samples).
    assert pit_uniformity(pit, nbins=10)["chi2"] < 25.0


def test_pit_detects_miscalibration():
    rng = np.random.default_rng(1)
    n = 5000
    # Model claims sigma=1 but reality is far wider -> under-dispersed -> PIT piles at the edges.
    actual = rng.normal(0.0, 3.0, size=n)
    pit = pit_values(actual, np.zeros(n), np.ones(n))
    assert interval_coverage(pit, 0.8) < 0.6  # far below nominal 0.8


def test_reliability_bins_shape():
    rng = np.random.default_rng(2)
    p = rng.uniform(0, 1, size=1000)
    y = (rng.uniform(0, 1, size=1000) < p).astype(int)  # calibrated by construction
    bins = reliability_bins(p, y, nbins=10)
    assert len(bins) >= 5
    for b in bins:
        assert 0.0 <= b["pred_mean"] <= 1.0 and 0.0 <= b["obs_rate"] <= 1.0
