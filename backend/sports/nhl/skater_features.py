"""NHL skater points/shots prop features (points = goals+assists; shots on goal).

Same v2 philosophy as the other sports' player props: leakage-safe prior-only
rolling (last-5/10 games, shifted), and each target is modeled as an ADJUSTMENT
to the skater's recent average (anchor = its _L5), so the level tracks form.
Trained only on games where the skater has enough prior history (usage gate).
"""
from __future__ import annotations

from typing import Dict, List

import numpy as np
import pandas as pd

from sports.nhl.skater_data import build_skater_games

# The props this track serves. Each is anchored on its own last-5 average.
PROP_TARGETS: List[str] = ["points", "shots"]
FEATURE_COLS: List[str] = ["points_L5", "points_L10", "shots_L5", "shots_L10", "toi_L5"]
ANCHOR_COLS: Dict[str, str] = {"points": "points_L5", "shots": "shots_L5"}
MIN_PRIOR_GAMES = 5   # usage gate: need some history for a reliable projection


def add_skater_features(df: pd.DataFrame) -> pd.DataFrame:
    """Pure feature computation over a skater game-log frame (leakage-safe
    rolling); split out from the network fetch so it's unit-testable."""
    if df.empty:
        return df
    df = df.sort_values(["player_id", "date"]).reset_index(drop=True)
    g = df.groupby("player_id", sort=False)
    for stat in ("points", "shots"):
        for w in (5, 10):
            df[f"{stat}_L{w}"] = g[stat].transform(
                lambda s: s.shift(1).rolling(w, min_periods=3).mean())
    df["toi_L5"] = g["toi"].transform(lambda s: s.shift(1).rolling(5, min_periods=3).mean())
    # prior-game count (usage gate, prior-only)
    df["_n_prior"] = g.cumcount()
    return df


def build_skater_frame(years) -> pd.DataFrame:
    return add_skater_features(build_skater_games(years))


def latest_skater_features(frame: pd.DataFrame) -> Dict[int, Dict]:
    """Each skater's features for their NEXT game — rolling over their most
    recent ACTUAL games (not the shift(1) training column, which would be stale
    by one game). Keyed by player id for inference; carries a per-target anchor.
    """
    out: Dict[int, Dict] = {}
    for pid, pdf in frame.groupby("player_id"):
        p = pdf.sort_values("date")
        f = {}
        for stat in ("points", "shots"):
            for w in (5, 10):
                f[f"{stat}_L{w}"] = float(p[stat].tail(w).mean())
        f["toi_L5"] = float(p["toi"].tail(5).mean())
        out[int(pid)] = {
            "feats": {c: f[c] for c in FEATURE_COLS},
            "anchors": {t: f[ANCHOR_COLS[t]] for t in PROP_TARGETS},
            "n_prior": int(len(p)),
            "team": _latest_str(p, "team"), "name": _latest_str(p, "name"),
        }
    return out


def _latest_str(p: pd.DataFrame, col: str) -> str:
    """Most recent non-null value of a passthrough label column (team/name), or ""
    when absent — older cached frames predate these columns."""
    if col not in p.columns or p.empty:
        return ""
    v = p[col].iloc[-1]
    return "" if pd.isna(v) else str(v)
