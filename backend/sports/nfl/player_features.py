"""NFL player-prop features from nflverse weekly stats.

Same v2 philosophy as NBA: leakage-safe prior-only rolling (last-3 + season-to-
date, shifted), and each prop is modeled as an ADJUSTMENT to the player's recent
average (anchor = <stat>_L3) so the level tracks form. Each stat is trained only
on players who actually produce it (usage filter), the NFL analog of the NBA
rotation filter.
"""
from __future__ import annotations

from typing import Dict, List

import pandas as pd

from sports.nfl.data import load_weekly_player_stats
from utils.names import player_slug

# Box stats we roll into features.
STATS: List[str] = [
    "passing_yards", "passing_tds", "attempts", "completions",
    "carries", "rushing_yards", "rushing_tds",
    "targets", "receptions", "receiving_yards", "receiving_tds",
]
# Props we predict.
PROP_TARGETS: List[str] = ["passing_yards", "rushing_yards", "receiving_yards", "receptions"]
# Usage gate per prop: only train on players who actually produce that stat.
USAGE_GATE: Dict[str, tuple] = {
    "passing_yards": ("attempts_L3", 10.0),
    "rushing_yards": ("carries_L3", 3.0),
    "receiving_yards": ("targets_L3", 2.0),
    "receptions": ("targets_L3", 2.0),
}
_POS_ENC = {"QB": 0, "RB": 1, "WR": 2, "TE": 3}
FEATURE_COLS: List[str] = [f"{s}_L3" for s in STATS] + [f"{s}_STD" for s in STATS] + ["position_enc"]


def build_player_frame(years) -> pd.DataFrame:
    w = load_weekly_player_stats(list(years))
    if "season_type" in w.columns:
        w = w[w["season_type"] == "REG"]
    for s in STATS:
        if s not in w.columns:
            w[s] = 0.0
    w[STATS] = w[STATS].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    w = w.sort_values(["player_id", "season", "week"]).reset_index(drop=True)

    grp = w.groupby(["player_id", "season"], sort=False)
    for s in STATS:
        w[f"{s}_L3"] = grp[s].transform(lambda x: x.shift(1).rolling(3, min_periods=1).mean())
        w[f"{s}_STD"] = grp[s].transform(lambda x: x.shift(1).expanding().mean())
    w["position_enc"] = w["position"].map(_POS_ENC).fillna(4).astype(int) if "position" in w.columns else 4

    roll_cols = [f"{s}_L3" for s in STATS] + [f"{s}_STD" for s in STATS]
    w[roll_cols] = w[roll_cols].fillna(0.0)
    return w


def latest_player_features(frame: pd.DataFrame) -> Dict[str, Dict]:
    """Each player's feature vector + per-prop anchor for their NEXT game: the
    true next-game rolling, computed over their most recent ACTUAL games (NOT the
    last row's shift(1) columns, which are the rolls ENTERING that last game and
    so are stale by one game). Mirrors the training rolls (L3 = last-3 mean; STD =
    season-to-date expanding mean) but evaluated at "now"; scoped to the player's
    MOST RECENT season, since the training rolls reset per (player, season).
    Keyed by player slug (for name-based inference), shape unchanged."""
    out: Dict[str, Dict] = {}
    name_col = "player_display_name" if "player_display_name" in frame.columns else "player_name"
    for _, pdf in frame.sort_values(["season", "week"]).groupby("player_id"):
        p = pdf.sort_values(["season", "week"])
        last = p.iloc[-1]
        name = str(last.get(name_col, ""))
        if not name:
            continue
        # training rolls reset per season -> next-game roll uses this season only
        cur = p[p["season"] == last["season"]]
        feats: Dict[str, float] = {}
        for s in STATS:
            feats[f"{s}_L3"] = float(cur[s].tail(3).mean()) if len(cur) else 0.0
            feats[f"{s}_STD"] = float(cur[s].mean()) if len(cur) else 0.0  # season-to-date (expanding) mean
        feats["position_enc"] = float(last.get("position_enc", 4))
        out[player_slug(name)] = {
            "name": name,
            "team": str(last.get("recent_team", "")),
            "position": str(last.get("position", "")),
            "feats": {c: feats[c] for c in FEATURE_COLS},
            "anchors": {t: feats[f"{t}_L3"] for t in PROP_TARGETS},
        }
    return out
