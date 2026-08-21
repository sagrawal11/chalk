"""Historical team-market odds from a normalized CSV (sportsbookreview / Kaggle
free datasets). Enables the historical record simulation + ATS/O-U grading. No
network.

Expected CSV columns (one row per game):
    game_date, home, away, moneyline_home, moneyline_away, spread_home, total
    [optional] is_closing
Missing moneyline/spread/total columns are simply skipped. Spread/total prices
default to -110 when a price column is absent.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import pandas as pd

from odds.provider import OddsProvider
from odds.schema import OddsLine
from sports.base import get_sport

_DEFAULT_PRICE = -110


class CSVBackfillProvider(OddsProvider):
    name = "csv_backfill"
    markets = frozenset({"moneyline", "spread", "game_total"})

    def __init__(self, csv_path: Path, book: str = "sbr_close"):
        self.csv_path = Path(csv_path)
        self.book = book
        self._df: Optional[pd.DataFrame] = None

    def _load(self) -> pd.DataFrame:
        if self._df is None:
            df = pd.read_csv(self.csv_path)
            df["game_date"] = pd.to_datetime(df["game_date"]).dt.strftime("%Y-%m-%d")
            self._df = df
        return self._df

    def _rows_for(self, sport: str, df: pd.DataFrame) -> List[OddsLine]:
        canon = get_sport(sport).canonical_team
        out: List[OddsLine] = []
        for _, r in df.iterrows():
            home, away = canon(r["home"], strict=False), canon(r["away"], strict=False)
            is_closing = bool(r["is_closing"]) if "is_closing" in df.columns and pd.notna(r.get("is_closing")) else True
            common = dict(sport=sport, game_date=r["game_date"], home=home, away=away,
                          book=self.book, source=self.name, is_closing=is_closing)
            if {"moneyline_home", "moneyline_away"} <= set(df.columns) and pd.notna(r.get("moneyline_home")):
                out.append(OddsLine(market_family="moneyline", subject=home, side="home",
                                    odds_american=int(r["moneyline_home"]), **common))
                out.append(OddsLine(market_family="moneyline", subject=away, side="away",
                                    odds_american=int(r["moneyline_away"]), **common))
            if "spread_home" in df.columns and pd.notna(r.get("spread_home")):
                sh = float(r["spread_home"])
                out.append(OddsLine(market_family="spread", subject=home, side="home",
                                    line=sh, odds_american=_DEFAULT_PRICE, **common))
                out.append(OddsLine(market_family="spread", subject=away, side="away",
                                    line=-sh, odds_american=_DEFAULT_PRICE, **common))
            if "total" in df.columns and pd.notna(r.get("total")):
                t = float(r["total"])
                out.append(OddsLine(market_family="game_total", subject="GAME", side="over",
                                    line=t, odds_american=_DEFAULT_PRICE, **common))
                out.append(OddsLine(market_family="game_total", subject="GAME", side="under",
                                    line=t, odds_american=_DEFAULT_PRICE, **common))
        return [ln.validate() for ln in out]

    def fetch_game_markets(self, sport: str, game_date: str) -> List[OddsLine]:
        df = self._load()
        return self._rows_for(sport, df[df["game_date"] == game_date])

    def all_lines(self, sport: str) -> List[OddsLine]:
        """Every historical line (for the backtest / record simulation)."""
        return self._rows_for(sport, self._load())
