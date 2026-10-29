"""Pure odds / probability math for the prediction-media pipeline.

No I/O and no third-party dependencies (just the stdlib ``math``), so this is
trivially unit-testable and safe to import anywhere (odds ingestion, best-bet
selection, track-record grading, content captions).

Conventions
-----------
- **American** odds are numbers like ``-110`` / ``+150`` (favorites negative).
- **Decimal** odds are the European style (``2.0`` == even money).
- A single price's **implied probability** INCLUDES the bookmaker vig, so a
  two-way market sums to > 1. Use the ``devig_*`` helpers to recover the no-vig
  "fair" probabilities that a model edge should be compared against.

This module deliberately contains **no staking / Kelly** logic: this is a
content product (see the project plan), not a bankroll-managed bettor. ``edge``
and ``expected_value`` exist only for honest "our edge %" display and grading.
"""
from __future__ import annotations

import math
from typing import List, Optional, Sequence, Tuple

__all__ = [
    "american_to_decimal",
    "decimal_to_american",
    "american_to_implied_prob",
    "decimal_to_implied_prob",
    "implied_prob_to_decimal",
    "devig",
    "devig_two_way",
    "devig_two_way_american",
    "edge",
    "expected_value",
]


def american_to_decimal(american: float) -> float:
    a = float(american)
    if a == 0:
        raise ValueError("American odds cannot be 0")
    if a > 0:
        return 1.0 + a / 100.0
    return 1.0 + 100.0 / abs(a)


def decimal_to_american(decimal_odds: float) -> float:
    d = float(decimal_odds)
    if d <= 1.0:
        raise ValueError("Decimal odds must be > 1.0")
    if d >= 2.0:
        return round((d - 1.0) * 100.0)
    return round(-100.0 / (d - 1.0))


def decimal_to_implied_prob(decimal_odds: float) -> float:
    d = float(decimal_odds)
    if d <= 1.0:
        raise ValueError("Decimal odds must be > 1.0")
    return 1.0 / d


def american_to_implied_prob(american: float) -> float:
    return decimal_to_implied_prob(american_to_decimal(american))


def implied_prob_to_decimal(prob: float) -> float:
    if not (0.0 < prob <= 1.0):
        raise ValueError("Probability must be in (0, 1]")
    return 1.0 / prob


def devig(probs: Sequence[float], method: str = "multiplicative") -> List[float]:
    """Remove vig from the raw implied probabilities of a single market's
    outcomes. Returns fair probabilities that sum to 1.0.

    ``method="multiplicative"`` (default): proportional normalization, the
        robust, closed-form industry baseline.
    ``method="shin"``: Shin (1993) model attributing the overround to informed
        money, solved numerically. Falls back to multiplicative if the solve
        does not yield a valid distribution.
    """
    ps = [float(p) for p in probs]
    if len(ps) < 2:
        raise ValueError("Need at least two outcomes to de-vig")
    if any(p <= 0.0 for p in ps):
        raise ValueError("Implied probabilities must be positive")
    total = math.fsum(ps)

    if method == "multiplicative":
        return [p / total for p in ps]
    if method == "shin":
        fair = _devig_shin(ps)
        return fair if fair is not None else [p / total for p in ps]
    raise ValueError(f"Unknown de-vig method: {method!r}")


def _devig_shin(ps: Sequence[float]) -> Optional[List[float]]:
    """Shin's method via bisection on the insider proportion ``z`` in [0, 1).

    For each outcome ``i`` with raw implied prob ``p_i`` and booksum
    ``B = sum(p_i)``::

        q_i(z) = (sqrt(z^2 + 4(1-z) * p_i^2 / B) - z) / (2 (1 - z))

    ``z`` is chosen so ``sum_i q_i(z) == 1``. Returns ``None`` (caller falls
    back to multiplicative) if a valid root is not bracketed.
    """
    B = math.fsum(ps)

    def q_sum(z: float) -> float:
        denom = 2.0 * (1.0 - z)
        return math.fsum(
            (math.sqrt(z * z + 4.0 * (1.0 - z) * p * p / B) - z) / denom for p in ps
        )

    lo, hi = 0.0, 0.999999
    f_lo = q_sum(lo) - 1.0
    f_hi = q_sum(hi) - 1.0
    if f_lo == 0.0:
        z = 0.0
    elif (f_lo > 0.0) == (f_hi > 0.0):
        return None  # no sign change -> not bracketed
    else:
        for _ in range(200):
            mid = 0.5 * (lo + hi)
            f_mid = q_sum(mid) - 1.0
            if abs(f_mid) < 1e-13:
                lo = hi = mid
                break
            if (f_mid > 0.0) == (f_lo > 0.0):
                lo, f_lo = mid, f_mid
            else:
                hi = mid
        z = 0.5 * (lo + hi)

    denom = 2.0 * (1.0 - z)
    fair = [(math.sqrt(z * z + 4.0 * (1.0 - z) * p * p / B) - z) / denom for p in ps]
    s = math.fsum(fair)
    if abs(s - 1.0) > 1e-6 or any(not (0.0 < f < 1.0) for f in fair):
        return None
    return fair


def devig_two_way(
    p_a: float, p_b: float, method: str = "multiplicative"
) -> Tuple[float, float]:
    """De-vig a two-way market given the two sides' raw implied probabilities."""
    fair = devig([p_a, p_b], method=method)
    return fair[0], fair[1]


def devig_two_way_american(
    odds_a: float, odds_b: float, method: str = "multiplicative"
) -> Tuple[float, float]:
    """De-vig a two-way market given the two sides' American odds."""
    return devig_two_way(
        american_to_implied_prob(odds_a),
        american_to_implied_prob(odds_b),
        method=method,
    )


def edge(p_model: float, p_fair: float) -> float:
    """Model probability minus the no-vig fair probability (the honest edge)."""
    return float(p_model) - float(p_fair)


def expected_value(p_model: float, decimal_odds: float) -> float:
    """EV per 1 unit staked: ``p*(dec-1) - (1-p)`` == ``p*dec - 1``."""
    return float(p_model) * float(decimal_odds) - 1.0
