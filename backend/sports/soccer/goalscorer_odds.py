"""Market-anchored anytime-goalscorer probabilities from The Odds API (free tier).

Soccer has no free player-stats feed to train a prop model (unlike the other sports),
but the market IS the accuracy ceiling and ``player_goal_scorer_anytime`` is quoted on
the free tier. This surfaces the top market-implied scorers for a FEW marquee upcoming
matches as display content.

Quota discipline: player props are a PER-EVENT endpoint (~1 credit per event for one
market/region; the free tier is 500/mo), so callers cap the number of events. The bulk
1X2 anchor (``live_odds``) is untouched. These cards are display-only — grading a
scorer needs a player-level results feed the free match-score source doesn't provide.
"""
from __future__ import annotations

import logging
import statistics
from typing import Dict, List, Optional, Tuple

from sports.nba.live_odds import _get_key
from sports.soccer.teams import COMPETITIONS, canonical_team
from utils.odds_math import american_to_implied_prob, devig_two_way_american

logger = logging.getLogger(__name__)

_BASE = "https://api.the-odds-api.com/v4/sports/{sk}"
_MARKET = "player_goal_scorer_anytime"
# Region where each competition's scorer props are quoted (keeps it to 1 credit/event).
_REGION = {"epl": "uk", "ucl": "uk", "mls": "us"}


def parse_goalscorer_event(event_odds: dict, top_k: int = 3) -> List[Tuple[str, float]]:
    """Pure: top-K ``(player, prob)`` from one event-odds payload, ranked by the
    market-implied probability (median across books). De-vigs the Yes/No pair when a
    book supplies both; anytime-goalscorer is usually Yes-only, so otherwise it's the
    raw Yes implied prob (a market-implied number that carries the book margin)."""
    yes: Dict[str, List[float]] = {}
    no: Dict[str, List[float]] = {}
    for bk in event_odds.get("bookmakers", []) or []:
        for mk in bk.get("markets", []) or []:
            if mk.get("key") != _MARKET:
                continue
            for o in mk.get("outcomes", []) or []:
                player = (o.get("description") or "").strip()
                price = o.get("price")
                if not player or price is None:
                    continue
                side = yes if str(o.get("name", "")).lower() == "yes" else no
                side.setdefault(player, []).append(float(price))

    out: List[Tuple[str, float]] = []
    for player, prices in yes.items():
        y = statistics.median(prices)
        if player in no:
            prob, _ = devig_two_way_american(y, statistics.median(no[player]))
        else:
            prob = american_to_implied_prob(y)
        out.append((player, float(prob)))
    out.sort(key=lambda t: t[1], reverse=True)
    return out[:top_k]


def fetch_anytime_goalscorer(competitions: Optional[List[str]] = None, max_events: int = 3,
                             top_k: int = 2, api_key: Optional[str] = None,
                             timeout: int = 25) -> List[dict]:
    """Top market-implied scorers for up to ``max_events`` soonest upcoming matches
    across the given competitions. STRICTLY caps per-event odds calls at ``max_events``
    (each ~1 credit). Soft-fails to [] (no key / network / plan / off-season)."""
    key = _get_key(api_key)
    if not key:
        return []
    import requests

    out: List[dict] = []
    calls = 0
    for comp in (competitions or ["epl", "mls", "ucl"]):
        if calls >= max_events:
            break
        sk = COMPETITIONS.get(comp)
        if not sk:
            continue
        try:
            evs = requests.get(_BASE.format(sk=sk) + "/events", params={"apiKey": key}, timeout=timeout)
            events = evs.json() if evs.ok else []          # /events is free (no quota)
        except Exception as e:
            logger.warning("goalscorer events fetch failed for %s: %s", comp, e)
            continue
        for e in events:
            if calls >= max_events:
                break
            calls += 1                                     # one paid per-event odds call
            try:
                od = requests.get(
                    _BASE.format(sk=sk) + f"/events/{e['id']}/odds",
                    params={"apiKey": key, "regions": _REGION.get(comp, "uk"),
                            "oddsFormat": "american", "markets": _MARKET}, timeout=timeout)
                scorers = parse_goalscorer_event(od.json(), top_k=top_k) if od.ok else []
            except Exception as e2:
                logger.warning("goalscorer odds fetch failed for %s: %s", comp, e2)
                continue
            if scorers:
                out.append({
                    "home": canonical_team(e.get("home_team", ""), strict=False),
                    "away": canonical_team(e.get("away_team", ""), strict=False),
                    "date": str(e.get("commence_time", ""))[:10],
                    "competition": comp, "scorers": scorers,
                })
    logger.info("anytime-goalscorer: %d matches (%d odds calls)", len(out), calls)
    return out
