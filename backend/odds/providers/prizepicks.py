"""PrizePicks projections (player props): a free, keyless public endpoint.

PrizePicks is a pick'em projection, not a two-way sportsbook price, so lines
carry ``odds_american=None``; the projection itself is treated as the fair
line, and best-bet edge for props is model P(over) vs 0.5 (Task #10).

``parse`` is pure and unit-tested against a fixture; ``fetch_player_props`` does
the (guarded, best-effort) network call. Scraper fragility is expected; a
failure returns [] and the MultiProvider/nightly step degrades gracefully.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from odds.provider import OddsProvider
from odds.schema import OddsLine
from utils.names import player_slug

logger = logging.getLogger(__name__)

# PrizePicks stat_type -> our model's stat code. Unmapped types are skipped.
STAT_MAP: Dict[str, str] = {
    "Points": "PTS",
    "Rebounds": "REB",           # best_bet composes REB = OREB + DREB
    "Assists": "AST",
    "3-PT Made": "FG3M",
    "Blocked Shots": "BLK",
    "Steals": "STL",
    "Turnovers": "TOV",
    "Free Throws Made": "FTM",
    "FG Made": "FGM",
}

ENDPOINT = "https://api.prizepicks.com/projections?league_id=7&per_page=1000&single_stat=true"


def parse(payload: Dict[str, Any], sport: str = "nba", game_date: Optional[str] = None,
          book: str = "prizepicks") -> List[OddsLine]:
    players = {
        inc["id"]: inc for inc in payload.get("included", [])
        if inc.get("type") == "new_player"
    }
    out: List[OddsLine] = []
    for proj in payload.get("data", []):
        if proj.get("type") != "projection":
            continue
        a = proj.get("attributes", {})
        stat = STAT_MAP.get(a.get("stat_type"))
        line = a.get("line_score")
        if stat is None or line is None:
            continue
        pid = (proj.get("relationships", {}).get("new_player", {}).get("data", {}) or {}).get("id")
        pname = (players.get(pid, {}).get("attributes", {}) or {}).get("name", "")
        if not pname:
            continue
        gd = game_date or (a.get("start_time") or "")[:10]
        slug = player_slug(pname)
        for side in ("over", "under"):
            out.append(OddsLine(
                sport=sport, game_date=gd, market_family="player_prop", subject=slug,
                side=side, line=float(line), stat=stat, odds_american=None,
                book=book, source="prizepicks",
            ).validate())
    return out


class PrizePicksProvider(OddsProvider):
    name = "prizepicks"
    markets = frozenset({"player_prop"})

    def fetch_player_props(self, sport: str, game_date: str) -> List[OddsLine]:
        try:
            import requests

            resp = requests.get(ENDPOINT, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            return parse(resp.json(), sport=sport, game_date=game_date)
        except Exception as e:  # scraper fragility is expected, degrade gracefully
            logger.warning("PrizePicks fetch failed (%s); returning no props", e)
            return []
