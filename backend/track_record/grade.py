"""Grade a locked slate against actual outcomes and append to the results ledger.

Team-market outcomes come from final scores (game_key -> {home_pts, away_pts});
prop outcomes from player actuals ((subject, stat) -> value). Units use a flat
1u stake at the realized price (projection-only lines assume -110 for display).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import pandas as pd

from config.paths import DATA_DIR
from track_record.lock import load_lock
from utils.odds_math import american_to_decimal

logger = logging.getLogger(__name__)
RESULTS_LEDGER = DATA_DIR / "predictions" / "results_ledger.parquet"


def _units(result: str, odds_american: Optional[int]) -> float:
    """Flat-1u P&L at the realized price. A pick with NO real price is ROI-INELIGIBLE
    (NaN): we never fabricate a -110 line, so ROI reflects only genuinely-priced picks
    while win/loss accuracy still counts every graded pick (the hero metric)."""
    if odds_american is None:
        return float("nan")
    if result == "push":
        return 0.0
    dec = american_to_decimal(odds_american)
    return round(dec - 1.0, 4) if result == "win" else -1.0


def grade_team_pick(pick: Dict[str, Any], home_pts: float, away_pts: float) -> str:
    mf, side, line = pick["market_family"], pick["side"], pick.get("line")
    margin_home = home_pts - away_pts
    total = home_pts + away_pts
    if mf == "moneyline":
        if margin_home == 0:            # tie / draw: neither side won outright
            return "loss"
        return "win" if ((side == "home") == (margin_home > 0)) else "loss"
    if mf == "spread":
        team_margin = margin_home if side == "home" else -margin_home
        v = team_margin + float(line)
        return "push" if v == 0 else ("win" if v > 0 else "loss")
    if mf in ("game_total", "team_total"):
        v = total - float(line)
        return "push" if v == 0 else ("win" if ((side == "over") == (v > 0)) else "loss")
    return "loss"


def grade_prop_pick(pick: Dict[str, Any], actual: float) -> str:
    line = float(pick["line"])
    if actual == line:
        return "push"
    return "win" if ((pick["side"] == "over") == (actual > line)) else "loss"


def grade_date(
    sport: str,
    game_date: str,
    team_outcomes: Dict[str, Dict[str, float]],
    prop_actuals: Optional[Dict[tuple, float]] = None,
) -> pd.DataFrame:
    doc = load_lock(sport, game_date)
    rows = []
    for pick in doc.get("picks", []):
        mf = pick["market_family"]
        if mf == "player_prop":
            actual = (prop_actuals or {}).get((pick["subject"], pick["stat"]))
            if actual is None:
                continue
            res = grade_prop_pick(pick, float(actual))
        else:
            o = team_outcomes.get(pick.get("game_key", ""))
            if not o:
                continue
            res = grade_team_pick(pick, float(o["home_pts"]), float(o["away_pts"]))
        rows.append({
            "sport": sport, "game_date": game_date, "market_family": mf,
            "subject": pick["subject"], "side": pick["side"], "line": pick.get("line"),
            "stat": pick.get("stat"), "odds_american": pick.get("odds_american"),
            "edge": pick.get("edge"), "result": res,
            "units": _units(res, pick.get("odds_american")),
        })
    return pd.DataFrame(rows)


def append_ledger(df: pd.DataFrame) -> int:
    if df is None or df.empty:
        return 0
    key = ["sport", "game_date", "market_family", "subject", "side", "line", "stat"]
    if RESULTS_LEDGER.exists():
        old = pd.read_parquet(RESULTS_LEDGER)
        n_old = len(old)
        combined = pd.concat([old, df], ignore_index=True)
    else:
        n_old = 0
        combined = df
    combined = combined.drop_duplicates(subset=key, keep="last")
    RESULTS_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    combined.to_parquet(RESULTS_LEDGER, index=False)
    return len(combined) - n_old
