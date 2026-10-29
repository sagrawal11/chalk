"""Sport plugin interface + lazy registry.

Dependency-free (only ``abc``/``typing``) so importing this never drags in
pandas / lightgbm. Concrete sports live in ``sports/<key>/`` and are registered
via a **lazy factory**, so the heavy model/data imports happen only when a sport
is actually instantiated (``get_sport("nba")``), not at import time.

The interface is intentionally lean: identity/data methods are abstract (cheap,
pure), while capabilities that need trained models or network access have
default implementations that raise ``NotImplementedError`` and are overridden by
plugins where the underlying implementation exists. New capabilities are added
here as the generic core grows, not speculatively.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, FrozenSet, List, Optional


class Sport(ABC):
    key: str = ""
    display_name: str = ""
    capabilities: FrozenSet[str] = frozenset()

    # --- identity / data (cheap, pure) ---
    @abstractmethod
    def canonical_team(self, code: str, *, strict: bool = True) -> str: ...

    @abstractmethod
    def current_season(self) -> str: ...

    @abstractmethod
    def season_from_date(self, game_date: str) -> str: ...

    @abstractmethod
    def player_targets(self) -> List[str]: ...

    @abstractmethod
    def team_targets(self) -> List[str]: ...

    @abstractmethod
    def score_ranges(self) -> Dict[str, Any]: ...

    def supports(self, capability: str) -> bool:
        return capability in self.capabilities

    # --- capabilities requiring trained models / network (overridden by plugins) ---
    def predict_player(self, **kwargs: Any) -> Optional[Dict[str, Any]]:
        raise NotImplementedError(f"{self.key or 'sport'} does not implement predict_player")

    def predict_game(self, **kwargs: Any) -> Any:
        raise NotImplementedError(f"{self.key or 'sport'} does not implement predict_game")

    def schedule(self, game_date: Optional[str] = None) -> List[Dict[str, Any]]:
        raise NotImplementedError(f"{self.key or 'sport'} does not implement schedule")


_FACTORIES: Dict[str, Callable[[], Sport]] = {}
_INSTANCES: Dict[str, Sport] = {}


def register_sport(key: str, factory: Callable[[], Sport]) -> None:
    """Register a lazy factory for a sport (does not instantiate)."""
    _FACTORIES[key.lower()] = factory


def get_sport(key: str) -> Sport:
    """Return the (cached) Sport instance for ``key``; instantiates on first use."""
    k = key.lower()
    if k not in _INSTANCES:
        if k not in _FACTORIES:
            raise KeyError(f"No sport registered for {key!r}; available: {available_sports()}")
        _INSTANCES[k] = _FACTORIES[k]()
    return _INSTANCES[k]


def available_sports() -> List[str]:
    return sorted(_FACTORIES)


# Plugins registered lazily (heavy imports deferred to first use).
def _make_nba() -> Sport:
    from sports.nba.sport import NBASport

    return NBASport()


def _make_nfl() -> Sport:
    from sports.nfl.sport import NFLSport

    return NFLSport()


def _make_mlb() -> Sport:
    from sports.mlb.sport import MLBSport

    return MLBSport()


def _make_nhl() -> Sport:
    from sports.nhl.sport import NHLSport

    return NHLSport()


def _make_soccer() -> Sport:
    from sports.soccer.sport import SoccerSport

    return SoccerSport()


register_sport("nba", _make_nba)
register_sport("nfl", _make_nfl)
register_sport("mlb", _make_mlb)
register_sport("nhl", _make_nhl)
register_sport("soccer", _make_soccer)
