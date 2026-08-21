"""Unit tests for the pure odds/probability math (backend/utils/odds_math.py).

Acceptance criteria from the plan:
- -110 / -110 de-vigs to 0.5 / 0.5
- -200 / +170 de-vigs to fair probabilities that sum to 1.0
- Kelly at p=0.55/decimal=2.0 has EV 0.10; -EV bets are recognizable
"""
import pytest

from utils.odds_math import (
    american_to_decimal,
    american_to_implied_prob,
    decimal_to_american,
    decimal_to_implied_prob,
    devig,
    devig_two_way_american,
    edge,
    expected_value,
    implied_prob_to_decimal,
)


def test_american_to_decimal():
    assert american_to_decimal(100) == pytest.approx(2.0)
    assert american_to_decimal(-110) == pytest.approx(1.9090909, rel=1e-6)
    assert american_to_decimal(150) == pytest.approx(2.5)
    assert american_to_decimal(-200) == pytest.approx(1.5)


def test_american_zero_is_invalid():
    with pytest.raises(ValueError):
        american_to_decimal(0)


def test_american_implied_prob():
    assert american_to_implied_prob(-110) == pytest.approx(110 / 210)
    assert american_to_implied_prob(100) == pytest.approx(0.5)
    assert american_to_implied_prob(-200) == pytest.approx(2 / 3)


def test_decimal_american_roundtrip():
    for a in (-250, -150, -110, 100, 120, 300):
        assert decimal_to_american(american_to_decimal(a)) == pytest.approx(a)


def test_decimal_prob_roundtrip():
    for p in (0.25, 0.5, 0.524, 0.9):
        assert decimal_to_implied_prob(implied_prob_to_decimal(p)) == pytest.approx(p)


def test_devig_two_way_balanced_is_fifty_fifty():
    over, under = devig_two_way_american(-110, -110)
    assert over == pytest.approx(0.5)
    assert under == pytest.approx(0.5)


def test_devig_two_way_sums_to_one_and_favorite_leads():
    o, u = devig_two_way_american(-200, +170)
    assert o + u == pytest.approx(1.0)
    assert o > u  # -200 favorite must carry the higher fair probability


def test_devig_shin_valid_distribution():
    o, u = devig_two_way_american(-200, +170, method="shin")
    assert o + u == pytest.approx(1.0)
    assert 0.0 < u < o < 1.0
    # Shin should stay in the same ballpark as multiplicative, not diverge wildly
    o_mult, _ = devig_two_way_american(-200, +170, method="multiplicative")
    assert abs(o - o_mult) < 0.05


def test_multiway_devig_sums_to_one():
    fair = devig([0.40, 0.35, 0.35])  # a 3-way market with ~10% overround
    assert sum(fair) == pytest.approx(1.0)
    assert all(0.0 < f < 1.0 for f in fair)


def test_edge_and_expected_value():
    assert edge(0.55, 0.50) == pytest.approx(0.05)
    assert expected_value(0.55, 2.0) == pytest.approx(0.10)  # +EV
    assert expected_value(0.50, 2.0) == pytest.approx(0.0)   # fair coin, no edge
    assert expected_value(0.45, 2.0) == pytest.approx(-0.10)  # -EV
