"""Starting-pitcher strikeout-prop features (the #1 MLB prop).

Same v2 philosophy as the other sports' player props: leakage-safe prior-only
rolling (last-3/5/10 STARTS, shifted), and K is modeled as an ADJUSTMENT to the
pitcher's recent average (anchor = K_L5), so the level tracks form. Trained only
on starts where the pitcher has enough prior history (usage gate).
"""
from __future__ import annotations

from typing import Dict, List

import numpy as np
import pandas as pd

from sports.mlb.pitcher_data import build_pitcher_starts

FEATURE_COLS: List[str] = ["K_L3", "K_L5", "K_L10", "IP_L5", "BF_L5", "K_per_BF_L5"]
ANCHOR_COL = "K_L5"
MIN_PRIOR_STARTS = 3   # usage gate: need some history for a reliable projection


def add_pitcher_features(df: pd.DataFrame) -> pd.DataFrame:
    """Pure feature computation over a pitcher-starts frame (leakage-safe rolling);
    split out from the network fetch so it's unit-testable."""
    if df.empty:
        return df
    df = df.sort_values(["pitcher_id", "date"]).reset_index(drop=True)
    g = df.groupby("pitcher_id", sort=False)
    for w in (3, 5, 10):
        df[f"K_L{w}"] = g["K"].transform(lambda s: s.shift(1).rolling(w, min_periods=2).mean())
    df["IP_L5"] = g["IP"].transform(lambda s: s.shift(1).rolling(5, min_periods=2).mean())
    df["BF_L5"] = g["BF"].transform(lambda s: s.shift(1).rolling(5, min_periods=2).mean())
    kc = g["K"].transform(lambda s: s.shift(1).rolling(5, min_periods=2).sum())
    bc = g["BF"].transform(lambda s: s.shift(1).rolling(5, min_periods=2).sum())
    df["K_per_BF_L5"] = (kc / bc).replace([np.inf, -np.inf], np.nan)
    # prior-start count (usage gate, prior-only)
    df["_n_prior"] = g.cumcount()
    return df


def build_pitcher_frame(years) -> pd.DataFrame:
    return add_pitcher_features(build_pitcher_starts(years))


def latest_pitcher_features(frame: pd.DataFrame) -> Dict[int, Dict]:
    """Each pitcher's features for their NEXT start — rolling over their most
    recent ACTUAL starts (not the shift(1) training column, which would be stale
    by one start). Keyed by pitcher id for inference."""
    out: Dict[int, Dict] = {}
    for pid, pdf in frame.groupby("pitcher_id"):
        p = pdf.sort_values("date")
        f = {f"K_L{w}": float(p["K"].tail(w).mean()) for w in (3, 5, 10)}
        f["IP_L5"] = float(p["IP"].tail(5).mean())
        f["BF_L5"] = float(p["BF"].tail(5).mean())
        bc = float(p["BF"].tail(5).sum())
        f["K_per_BF_L5"] = float(p["K"].tail(5).sum() / bc) if bc else 0.0
        out[int(pid)] = {"feats": {c: f[c] for c in FEATURE_COLS}, "anchor": f["K_L5"], "n_prior": int(len(p))}
    return out
