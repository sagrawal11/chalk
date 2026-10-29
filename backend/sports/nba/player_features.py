"""Clean, curated NBA player-prop feature engine (v3).

Replaces the degenerate global_lgbm path (336-column kitchen-sink that
collapsed to 1-9 trees => projection == L10 average). Diagnosis: game-level
player stats are dominated by irreducible variance; the only real signal beyond
recent form is MINUTES, driven by teammate availability. So features here are a
FOCUSED set: recent-form windows + per-minute rate + teammate-availability +
light context, proven to train non-degenerately and beat the L10 baseline
(backtest/player_signal_probe.py: PTS +0.9% recent-form, +1.5% with availability).

Leakage-safe: every rolling feature is shift(1) (prior games only); teammate
availability is same-day roster info (known before tip); each stat is modeled as
an ADJUSTMENT to its L10 anchor (holdout_mae on the adjustment == level MAE).
"""
from __future__ import annotations

import unicodedata
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

from config.paths import PLAYER_DATA_DIR, TEAM_AVAILABILITY_PARQUET
from sports.nba.teams import canonical_team
from utils.names import player_slug


def player_key(name: str) -> str:
    """Canonical inference key: ASCII-fold accents BEFORE slugging so "Nikola
    Jokić" and "Nikola Jokic" collapse to the same key (player_slug drops the
    accented char outright, e.g. -> 'nikola_joki', which never matches 'jokic')."""
    ascii_name = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode()
    return player_slug(ascii_name)

TARGET_STATS: List[str] = ["PTS", "OREB", "DREB", "AST", "FTM", "FG3M", "FGM", "STL", "BLK", "TOV"]
MIN_WINDOWS = [3, 5, 10, 20]
ROTATION_MIN_L10 = 8.0
AVAIL_COLS = ["TM_OUT_MIN", "TM_OUT_PTS", "TM_OUT_COUNT", "TM_TOP_OUT"]
CTX_COLS = ["IS_HOME", "DAYS_REST", "IS_B2B"]


def features_for(target: str) -> List[str]:
    """Curated, per-stat feature set (~15 cols), focused enough to avoid the
    kitchen-sink degeneracy, rich enough to carry the minutes/availability signal."""
    return (
        [f"MIN_L{w}" for w in MIN_WINDOWS]
        + [f"{target}_L{w}" for w in (3, 5, 10)]
        + [f"{target}_rate_L10"]
        + CTX_COLS + AVAIL_COLS
    )


def _roll(s: pd.Series, w: int) -> pd.Series:
    return s.shift(1).rolling(w, min_periods=max(2, w // 3)).mean()


def _load_availability() -> pd.DataFrame:
    if not TEAM_AVAILABILITY_PARQUET.exists():
        return pd.DataFrame(columns=["team", "game_date"] + AVAIL_COLS)
    av = pd.read_parquet(TEAM_AVAILABILITY_PARQUET)
    av["game_date"] = pd.to_datetime(av["game_date"]).dt.normalize()
    return av[["team", "game_date"] + AVAIL_COLS]


def build_player_frame(player_data_dir=PLAYER_DATA_DIR, max_players=None) -> pd.DataFrame:
    av = _load_availability()
    dirs = sorted(p for p in Path(player_data_dir).iterdir() if p.is_dir())
    if max_players:
        dirs = dirs[:max_players]
    frames = []
    for d in dirs:
        csv = d / f"{d.name}_data.csv"
        if not csv.exists():
            continue
        try:
            df = pd.read_csv(csv, usecols=lambda c: c in (
                {"GAME_DATE", "SEASON", "PLAYER_TEAM", "IS_HOME", "MIN"} | set(TARGET_STATS)))
        except Exception:
            continue
        if "MIN" not in df.columns or "GAME_DATE" not in df.columns:
            continue
        df["MIN"] = pd.to_numeric(df["MIN"], errors="coerce")
        df = df.dropna(subset=["MIN"])
        df = df[df["MIN"] > 0]
        if len(df) < 20:
            continue
        df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"], errors="coerce")
        df = df.dropna(subset=["GAME_DATE"]).sort_values("GAME_DATE").reset_index(drop=True)
        for t in TARGET_STATS:
            if t not in df.columns:
                df[t] = 0.0
            df[t] = pd.to_numeric(df[t], errors="coerce").fillna(0.0)
        # recent-form rolls (prior-only)
        for w in MIN_WINDOWS:
            df[f"MIN_L{w}"] = _roll(df["MIN"], w)
        for t in TARGET_STATS:
            for w in (3, 5, 10):
                df[f"{t}_L{w}"] = _roll(df[t], w)
            num = df[t].shift(1).rolling(10, min_periods=3).sum()
            den = df["MIN"].shift(1).rolling(10, min_periods=3).sum()
            df[f"{t}_rate_L10"] = (num / den).replace([np.inf, -np.inf], np.nan)
        # context
        df["IS_HOME"] = pd.to_numeric(df.get("IS_HOME"), errors="coerce").fillna(0).astype(int)
        rest = df["GAME_DATE"].diff().dt.days
        df["DAYS_REST"] = rest.fillna(3).clip(0, 10)
        df["IS_B2B"] = (rest <= 1).fillna(False).astype(int)
        df["slug"] = player_key(d.name.replace("_", " "))
        df["team"] = df["PLAYER_TEAM"].map(lambda x: canonical_team(x, strict=False)) if "PLAYER_TEAM" in df.columns else ""
        frames.append(df)
    if not frames:
        raise RuntimeError("no player logs found")
    allp = pd.concat(frames, ignore_index=True)
    allp["game_date"] = allp["GAME_DATE"].dt.normalize()
    allp = allp.merge(av, on=["team", "game_date"], how="left")
    for c in AVAIL_COLS:
        allp[c] = pd.to_numeric(allp.get(c), errors="coerce").fillna(0.0)
    return allp


def _tail_mean(s: pd.Series, w: int) -> float:
    """Rolling-mean value the training column would carry for the NEXT (unplayed)
    game: the mean of the last ``w`` ACTUAL games, honoring the same min_periods
    the training roll uses (``max(2, w//3)``). Returns 0.0 when under the gate."""
    tail = s.tail(w)
    return float(tail.mean()) if len(tail) >= max(2, w // 3) else 0.0


def latest_player_features(frame: pd.DataFrame) -> Dict[str, Dict]:
    """Each player's feature vector + per-stat anchor for their NEXT game: the
    true next-game rolling, computed over their most recent N ACTUAL games (NOT
    the last row's shift(1) columns, which are the rolls ENTERING that last game
    and so are stale by one game). Mirrors the training rolls (same windows +
    min_periods) but evaluated at "now", matching the MLB pitcher pattern.
    Non-rolling context (IS_HOME/DAYS_REST/IS_B2B) carries the last game's value
    (next-game schedule context is unknown here); availability is set by the
    caller. Keyed by slug (for name-based inference), shape unchanged."""
    out: Dict[str, Dict] = {}
    all_feats = sorted({c for t in TARGET_STATS for c in features_for(t)})
    for slug, pdf in frame.sort_values("GAME_DATE").groupby("slug"):
        p = pdf.sort_values("GAME_DATE")
        last = p.iloc[-1]
        f: Dict[str, float] = {}
        # recent-form rolls over the last N ACTUAL games (true next-game roll)
        for w in MIN_WINDOWS:
            f[f"MIN_L{w}"] = _tail_mean(p["MIN"], w)
        for t in TARGET_STATS:
            for w in (3, 5, 10):
                f[f"{t}_L{w}"] = _tail_mean(p[t], w)
            den = float(p["MIN"].tail(10).sum())
            f[f"{t}_rate_L10"] = (
                float(p[t].tail(10).sum() / den) if den and len(p) >= 3 else 0.0
            )
        # non-rolling context: last-known (not part of the off-by-one rolling bug)
        for c in CTX_COLS:
            f[c] = float(last.get(c, 0.0)) if pd.notna(last.get(c)) else 0.0
        # availability defaults to 0 (full roster); caller overrides at inference
        for c in AVAIL_COLS:
            f[c] = float(last.get(c, 0.0)) if pd.notna(last.get(c)) else 0.0
        out[slug] = {
            "feats": {c: f.get(c, 0.0) for c in all_feats},
            "anchors": {t: f[f"{t}_L10"] for t in TARGET_STATS},
            "min_l10": f["MIN_L10"],
        }
    return out
