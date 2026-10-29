"""Predictive distributions for player counting stats.

A MAE-optimized point prediction cannot answer "what is P(PTS > 24.5)?", which
is exactly what a prop needs. This turns each per-stat mean prediction into a
distribution:

- ``PoissonNBHead`` (primary): counting stats are non-negative and overdispersed,
  so a Negative-Binomial (Poisson when not overdispersed) with a dispersion
  fitted on out-of-sample residuals fits far better than a Gaussian and yields a
  closed-form ``P(X > line)``.
- ``EmpiricalResidualHead`` (fallback/backstop): the empirical distribution of
  holdout residuals around the mean prediction.

Dispersion is fitted by method-of-moments on holdout residuals (``fit_nb_dispersion``)
so it is never estimated in-sample.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from scipy.stats import nbinom, poisson

_POISSON_R_CEILING = 1e6  # dispersion above this is treated as Poisson


@dataclass
class PoissonNBHead:
    """Negative-Binomial (or Poisson) head for a single stat prediction."""

    mu: float
    dispersion: Optional[float] = None  # NB "size" r; None/inf/huge -> Poisson

    def _nb_params(self):
        mu = max(float(self.mu), 1e-6)
        r = self.dispersion
        if r is None or not np.isfinite(r) or r <= 0 or r > _POISSON_R_CEILING:
            return None, mu  # Poisson
        p = r / (r + mu)
        return (r, p), mu

    def mean(self) -> float:
        return max(float(self.mu), 0.0)

    def sf(self, line: float) -> float:
        """P(X > line). For a half-point line (e.g. 24.5) this is P(X >= 25)."""
        params, mu = self._nb_params()
        k = math.floor(line)
        if params is None:
            return float(poisson.sf(k, mu))
        r, p = params
        return float(nbinom.sf(k, r, p))

    def cdf(self, x: float) -> float:
        params, mu = self._nb_params()
        k = math.floor(x)
        if params is None:
            return float(poisson.cdf(k, mu))
        r, p = params
        return float(nbinom.cdf(k, r, p))

    def p_over(self, line: float) -> float:
        return self.sf(line)

    def p_under(self, line: float) -> float:
        return 1.0 - self.sf(line)


@dataclass
class EmpiricalResidualHead:
    """Mean prediction + empirical holdout-residual distribution."""

    mu: float
    residuals: np.ndarray = field(default_factory=lambda: np.zeros(0))

    def mean(self) -> float:
        return float(self.mu)

    def sf(self, line: float) -> float:
        if len(self.residuals) == 0:
            return 1.0 if self.mu > line else 0.0
        return float(np.mean((self.mu + self.residuals) > line))

    def p_over(self, line: float) -> float:
        return self.sf(line)

    def p_under(self, line: float) -> float:
        return 1.0 - self.sf(line)


def nb_dispersion_from_moments(mu_mean: float, mu_sq_mean: float, resid_var: float) -> float:
    """NB dispersion ``r`` from out-of-sample moments, using
    Var(y) ≈ E[mu] + E[mu^2]/r. Returns ``inf`` (⇒ Poisson) when not
    overdispersed. Lets trainers fit dispersion from compact holdout moments
    (no need to ship residual arrays)."""
    denom = float(resid_var) - float(mu_mean)
    if not np.isfinite(denom) or denom <= 1e-6:
        return float("inf")
    return float(max(float(mu_sq_mean) / denom, 0.1))


def fit_nb_dispersion(mu: np.ndarray, y: np.ndarray) -> float:
    """Method-of-moments NB dispersion ``r`` from OOS predictions ``mu`` and
    actuals ``y``, using Var(y) ≈ E[mu] + E[mu^2]/r. Returns ``inf`` (⇒ Poisson)
    when the data is not overdispersed or too small to estimate.
    """
    mu = np.asarray(mu, dtype=float)
    y = np.asarray(y, dtype=float)
    m = np.isfinite(mu) & np.isfinite(y) & (mu > 0)
    mu, y = mu[m], y[m]
    if len(mu) < 30:
        return float("inf")
    resid_var = float(np.mean((y - mu) ** 2))
    denom = resid_var - float(np.mean(mu))
    if denom <= 1e-6:
        return float("inf")  # not overdispersed -> Poisson
    r = float(np.mean(mu ** 2)) / denom
    return float(max(r, 0.1))
