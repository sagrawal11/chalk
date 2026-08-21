"""The ``OddsProvider`` interface — the vendor-agnostic seam. The betting layer
depends only on this ABC and the normalized ``OddsLine`` schema, never on a
concrete free source, so swapping/adding sources is config, not code.
"""
from __future__ import annotations

from abc import ABC
from typing import FrozenSet, List

from odds.schema import OddsLine


class OddsProvider(ABC):
    name: str = ""
    # Which market families this provider can supply.
    markets: FrozenSet[str] = frozenset()

    def supports(self, market_family: str) -> bool:
        return market_family in self.markets

    def fetch_game_markets(self, sport: str, game_date: str) -> List[OddsLine]:
        """Team markets (moneyline / spread / totals). Default: none."""
        return []

    def fetch_player_props(self, sport: str, game_date: str) -> List[OddsLine]:
        """Player prop lines. Default: none."""
        return []


class MultiProvider(OddsProvider):
    """Fan out to several providers and concatenate (best-line / consensus).
    A provider that raises is skipped so one broken free scraper can't take the
    whole slate down."""

    name = "multi"

    def __init__(self, providers: List[OddsProvider]):
        self.providers = providers
        self.markets = frozenset().union(*(p.markets for p in providers)) if providers else frozenset()

    def _gather(self, method: str, sport: str, game_date: str) -> List[OddsLine]:
        out: List[OddsLine] = []
        for p in self.providers:
            try:
                out.extend(getattr(p, method)(sport, game_date))
            except Exception:  # a broken free source degrades gracefully
                continue
        return out

    def fetch_game_markets(self, sport: str, game_date: str) -> List[OddsLine]:
        return self._gather("fetch_game_markets", sport, game_date)

    def fetch_player_props(self, sport: str, game_date: str) -> List[OddsLine]:
        return self._gather("fetch_player_props", sport, game_date)
