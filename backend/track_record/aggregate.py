"""Aggregate the graded ledger into the public record: win%, units, ROI, and the
current streak — sliceable by sport / market / time window. Feeds both the
track-record content card and the control-room dashboard.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd


def _agg(g: pd.DataFrame) -> pd.Series:
    wins = int((g["result"] == "win").sum())
    losses = int((g["result"] == "loss").sum())
    pushes = int((g["result"] == "push").sum())
    settled = wins + losses
    priced = g[g["units"].notna()]           # only genuinely-priced picks count for ROI
    roi_n = int(len(priced))
    units = float(priced["units"].sum())
    return pd.Series({
        "n": int(len(g)), "wins": wins, "losses": losses, "pushes": pushes,
        "win_pct": (wins / settled if settled else float("nan")),
        "units": round(units, 3),
        "roi_eligible_n": roi_n,
        "roi": (round(units / roi_n, 4) if roi_n else float("nan")),
    })


def summarize(ledger: pd.DataFrame, group_cols: Optional[List[str]] = None) -> pd.DataFrame:
    if ledger is None or ledger.empty:
        return pd.DataFrame()
    if group_cols:
        rows = []
        for key, g in ledger.groupby(group_cols, dropna=False):
            row = _agg(g).to_dict()
            key_tuple = key if isinstance(key, tuple) else (key,)
            row.update(dict(zip(group_cols, key_tuple)))
            rows.append(row)
        return pd.DataFrame(rows)
    return _agg(ledger).to_frame().T


def current_streak(ledger: pd.DataFrame) -> int:
    """+N win streak / -N loss streak over settled (non-push) picks, most-recent first."""
    s = ledger[ledger["result"].isin(["win", "loss"])].sort_values("game_date")
    streak = 0
    for r in reversed(s["result"].tolist()):
        if streak == 0:
            streak = 1 if r == "win" else -1
        elif streak > 0 and r == "win":
            streak += 1
        elif streak < 0 and r == "loss":
            streak -= 1
        else:
            break
    return streak


def headline(ledger: pd.DataFrame) -> Dict[str, Any]:
    """One-glance record for content ('22-8, 64% SU'). Winner accuracy is the hero and
    counts every graded pick; ROI (units) is computed ONLY over genuinely-priced picks
    (``roi_eligible_n``), so an all-unpriced market-blind ledger honestly reports 0u / 0
    eligible ('accruing') rather than a fabricated number."""
    if ledger is None or ledger.empty:
        return {"record": "0-0", "units": 0.0, "roi": 0.0, "roi_eligible_n": 0,
                "win_pct": None, "streak": 0, "n_picks": 0}
    wins = int((ledger["result"] == "win").sum())
    losses = int((ledger["result"] == "loss").sum())
    pushes = int((ledger["result"] == "push").sum())
    settled = wins + losses
    priced = ledger[ledger["units"].notna()]
    roi_n = int(len(priced))
    units = round(float(priced["units"].sum()), 2)
    return {
        "record": f"{wins}-{losses}" + (f"-{pushes}" if pushes else ""),
        "units": units,
        "roi": round(units / roi_n, 4) if roi_n else 0.0,
        "roi_eligible_n": roi_n,
        "win_pct": round(wins / settled, 4) if settled else None,
        "streak": current_streak(ledger),
        "n_picks": int(len(ledger)),
    }


def score_mae(ledger: pd.DataFrame) -> Optional[float]:
    """Mean absolute error of the predicted final scores, when the ledger carries
    per-pick score errors (seed/backtest rows write ``home_pts_err``/``away_pts_err``).
    Returns None when those columns are absent (e.g. odds-only rows)."""
    if ledger is None or ledger.empty:
        return None
    cols = [c for c in ("home_pts_err", "away_pts_err") if c in ledger.columns]
    if not cols:
        return None
    errs = pd.concat([ledger[c] for c in cols], ignore_index=True).dropna()
    return round(float(errs.abs().mean()), 3) if len(errs) else None
