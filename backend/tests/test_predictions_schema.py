"""Normalized prediction schemas (backend/predictions/schema.py). Hermetic."""
import pytest

from predictions.schema import GamePrediction, PlayerPropPrediction, make_game_key


def _game(**kw) -> GamePrediction:
    base = dict(
        sport="nba", game_date="2025-01-15", home="LAL", away="BOS",
        mu_total=224.0, sigma_total=20.0, mu_margin=3.0, sigma_margin=14.0,
        pred_home_pts=113.5, pred_away_pts=110.5, p_home_win=0.585,
    )
    base.update(kw)
    return GamePrediction(**base)


def test_game_key_format_and_autoderive():
    g = _game()
    assert g.game_key == "nba:2025-01-15:BOS@LAL"
    assert make_game_key("nba", "2025-01-15", "BOS", "LAL") == g.game_key


def test_sigma_must_be_positive():
    with pytest.raises(ValueError):
        _game(sigma_total=0.0)
    with pytest.raises(ValueError):
        _game(sigma_margin=-1.0)


def test_total_over_under_sum_to_one():
    g = _game()
    assert g.p_total_over(224.0) + g.p_total_under(224.0) == pytest.approx(1.0)
    # over of the mean total is ~0.5
    assert g.p_total_over(224.0) == pytest.approx(0.5, abs=1e-9)


def test_total_over_monotonic_in_line():
    g = _game()
    assert g.p_total_over(210.0) > g.p_total_over(224.0) > g.p_total_over(240.0)


def test_home_cover_consistent_with_win_prob_at_pickem():
    # A spread of 0 (pick'em) => cover prob == win prob from the same margin normal
    g = _game()
    from statistics import NormalDist
    implied = 1.0 - NormalDist(g.mu_margin, g.sigma_margin).cdf(0.0)
    assert g.p_home_cover(0.0) == pytest.approx(implied)
    assert g.p_home_cover(0.0) + g.p_away_cover(0.0) == pytest.approx(1.0)


def test_home_cover_favorite_direction():
    g = _game(mu_margin=6.0)
    # laying -3.5 with a +6 expected margin should be > 50% to cover
    assert g.p_home_cover(-3.5) > 0.5
    # laying a huge -12.5 with only +6 expected margin should be < 50%
    assert g.p_home_cover(-12.5) < 0.5


def test_default_confidence_from_win_prob():
    assert _game(p_home_win=0.5).default_confidence() == pytest.approx(0.0)
    assert _game(p_home_win=0.75).default_confidence() == pytest.approx(0.5)


def test_roundtrip_serialization():
    g = _game()
    g2 = GamePrediction.from_dict(g.to_dict())
    assert g2.game_key == g.game_key
    assert g2.mu_total == g.mu_total


def test_prop_normal_p_over():
    p = PlayerPropPrediction(
        sport="nba", game_date="2025-01-15", player_slug="lebron_james",
        stat="PTS", mu=27.0, home="LAL", away="BOS",
        dist_kind="normal", dist_params={"sigma": 6.0},
    )
    assert p.game_key == "nba:2025-01-15:BOS@LAL"
    assert p.p_over(27.0) == pytest.approx(0.5)
    assert p.p_over(21.0) > p.p_over(33.0)


def test_prop_point_kind_not_implemented():
    p = PlayerPropPrediction(
        sport="nba", game_date="2025-01-15", player_slug="x", stat="PTS", mu=20.0,
    )
    with pytest.raises(NotImplementedError):
        p.p_over(19.5)
