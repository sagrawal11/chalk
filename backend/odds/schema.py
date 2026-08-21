"""Normalized odds line — the source-independent contract for the whole betting
layer (context + grading). One row per (game/player, market, side, book,
snapshot).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, FrozenSet, Optional

from predictions.schema import make_game_key

MARKET_FAMILIES: FrozenSet[str] = frozenset(
    {"player_prop", "team_total", "game_total", "spread", "moneyline"}
)
SIDES: FrozenSet[str] = frozenset({"over", "under", "home", "away"})


@dataclass
class OddsLine:
    sport: str
    game_date: str            # "YYYY-MM-DD"
    market_family: str        # one of MARKET_FAMILIES
    subject: str              # player_slug | canonical team code | "GAME"
    side: str                 # one of SIDES
    odds_american: Optional[int] = None   # None for a pure projection (e.g. PrizePicks)
    line: Optional[float] = None          # None for moneyline
    stat: Optional[str] = None            # e.g. "PTS" for player_prop
    book: str = ""
    source: str = ""
    is_closing: bool = False
    home: str = ""            # canonical
    away: str = ""            # canonical
    captured_at: Optional[str] = None     # ISO timestamp of capture
    game_key: str = ""

    def __post_init__(self) -> None:
        if not self.game_key and self.home and self.away:
            self.game_key = make_game_key(self.sport, self.game_date, self.away, self.home)

    @property
    def odds_id(self) -> str:
        """Stable identity for dedup (independent of capture time / odds value)."""
        line = "" if self.line is None else f"{self.line:g}"
        return "|".join([
            self.sport, self.game_date, self.home, self.away, self.market_family,
            self.subject, self.stat or "", self.side, line, self.book, self.source,
        ])

    def validate(self) -> "OddsLine":
        if self.market_family not in MARKET_FAMILIES:
            raise ValueError(f"bad market_family: {self.market_family!r}")
        if self.side not in SIDES:
            raise ValueError(f"bad side: {self.side!r}")
        if self.market_family in ("spread", "moneyline") and self.side not in ("home", "away"):
            raise ValueError(f"{self.market_family} side must be home/away, got {self.side!r}")
        if self.market_family in ("player_prop", "team_total", "game_total") and self.side not in ("over", "under"):
            raise ValueError(f"{self.market_family} side must be over/under, got {self.side!r}")
        if self.market_family != "moneyline" and self.line is None:
            raise ValueError(f"{self.market_family} requires a line")
        if self.market_family == "player_prop" and not self.stat:
            raise ValueError("player_prop requires a stat")
        return self

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["odds_id"] = self.odds_id
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "OddsLine":
        fields = {k: d[k] for k in d if k in cls.__dataclass_fields__}
        return cls(**fields)
