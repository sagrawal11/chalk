"""Sport ABC + lazy registry + NBA plugin identity (backend/sports/).

Hermetic: exercises only the lazy registry and the NBA plugin's *cheap* identity
methods. It never calls predict_player/predict_game/schedule (models/network),
and only touches player_targets() behind an importorskip on feature_engine.
"""
import pytest

from sports.base import Sport, available_sports, get_sport, register_sport
from sports.nba.sport import NBASport


def test_nba_is_registered_lazily():
    assert "nba" in available_sports()


def test_registry_roundtrip_with_dummy_sport():
    class _Dummy(Sport):
        key = "dummy"
        display_name = "Dummy"
        capabilities = frozenset({"x"})

        def canonical_team(self, code, *, strict=True):
            return str(code).upper()

        def current_season(self):
            return "2024-25"

        def season_from_date(self, game_date):
            return "2024-25"

        def player_targets(self):
            return ["A"]

        def team_targets(self):
            return ["margin"]

        def score_ranges(self):
            return {}

    register_sport("dummy", _Dummy)
    got = get_sport("dummy")
    assert isinstance(got, _Dummy)
    assert get_sport("DUMMY") is got  # cached + case-insensitive
    assert "dummy" in available_sports()


def test_unknown_sport_raises():
    with pytest.raises(KeyError):
        get_sport("quidditch")


def test_nba_identity_methods():
    nba = NBASport()
    assert nba.key == "nba"
    assert nba.display_name == "NBA"
    # canonical_team delegates to the teams module (folds relocations)
    assert nba.canonical_team("BRK") == "BKN"
    assert nba.canonical_team("nop") == "NOP"


def test_nba_season_from_date():
    nba = NBASport()
    assert nba.season_from_date("2025-01-15") == "2024-25"  # Jan -> season started prior year
    assert nba.season_from_date("2024-11-20") == "2024-25"
    assert nba.season_from_date("2025-10-30") == "2025-26"


def test_nba_current_season_format():
    import re

    assert re.fullmatch(r"\d{4}-\d{2}", NBASport().current_season())


def test_nba_team_targets_and_score_ranges():
    nba = NBASport()
    assert nba.team_targets() == ["margin", "total", "home_pts", "away_pts"]
    r = nba.score_ranges()
    assert r["total"][0] < r["total"][1]
    assert r["margin"][0] < 0 < r["margin"][1]


def test_nba_supports_flags():
    nba = NBASport()
    assert nba.supports("predict_player")
    assert nba.supports("predict_game")
    assert not nba.supports("teleport")


def test_nba_player_targets_when_feature_engine_importable():
    pytest.importorskip("feature_engine")
    targets = NBASport().player_targets()
    assert "PTS" in targets and "AST" in targets and len(targets) >= 5
