"""Manual CSV drop: a hand-entered normalized odds file whose columns are
OddsLine fields (sport, game_date, market_family, subject, side, and optionally
odds_american, line, stat, book, home, away). Keeps the system usable for any
market when scrapers break.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import pandas as pd

from odds.provider import OddsProvider
from odds.schema import MARKET_FAMILIES, OddsLine


class ManualProvider(OddsProvider):
    name = "manual"
    markets = frozenset(MARKET_FAMILIES)

    def __init__(self, csv_path: Path):
        self.csv_path = Path(csv_path)
        self._lines: Optional[List[OddsLine]] = None

    def _load(self) -> List[OddsLine]:
        if self._lines is None:
            df = pd.read_csv(self.csv_path)
            df["game_date"] = pd.to_datetime(df["game_date"]).dt.strftime("%Y-%m-%d")
            fields = OddsLine.__dataclass_fields__
            out: List[OddsLine] = []
            for _, r in df.iterrows():
                kw = {k: r[k] for k in df.columns if k in fields and pd.notna(r[k])}
                kw.setdefault("source", "manual")
                if "odds_american" in kw:
                    kw["odds_american"] = int(kw["odds_american"])
                out.append(OddsLine(**kw).validate())
            self._lines = out
        return self._lines

    def fetch_game_markets(self, sport: str, game_date: str) -> List[OddsLine]:
        return [
            ln for ln in self._load()
            if ln.sport == sport and ln.game_date == game_date
            and ln.market_family in ("moneyline", "spread", "game_total", "team_total")
        ]

    def fetch_player_props(self, sport: str, game_date: str) -> List[OddsLine]:
        return [
            ln for ln in self._load()
            if ln.sport == sport and ln.game_date == game_date and ln.market_family == "player_prop"
        ]
