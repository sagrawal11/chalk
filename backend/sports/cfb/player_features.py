"""CFB player-prop features from CFBD box scores.

Same anchored, leakage-safe design as the NFL player model: prior-only rolling
(last-3 + season-to-date, both shifted) per (player, season), and each prop is
modeled as an ADJUSTMENT to the player's recent average (anchor = ``<stat>_L3``)
so the level tracks form. Each stat is trained only on players who actually
produce it (usage gate), the CFB analog of the NFL usage filter.

Two deliberate differences from NFL: ordering is by ``game_date`` (CFB postseason
week numbers restart, so the date is the unambiguous temporal key), and there is
NO position feature -- the CFBD box-score endpoint carries no position and the
usage gates already segment role (passer / rusher / receiver), so it is omitted
on purpose (curated, not kitchen-sink).
"""
from __future__ import annotations

from typing import Dict, List

import pandas as pd

from sports.cfb.data import PLAYER_STAT_COLS, load_player_games
from utils.names import player_slug

# Box stats we roll into features (the CFBD-available set; no targets).
STATS: List[str] = list(PLAYER_STAT_COLS)
# Props we predict.
PROP_TARGETS: List[str] = ["passing_yards", "rushing_yards", "receiving_yards", "receptions"]
# Usage gate per prop: only train on players who actually produce that stat.
# CFBD has no targets, so receptions is the receiving usage signal.
USAGE_GATE: Dict[str, tuple] = {
    "passing_yards": ("attempts_L3", 10.0),
    "rushing_yards": ("carries_L3", 3.0),
    "receiving_yards": ("receptions_L3", 2.0),
    "receptions": ("receptions_L3", 2.0),
}
FEATURE_COLS: List[str] = [f"{s}_L3" for s in STATS] + [f"{s}_STD" for s in STATS]


def build_player_frame(years) -> pd.DataFrame:
    w = load_player_games(list(years))
    if w.empty:
        return w
    for s in STATS:
        if s not in w.columns:
            w[s] = 0.0
    w[STATS] = w[STATS].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    w = w.sort_values(["player_id", "season", "game_date"]).reset_index(drop=True)

    grp = w.groupby(["player_id", "season"], sort=False)
    for s in STATS:
        w[f"{s}_L3"] = grp[s].transform(lambda x: x.shift(1).rolling(3, min_periods=1).mean())
        w[f"{s}_STD"] = grp[s].transform(lambda x: x.shift(1).expanding().mean())  # season-to-date

    roll_cols = [f"{s}_L3" for s in STATS] + [f"{s}_STD" for s in STATS]
    w[roll_cols] = w[roll_cols].fillna(0.0)
    return w


def latest_player_features(frame: pd.DataFrame) -> Dict[str, Dict]:
    """Each player's feature vector + per-prop anchor for their NEXT game: the
    true next-game rolling, computed over their most recent ACTUAL games (not the
    last row's shifted columns, which are stale by one game). Mirrors the training
    rolls (L3 = last-3 mean; STD = season-to-date expanding mean) evaluated at
    "now", scoped to the player's most recent season (training rolls reset per
    season). Keyed by player slug for name-based inference."""
    out: Dict[str, Dict] = {}
    if frame.empty:
        return out
    for _, pdf in frame.groupby("player_id"):
        p = pdf.sort_values(["season", "game_date"])
        last = p.iloc[-1]
        name = str(last.get("player_name", ""))
        if not name:
            continue
        cur = p[p["season"] == last["season"]]  # next-game roll uses this season only
        feats: Dict[str, float] = {}
        for s in STATS:
            feats[f"{s}_L3"] = float(cur[s].tail(3).mean()) if len(cur) else 0.0
            feats[f"{s}_STD"] = float(cur[s].mean()) if len(cur) else 0.0
        out[player_slug(name)] = {
            "name": name,
            "team": str(last.get("team", "")),
            "feats": {c: feats[c] for c in FEATURE_COLS},
            "anchors": {t: feats[f"{t}_L3"] for t in PROP_TARGETS},
        }
    return out
