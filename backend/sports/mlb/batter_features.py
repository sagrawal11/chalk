"""Batter hitting-prop features (hits, total bases, home runs).

Same v2 philosophy as the other sports' player props: leakage-safe prior-only
rolling (last-5/10 GAMES, shifted), and each prop is modeled as an ADJUSTMENT to
the batter's recent average (anchor = <stat>_L5) so the level tracks form. Each
prop is trained only on batter-games with enough prior history (usage gate).

Home runs are extremely low-variance per game (most games = 0), so a rolling HR
*rate* is the useful signal; skill over the recent-average baseline is expected
to be small, reported honestly by the trainer.
"""
from __future__ import annotations

from typing import Dict, List

import numpy as np
import pandas as pd

from sports.mlb.batter_data import build_batter_games

# Props we predict (anchored on each one's own _L5).
PROP_TARGETS: List[str] = ["hits", "totalBases", "homeRuns"]
# Model features (all prior-only rolling): recent level of each prop + AB volume + HR rate.
FEATURE_COLS: List[str] = [
    "hits_L5", "hits_L10", "TB_L5", "TB_L10", "HR_L5", "HR_L10", "HR_rate_L10", "AB_L5",
]
# Per-prop anchor column (recent average the model adjusts around).
ANCHOR_COLS: Dict[str, str] = {"hits": "hits_L5", "totalBases": "TB_L5", "homeRuns": "HR_L5"}
MIN_PRIOR_GAMES = 10   # usage gate: need some history for a reliable projection


def add_batter_features(df: pd.DataFrame) -> pd.DataFrame:
    """Pure feature computation over a batter-games frame (leakage-safe rolling);
    split out from the network fetch so it's unit-testable."""
    if df.empty:
        return df
    df = df.sort_values(["batter_id", "date"]).reset_index(drop=True)
    g = df.groupby("batter_id", sort=False)
    for w in (5, 10):
        df[f"hits_L{w}"] = g["hits"].transform(lambda s: s.shift(1).rolling(w, min_periods=3).mean())
        df[f"TB_L{w}"] = g["totalBases"].transform(lambda s: s.shift(1).rolling(w, min_periods=3).mean())
        df[f"HR_L{w}"] = g["homeRuns"].transform(lambda s: s.shift(1).rolling(w, min_periods=3).mean())
    df["AB_L5"] = g["atBats"].transform(lambda s: s.shift(1).rolling(5, min_periods=3).mean())
    # HR rate over last-10: HR per AB (more stable than the per-game mean for a rare event).
    hr = g["homeRuns"].transform(lambda s: s.shift(1).rolling(10, min_periods=3).sum())
    ab = g["atBats"].transform(lambda s: s.shift(1).rolling(10, min_periods=3).sum())
    df["HR_rate_L10"] = (hr / ab).replace([np.inf, -np.inf], np.nan)
    # prior-game count (usage gate, prior-only)
    df["_n_prior"] = g.cumcount()
    return df


def build_batter_frame(years) -> pd.DataFrame:
    return add_batter_features(build_batter_games(years))


def latest_batter_features(frame: pd.DataFrame) -> Dict[int, Dict]:
    """Each batter's features for their NEXT game, rolling over their most recent
    ACTUAL games (not the shift(1) training column, which would be stale by one
    game). Keyed by batter id for inference; anchors carry a recent avg per prop."""
    out: Dict[int, Dict] = {}
    for pid, pdf in frame.groupby("batter_id"):
        p = pdf.sort_values("date")
        f = {}
        for w in (5, 10):
            f[f"hits_L{w}"] = float(p["hits"].tail(w).mean())
            f[f"TB_L{w}"] = float(p["totalBases"].tail(w).mean())
            f[f"HR_L{w}"] = float(p["homeRuns"].tail(w).mean())
        f["AB_L5"] = float(p["atBats"].tail(5).mean())
        ab10 = float(p["atBats"].tail(10).sum())
        f["HR_rate_L10"] = float(p["homeRuns"].tail(10).sum() / ab10) if ab10 else 0.0
        anchors = {t: f[ANCHOR_COLS[t]] for t in PROP_TARGETS}
        out[int(pid)] = {"feats": {c: f[c] for c in FEATURE_COLS}, "anchors": anchors,
                         "n_prior": int(len(p)),
                         "team": _latest_str(p, "team"), "name": _latest_str(p, "name")}
    return out


def _latest_str(p: pd.DataFrame, col: str) -> str:
    """Most recent non-null value of a passthrough label column (team/name), or ""
    when absent: older cached frames predate these columns."""
    if col not in p.columns or p.empty:
        return ""
    v = p[col].iloc[-1]
    return "" if pd.isna(v) else str(v)
