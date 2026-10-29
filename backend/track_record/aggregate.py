"""Aggregate the graded ledger into the public record: straight-up win%, the current
streak, and predicted-score MAE, sliceable by sport / time window.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd


def score_mae(ledger: pd.DataFrame) -> Optional[float]:
    """Mean absolute error of the predicted final scores, from the per-side score-error
    columns (``home_pts_err``/``away_pts_err``). None when those columns are absent."""
    if ledger is None or ledger.empty:
        return None
    cols = [c for c in ("home_pts_err", "away_pts_err") if c in ledger.columns]
    if not cols:
        return None
    errs = pd.concat([ledger[c] for c in cols], ignore_index=True).dropna()
    return round(float(errs.abs().mean()), 3) if len(errs) else None


def _agg(g: pd.DataFrame) -> pd.Series:
    wins = int((g["result"] == "win").sum())
    losses = int((g["result"] == "loss").sum())
    settled = wins + losses
    return pd.Series({
        "n": int(len(g)), "wins": wins, "losses": losses,
        "win_pct": (wins / settled if settled else float("nan")),
        "score_mae": score_mae(g),
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
    """+N win streak / -N loss streak over graded games, most-recent first."""
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
    """One-glance record for content ('22-8, 64% SU') plus predicted-score MAE."""
    if ledger is None or ledger.empty:
        return {"record": "0-0", "win_pct": None, "streak": 0, "n": 0, "score_mae": None}
    wins = int((ledger["result"] == "win").sum())
    losses = int((ledger["result"] == "loss").sum())
    settled = wins + losses
    return {
        "record": f"{wins}-{losses}",
        "win_pct": round(wins / settled, 4) if settled else None,
        "streak": current_streak(ledger),
        "n": int(len(ledger)),
        "score_mae": score_mae(ledger),
    }
