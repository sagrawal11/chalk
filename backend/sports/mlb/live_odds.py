"""Live MLB lines from The Odds API (free tier), the market anchor for
upcoming/in-progress games. MLB has no meaningful point spread (run line is a
fixed +/-1.5), so we anchor the WINNER on the de-vigged moneyline and the TOTAL
on the market total. Needs ODDS_API_KEY (shared with the NBA provider). Fails
soft: no key / network error -> {} -> team-model fallback.
"""
from __future__ import annotations

import logging
from typing import Callable, Dict, Optional, Tuple

from sports.mlb.teams import canonical_team
from sports.nba.live_odds import _get_key
from utils.odds_math import devig_two_way_american

logger = logging.getLogger(__name__)
_URL = "https://api.the-odds-api.com/v4/sports/baseball_mlb/odds"


def fetch_mlb_lines(api_key: Optional[str] = None, regions: str = "us", timeout: int = 15
                    ) -> Dict[Tuple[str, str], Dict[str, float]]:
    """Current MLB games keyed by (home_code, away_code) -> {p_home_win, total}
    from the first book quoting both a moneyline and a total."""
    key = _get_key(api_key)
    if not key:
        return {}
    try:
        import requests
        r = requests.get(_URL, params={"apiKey": key, "regions": regions,
                                       "markets": "h2h,totals", "oddsFormat": "american"}, timeout=timeout)
        r.raise_for_status()
        events = r.json()
    except Exception as e:
        logger.warning("The Odds API (MLB) fetch failed: %s", e)
        return {}

    out: Dict[Tuple[str, str], Dict[str, float]] = {}
    for ev in events or []:
        home, away = canonical_team(ev.get("home_team", ""), strict=False), canonical_team(ev.get("away_team", ""), strict=False)
        if not home or not away:
            continue
        p_home = total = None
        for bk in ev.get("bookmakers", []):
            h_ml = a_ml = None
            for mk in bk.get("markets", []):
                if mk.get("key") == "h2h":
                    for oc in mk.get("outcomes", []):
                        c = canonical_team(oc.get("name", ""), strict=False)
                        if c == home:
                            h_ml = oc.get("price")
                        elif c == away:
                            a_ml = oc.get("price")
                elif mk.get("key") == "totals":
                    for oc in mk.get("outcomes", []):
                        if str(oc.get("name", "")).lower() == "over" and oc.get("point") is not None:
                            total = float(oc["point"])
            if h_ml is not None and a_ml is not None and p_home is None:
                p_home = float(devig_two_way_american(float(h_ml), float(a_ml))[0])  # fair home win prob
            if p_home is not None and total is not None:
                break
        if p_home is not None and total is not None:
            out[(home, away)] = {"p_home_win": p_home, "total": total}
    logger.info("The Odds API: %d MLB games with lines", len(out))
    return out


def market_provider(api_key: Optional[str] = None) -> Callable[[str, str, str], Optional[Dict[str, float]]]:
    """Cached (home, away, date) -> {p_home_win, total} | None for the predictor."""
    cache: Dict[str, Dict[Tuple[str, str], Dict[str, float]]] = {}

    def _lookup(home: str, away: str, game_date: str):
        if "lines" not in cache:
            cache["lines"] = fetch_mlb_lines(api_key)
        return cache["lines"].get((home, away))

    return _lookup
