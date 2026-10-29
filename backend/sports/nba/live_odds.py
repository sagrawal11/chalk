"""Live NBA closing lines from The Odds API (free tier), the up-to-date source
for anchoring UPCOMING-season predictions.

The Kaggle backfill covers 2007 -> Jan-2023; this fills the gap for today's and
future games so the model anchors on a fresh line (the ~68% SU ceiling) instead
of falling back to the team model. Needs a free key in the ``ODDS_API_KEY`` env
var (get one at the-odds-api.com; free tier = 500 requests/month, plenty for a
daily slate). Fails soft: no key / network error -> {} -> team-model fallback.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Callable, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


def _get_key(api_key: Optional[str] = None) -> Optional[str]:
    """ODDS_API_KEY from arg -> env -> repo .env (so it works under the Docker
    stack AND a direct CLI run, mirroring how KAGGLE_* is configured)."""
    key = api_key or os.environ.get("ODDS_API_KEY")
    if key:
        return key
    for up in (3, 2):  # backend/sports/nba/live_odds.py -> repo root / backend
        env = Path(__file__).resolve().parents[up] / ".env"
        if env.exists():
            for line in env.read_text().splitlines():
                if line.strip().startswith("ODDS_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'") or None
    return None

_ODDS_API_URL = "https://api.the-odds-api.com/v4/sports/basketball_nba/odds"

# The Odds API returns full team names; map to our canonical codes.
_NAME_TO_CODE = {
    "Atlanta Hawks": "ATL", "Boston Celtics": "BOS", "Brooklyn Nets": "BKN",
    "Charlotte Hornets": "CHA", "Chicago Bulls": "CHI", "Cleveland Cavaliers": "CLE",
    "Dallas Mavericks": "DAL", "Denver Nuggets": "DEN", "Detroit Pistons": "DET",
    "Golden State Warriors": "GSW", "Houston Rockets": "HOU", "Indiana Pacers": "IND",
    "Los Angeles Clippers": "LAC", "LA Clippers": "LAC", "Los Angeles Lakers": "LAL",
    "Memphis Grizzlies": "MEM", "Miami Heat": "MIA", "Milwaukee Bucks": "MIL",
    "Minnesota Timberwolves": "MIN", "New Orleans Pelicans": "NOP", "New York Knicks": "NYK",
    "Oklahoma City Thunder": "OKC", "Orlando Magic": "ORL", "Philadelphia 76ers": "PHI",
    "Phoenix Suns": "PHX", "Portland Trail Blazers": "POR", "Sacramento Kings": "SAC",
    "San Antonio Spurs": "SAS", "Toronto Raptors": "TOR", "Utah Jazz": "UTA",
    "Washington Wizards": "WAS",
}


def _to_code(name: Optional[str]) -> Optional[str]:
    if not name:
        return None
    if name in _NAME_TO_CODE:
        return _NAME_TO_CODE[name]
    low = name.lower()  # fall back to a nickname/city substring match
    for full, code in _NAME_TO_CODE.items():
        if full.lower() in low or low in full.lower():
            return code
    return None


def fetch_nba_lines(api_key: Optional[str] = None, regions: str = "us", timeout: int = 15
                    ) -> Dict[Tuple[str, str], Dict[str, float]]:
    """Current NBA spreads+totals (+moneyline) keyed by (home_code, away_code).

    Returns, per matchup, the home-favored-positive ``spread`` + game ``total`` from
    the first book quoting both, PLUS the home/away American ``moneyline_home`` /
    ``moneyline_away`` when a book quotes the ``h2h`` market. The moneyline keys are
    additive (absent if no book quotes h2h) so existing spread/total callers are
    unaffected. Moneyline is NOT used to change the (market-blind) prediction; it is
    the closing price we settle the winner pick at, so ROI accrues forward honestly.
    {} on missing key / network error / parse failure (caller falls back)."""
    key = _get_key(api_key)
    if not key:
        return {}
    try:
        import requests
        r = requests.get(_ODDS_API_URL, params={
            "apiKey": key, "regions": regions, "markets": "spreads,totals,h2h",
            "oddsFormat": "american"}, timeout=timeout)
        r.raise_for_status()
        events = r.json()
    except Exception as e:  # network / auth / rate-limit, degrade to team model
        logger.warning("The Odds API fetch failed: %s", e)
        return {}

    out: Dict[Tuple[str, str], Dict[str, float]] = {}
    for ev in events or []:
        home, away = _to_code(ev.get("home_team")), _to_code(ev.get("away_team"))
        if not home or not away:
            continue
        spread_home = total = ml_home = ml_away = None
        for bk in ev.get("bookmakers", []):
            for mk in bk.get("markets", []):
                if mk.get("key") == "spreads":
                    for oc in mk.get("outcomes", []):
                        if _to_code(oc.get("name")) == home and oc.get("point") is not None:
                            spread_home = -float(oc["point"])  # DK home -6 (favored) -> +6 home-favored
                elif mk.get("key") == "totals":
                    for oc in mk.get("outcomes", []):
                        if str(oc.get("name", "")).lower() == "over" and oc.get("point") is not None:
                            total = float(oc["point"])
                elif mk.get("key") == "h2h":  # moneyline (two-way: home + away)
                    for oc in mk.get("outcomes", []):
                        if oc.get("price") is None:
                            continue
                        code = _to_code(oc.get("name"))
                        if code == home and ml_home is None:
                            ml_home = int(oc["price"])
                        elif code == away and ml_away is None:
                            ml_away = int(oc["price"])
            # Stop once the first book has quoted every market we want (moneyline
            # is opportunistic, don't hold out the spread/total for a missing h2h).
            if spread_home is not None and total is not None and ml_home is not None and ml_away is not None:
                break
        if spread_home is not None and total is not None:
            game = {"spread": spread_home, "total": total}
            if ml_home is not None and ml_away is not None:
                game["moneyline_home"] = ml_home
                game["moneyline_away"] = ml_away
            out[(home, away)] = game
    logger.info("The Odds API: %d NBA games with lines", len(out))
    return out


def market_provider(api_key: Optional[str] = None) -> Callable[[str, str, str], Optional[Tuple[float, float]]]:
    """A cached (home, away, date) -> (home-favored spread, total) | None callable
    for TeamPredictor.market_provider. Fetches the slate once per process."""
    cache: Dict[str, Dict[Tuple[str, str], Dict[str, float]]] = {}

    def _lookup(home: str, away: str, game_date: str):
        if "lines" not in cache:
            cache["lines"] = fetch_nba_lines(api_key)
        line = cache["lines"].get((home, away))
        return (line["spread"], line["total"]) if line else None

    return _lookup
