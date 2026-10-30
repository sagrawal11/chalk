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


def test_default_confidence_from_win_prob():
    assert _game(p_home_win=0.5).default_confidence() == pytest.approx(0.0)
    assert _game(p_home_win=0.75).default_confidence() == pytest.approx(0.5)


def test_roundtrip_serialization():
    g = _game()
    g2 = GamePrediction.from_dict(g.to_dict())
    assert g2.game_key == g.game_key
    assert g2.mu_total == g.mu_total


def test_prop_construction_and_game_key():
    p = PlayerPropPrediction(
        sport="nba", game_date="2025-01-15", player_slug="lebron_james",
        stat="PTS", mu=27.0, home="LAL", away="BOS",
    )
    assert p.game_key == "nba:2025-01-15:BOS@LAL"
    assert p.mu == 27.0 and p.stat == "PTS"
