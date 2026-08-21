"""Live game-market odds -> normalized OddsLine, so the automated daily pipeline
can generate (and next day grade) spread / total picks and auto-populate the
public track record.

Sources reuse what each sport already has for its market anchor, so no new feeds:
- NBA: The Odds API spreads+totals+moneyline (``sports.nba.live_odds.fetch_nba_lines``).
- NFL: the nflverse schedule's closing ``spread_line`` / ``total_line`` (free).

Spreads/totals are captured *projection-only* (no price): ``best_bet`` treats a
priceless line as a fair 50/50, the right approximation for near-pick'em
spreads/totals (a standard book prices both sides ~ -110). NBA moneyline lines DO
carry the real American price when a book quotes h2h — that price is not used to
change the (market-blind) prediction, only to SETTLE the model's winner pick at a
genuine closing number so ROI accrues forward honestly (see ``daily_content.run_day``).
MLB/NHL moneyline and soccer 1X2 are not wired here (unsupported sports return no
lines, so the daily loop degrades gracefully).

Both source values are "home-favored-positive"; ``OddsLine`` / ``GamePrediction``
use the standard home spread (negative == home favored), so the home line is the
NEGATED source value (see ``predictions.schema.GamePrediction.p_home_cover``).
"""
from __future__ import annotations

import logging
from typing import List

import pandas as pd

from odds.provider import OddsProvider
from odds.schema import OddsLine

logger = logging.getLogger(__name__)

_SUPPORTED = frozenset({"nba", "nfl"})


def _spread_total_lines(sport: str, date: str, home: str, away: str,
                        home_spread: float, total: float) -> List[OddsLine]:
    """Four priceless OddsLines for one game: spread (home/away) + total (over/under).
    ``home_spread`` is the STANDARD home spread (negative == home favored)."""
    def mk(fam: str, side: str, line: float, subj: str) -> OddsLine:
        return OddsLine(sport=sport, game_date=date, market_family=fam, subject=subj,
                        side=side, line=float(line), home=home, away=away,
                        source="live_market").validate()

    return [
        mk("spread", "home", home_spread, home),
        mk("spread", "away", -home_spread, away),
        mk("game_total", "over", total, "GAME"),
        mk("game_total", "under", total, "GAME"),
    ]


def _moneyline_lines(sport: str, date: str, home: str, away: str,
                     ml_home: int, ml_away: int) -> List[OddsLine]:
    """Two priced moneyline OddsLines for one game (home + away), line=None. These
    carry the real captured American price so a settled winner pick is ROI-eligible."""
    def mk(side: str, odds: int, subj: str) -> OddsLine:
        return OddsLine(sport=sport, game_date=date, market_family="moneyline", subject=subj,
                        side=side, line=None, odds_american=int(odds), home=home, away=away,
                        source="live_market").validate()

    return [mk("home", ml_home, home), mk("away", ml_away, away)]


def _nba_game_markets(game_date: str) -> List[OddsLine]:
    from sports.nba.live_odds import fetch_nba_lines

    date = str(game_date)[:10]
    out: List[OddsLine] = []
    for (home, away), ln in (fetch_nba_lines() or {}).items():
        # fetch_nba_lines "spread" is home-favored-positive -> standard = negated.
        out += _spread_total_lines("nba", date, home, away,
                                    -float(ln["spread"]), float(ln["total"]))
        # Moneyline is opportunistic: emit priced home/away lines only when h2h was
        # quoted, so the daily loop can settle the market-blind winner pick at a real
        # closing price (spread/total still emit even if moneyline is absent).
        if ln.get("moneyline_home") is not None and ln.get("moneyline_away") is not None:
            out += _moneyline_lines("nba", date, home, away,
                                    int(ln["moneyline_home"]), int(ln["moneyline_away"]))
    return out


def _nfl_game_markets(game_date: str) -> List[OddsLine]:
    from sports.base import get_sport
    from sports.nfl import data as nfl_data

    date = str(game_date)[:10]
    season = int(get_sport("nfl").season_from_date(date))
    s = nfl_data.load_schedules([season])
    s = s[s["game_date"].astype(str).str[:10] == date]
    out: List[OddsLine] = []
    for _, r in s.iterrows():
        sp, tot = r.get("spread_line"), r.get("total_line")
        if pd.isna(sp) or pd.isna(tot):
            continue
        # nflverse spread_line is home-relative (>0 == home favored) -> standard = negated.
        out += _spread_total_lines("nfl", date, r["home"], r["away"], -float(sp), float(tot))
    return out


class LiveMarketProvider(OddsProvider):
    """Spread + total lines for the sports whose anchor source exposes them (NBA/NFL),
    plus NBA closing moneyline (with a real price) for forward ROI settlement.
    Sport-agnostic entry: unsupported sports return []. Never raises — a down feed
    just yields no picks that day."""

    name = "live_market"
    markets = frozenset({"spread", "game_total", "moneyline"})

    def fetch_game_markets(self, sport: str, game_date: str) -> List[OddsLine]:
        if sport not in _SUPPORTED:
            return []
        try:
            return _nba_game_markets(game_date) if sport == "nba" else _nfl_game_markets(game_date)
        except Exception as e:  # a down/rate-limited feed must not break the daily loop
            logger.warning("live market odds unavailable for %s %s: %s", sport, game_date, e)
            return []
