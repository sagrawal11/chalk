"""Turn model probabilities + posted (de-vigged) lines into ranked value picks.

edge = model_prob - no_vig_fair_prob. A projection-only market (e.g. PrizePicks,
no two-way price) is treated as a fair 50/50 line, so a prop edge is
model P(over) - 0.5. This is honest "our edge%" for content, not a staking
engine (fractional Kelly EV is included only for display).
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from typing import Any, Callable, Dict, List, Optional

from config.settings import market_blind
from odds.schema import OddsLine
from predictions.schema import GamePrediction
from utils.odds_math import american_to_decimal, american_to_implied_prob, devig_two_way, expected_value

MIN_EDGE = 0.03


def confidence_tier(edge: float) -> str:
    if edge >= 0.10:
        return "high"
    if edge >= 0.05:
        return "medium"
    return "low"


def _fair(a_odds: Optional[int], b_odds: Optional[int]) -> tuple:
    """No-vig fair (a, b) probabilities. Projection-only markets (either price
    missing) fall back to a 50/50 fair line."""
    if a_odds is None or b_odds is None:
        return 0.5, 0.5
    return devig_two_way(american_to_implied_prob(a_odds), american_to_implied_prob(b_odds))


@dataclass
class Pick:
    sport: str
    game_date: str
    market_family: str
    subject: str
    side: str
    model_prob: float
    fair_prob: float
    edge: float
    confidence: str
    line: Optional[float] = None
    stat: Optional[str] = None
    odds_american: Optional[int] = None
    ev: Optional[float] = None            # per-unit EV (display only; None if no price)
    game_key: str = ""
    book: str = ""
    source: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _mk(ln: OddsLine, model_prob: float, fair_prob: float, sport: str, game_date: str) -> Pick:
    edge = float(model_prob - fair_prob)
    ev = None
    if ln.odds_american is not None:
        ev = expected_value(model_prob, american_to_decimal(ln.odds_american))
    return Pick(
        sport=sport, game_date=game_date, market_family=ln.market_family, subject=ln.subject,
        side=ln.side, model_prob=round(float(model_prob), 4), fair_prob=round(float(fair_prob), 4),
        edge=round(edge, 4), confidence=confidence_tier(edge), line=ln.line, stat=ln.stat,
        odds_american=ln.odds_american, ev=(round(ev, 4) if ev is not None else None),
        game_key=ln.game_key, book=ln.book, source=ln.source,
    )


def game_market_picks(gp: GamePrediction, lines: List[OddsLine], min_edge: float = MIN_EDGE) -> List[Pick]:
    """Value picks for a game's team markets (moneyline / spread / total)."""
    by: Dict[str, Dict[str, OddsLine]] = defaultdict(dict)
    for ln in lines:
        if ln.game_key and gp.game_key and ln.game_key != gp.game_key:
            continue
        by[ln.market_family][ln.side] = ln

    picks: List[Pick] = []

    ml = by.get("moneyline", {})
    if "home" in ml and "away" in ml:
        fh, fa = _fair(ml["home"].odds_american, ml["away"].odds_american)
        picks.append(_mk(ml["home"], gp.p_home_win, fh, gp.sport, gp.game_date))
        picks.append(_mk(ml["away"], 1.0 - gp.p_home_win, fa, gp.sport, gp.game_date))

    sp = by.get("spread", {})
    if "home" in sp and "away" in sp and sp["home"].line is not None:
        fh, fa = _fair(sp["home"].odds_american, sp["away"].odds_american)
        p_home_cover = gp.p_home_cover(sp["home"].line)
        picks.append(_mk(sp["home"], p_home_cover, fh, gp.sport, gp.game_date))
        picks.append(_mk(sp["away"], 1.0 - p_home_cover, fa, gp.sport, gp.game_date))

    gt = by.get("game_total", {})
    if "over" in gt and "under" in gt and gt["over"].line is not None:
        fo, fu = _fair(gt["over"].odds_american, gt["under"].odds_american)
        p_over = gp.p_total_over(gt["over"].line)
        picks.append(_mk(gt["over"], p_over, fo, gp.sport, gp.game_date))
        picks.append(_mk(gt["under"], 1.0 - p_over, fu, gp.sport, gp.game_date))

    return [p for p in picks if p.edge >= min_edge]


def prop_picks(
    lines: List[OddsLine],
    dist_lookup: Callable[[str, str], Optional[Any]],
    min_edge: float = MIN_EDGE,
) -> List[Pick]:
    """Value picks for player props. ``dist_lookup(subject, stat)`` returns a
    distribution head with ``.sf(line)`` (or None to skip)."""
    by: Dict[tuple, Dict[str, OddsLine]] = defaultdict(dict)
    for ln in lines:
        if ln.market_family == "player_prop":
            by[(ln.subject, ln.stat)][ln.side] = ln

    picks: List[Pick] = []
    for (subject, stat), sides in by.items():
        dist = dist_lookup(subject, stat)
        if dist is None:
            continue
        any_ln = sides.get("over") or sides.get("under")
        p_over = float(dist.sf(any_ln.line))
        o, u = sides.get("over"), sides.get("under")
        fo, fu = _fair(o.odds_american if o else None, u.odds_american if u else None)
        if o:
            picks.append(_mk(o, p_over, fo, o.sport, o.game_date))
        if u:
            picks.append(_mk(u, 1.0 - p_over, fu, u.sport, u.game_date))

    return [p for p in picks if p.edge >= min_edge]


def game_winner_picks(gp: GamePrediction) -> List[Pick]:
    """Market-blind "winner" pick: one moneyline Pick for the side the model favors,
    carrying its win probability + confidence. No line, no price — ``edge`` is the
    distance of the win prob from a 0.5 coin flip (honest "how sure the model is",
    not a market edge). 3-way sports (soccer) pick the more-likely of home/away and
    never a draw, so the pick stays gradeable as a moneyline. Always emits (every
    game gets a headline pick); ROI is settled later only if a real price is captured.
    """
    p_home = float(gp.p_home_win)
    p_away = float(gp.p_away_win) if gp.p_away_win is not None else 1.0 - p_home
    if p_home >= p_away:
        side, subject, model_prob = "home", gp.home, p_home
    else:
        side, subject, model_prob = "away", gp.away, p_away
    edge = round(model_prob - 0.5, 4)
    return [Pick(
        sport=gp.sport, game_date=gp.game_date, market_family="moneyline",
        subject=subject, side=side, model_prob=round(float(model_prob), 4),
        fair_prob=0.5, edge=edge, confidence=confidence_tier(edge),
        line=None, stat=None, odds_american=None, ev=None,
        game_key=gp.game_key, book="", source="model",
    )]


def select_best_bets(
    game_preds: List[GamePrediction],
    team_lines: List[OddsLine],
    prop_lines: List[OddsLine],
    dist_lookup: Callable[[str, str], Optional[Any]],
    min_edge: float = MIN_EDGE,
) -> List[Pick]:
    """All picks across a slate, ranked (best/most-confident first).

    Market-blind (brand default): one odds-free winner pick per game — the headline
    content unit. Otherwise the market-anchored value path (moneyline/spread/total vs
    de-vigged lines + player props), kept for opt-in ROI settlement.
    """
    if market_blind():
        picks = [p for gp in game_preds for p in game_winner_picks(gp)]
        picks.sort(key=lambda p: p.edge, reverse=True)
        return picks
    picks: List[Pick] = []
    for gp in game_preds:
        picks.extend(game_market_picks(gp, team_lines, min_edge))
    picks.extend(prop_picks(prop_lines, dist_lookup, min_edge))
    picks.sort(key=lambda p: p.edge, reverse=True)
    return picks
