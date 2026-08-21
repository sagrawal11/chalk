"""Live soccer lines from The Odds API (free tier) across EPL / UCL / MLS — the
3-way market anchor. Soccer markets are highly efficient, so the de-vigged 1X2
(home/draw/away) is the accurate prediction. Shares ODDS_API_KEY; fails soft.
"""
from __future__ import annotations

import logging
from typing import Callable, Dict, Optional, Tuple

from sports.nba.live_odds import _get_key
from sports.soccer.teams import COMPETITIONS, canonical_team
from utils.odds_math import decimal_to_implied_prob, devig

logger = logging.getLogger(__name__)
_URL = "https://api.the-odds-api.com/v4/sports/{sk}/odds"


def fetch_soccer_lines(api_key: Optional[str] = None, competitions=None,
                       regions: str = "us,uk", timeout: int = 20
                       ) -> Dict[Tuple[str, str], Dict]:
    """{(home, away)} -> {p_home, p_draw, p_away, total, competition} from the
    de-vigged 3-way moneyline of the first book quoting all three outcomes."""
    key = _get_key(api_key)
    if not key:
        return {}
    import requests
    out: Dict[Tuple[str, str], Dict] = {}
    for comp in (competitions or list(COMPETITIONS)):
        try:
            r = requests.get(_URL.format(sk=COMPETITIONS[comp]),
                             params={"apiKey": key, "regions": regions,
                                     "markets": "h2h,totals", "oddsFormat": "decimal"}, timeout=timeout)
            r.raise_for_status()
            events = r.json()
        except Exception as e:
            logger.warning("The Odds API (%s) fetch failed: %s", comp, e)
            continue
        for ev in events or []:
            home, away = canonical_team(ev.get("home_team", ""), strict=False), canonical_team(ev.get("away_team", ""), strict=False)
            if not home or not away:
                continue
            probs = total = None
            for bk in ev.get("bookmakers", []):
                h = d = a = None
                for mk in bk.get("markets", []):
                    if mk.get("key") == "h2h":
                        for oc in mk.get("outcomes", []):
                            nm, price = oc.get("name", ""), oc.get("price")
                            if nm == "Draw":
                                d = price
                            elif canonical_team(nm, strict=False) == home:
                                h = price
                            elif canonical_team(nm, strict=False) == away:
                                a = price
                    elif mk.get("key") == "totals":
                        overs = [float(oc["point"]) for oc in mk.get("outcomes", [])
                                 if str(oc.get("name", "")).lower() == "over" and oc.get("point") is not None]
                        if overs:  # pick the line closest to the standard 2.5
                            total = min(overs, key=lambda x: abs(x - 2.5))
                if h and d and a and probs is None:
                    fair = devig([decimal_to_implied_prob(h), decimal_to_implied_prob(d),
                                  decimal_to_implied_prob(a)], "multiplicative")
                    probs = fair
                if probs is not None and total is not None:
                    break
            if probs is not None:
                out[(home, away)] = {"p_home": probs[0], "p_draw": probs[1], "p_away": probs[2],
                                     "total": total if total is not None else 2.5, "competition": comp}
    logger.info("The Odds API: %d soccer games with lines", len(out))
    return out


def market_provider(api_key: Optional[str] = None, competitions=None) -> Callable[..., Optional[Dict]]:
    cache: Dict[str, Dict] = {}

    def _lookup(home: str, away: str, game_date: Optional[str] = None):
        if "lines" not in cache:
            cache["lines"] = fetch_soccer_lines(api_key, competitions)
        return cache["lines"].get((canonical_team(home, strict=False), canonical_team(away, strict=False)))

    return _lookup
