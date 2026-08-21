"""Predictive distribution heads (backend/models/distribution.py)."""
import numpy as np
import pytest

from models.distribution import EmpiricalResidualHead, PoissonNBHead, fit_nb_dispersion


def test_nb_sf_monotonic_and_bounded():
    d = PoissonNBHead(mu=25.0, dispersion=15.0)
    assert 0.0 <= d.sf(40.0) < d.sf(25.0) < d.sf(10.0) <= 1.0
    assert d.p_over(24.5) + d.p_under(24.5) == pytest.approx(1.0)


def test_nb_more_dispersed_than_poisson_in_tail():
    mu = 25.0
    nb = PoissonNBHead(mu=mu, dispersion=8.0)   # overdispersed
    po = PoissonNBHead(mu=mu, dispersion=None)  # Poisson
    # Fatter tail => higher P(X > high line) for NB than Poisson.
    assert nb.sf(35.5) > po.sf(35.5)


def test_poisson_fallback_matches_scipy():
    from scipy.stats import poisson

    d = PoissonNBHead(mu=6.0, dispersion=None)
    assert d.sf(8.5) == pytest.approx(float(poisson.sf(8, 6.0)))


def test_half_point_line_semantics():
    # P(X > 24.5) == P(X >= 25) == sf(24)
    d = PoissonNBHead(mu=20.0, dispersion=None)
    from scipy.stats import poisson

    assert d.sf(24.5) == pytest.approx(float(poisson.sf(24, 20.0)))


def test_empirical_head():
    resid = np.array([-3.0, -1.0, 0.0, 1.0, 3.0])
    d = EmpiricalResidualHead(mu=20.0, residuals=resid)
    # samples: 17,19,20,21,23 -> P(>20) = 2/5
    assert d.sf(20.0) == pytest.approx(0.4)
    assert d.p_under(20.0) == pytest.approx(0.6)


def test_fit_dispersion_recovers_overdispersion():
    rng = np.random.default_rng(0)
    mu_true, r_true = 20.0, 10.0
    p = r_true / (r_true + mu_true)
    y = rng.negative_binomial(r_true, p, size=5000).astype(float)
    mu = np.full_like(y, mu_true)
    r_hat = fit_nb_dispersion(mu, y)
    assert 4.0 < r_hat < 30.0  # MoM recovers the right ballpark


def test_fit_dispersion_poisson_when_not_overdispersed():
    rng = np.random.default_rng(1)
    y = rng.poisson(10.0, size=3000).astype(float)
    mu = np.full_like(y, 10.0)
    # Poisson data has negligible overdispersion -> a very large r (== Poisson in
    # the limit). MoM won't return exactly inf on noisy finite data; it must at
    # least be far above the overdispersed regime (r~10).
    r_hat = fit_nb_dispersion(mu, y)
    assert r_hat == float("inf") or r_hat > 100.0
