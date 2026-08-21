#!/usr/bin/env python3
"""Reconstruct per-(team, game_date) teammate availability from all player logs.

For each team-game we compute how much of the team's *expected rotation* was OUT
— the single highest-signal driver of a player's usage bump when a star sits.

Leakage-safe: the "expected rotation" and each rotation player's baseline
minutes/points come from the team's PRIOR games only (a rolling window); whether
a rotation player is OUT of a given game is same-day roster info (known before
tip). Each team-game's result attaches to every player of that team in that game.

Emits: team, game_date, TM_OUT_MIN, TM_OUT_PTS, TM_OUT_COUNT, TM_TOP_OUT, and
TM_ROT_JSON (the expected rotation's baseline minutes, for skew-free inference
against tonight's known-out list).
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import deque
from pathlib import Path

import pandas as pd

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from config.paths import AUXILIARY_DIR, PLAYER_DATA_DIR, TEAM_AVAILABILITY_PARQUET
from sports.nba.teams import canonical_team
from utils.names import player_slug

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ROTATION_WINDOW = 3          # team-games used to define the "expected rotation"
MIN_ROTATION_MINUTES = 12.0  # a rotation player averages >= this in the window


def _load_all_logs(player_data_dir: Path) -> pd.DataFrame:
    frames = []
    for d in sorted(p for p in Path(player_data_dir).iterdir() if p.is_dir()):
        c = d / f"{d.name}_data.csv"
        if not c.exists():
            continue
        try:
            df = pd.read_csv(c, usecols=lambda x: x in ("GAME_DATE", "PLAYER_TEAM", "MIN", "PTS"))
        except Exception:
            continue
        if not {"GAME_DATE", "PLAYER_TEAM", "MIN"} <= set(df.columns):
            continue
        df["slug"] = player_slug(d.name.replace("_", " "))
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    allg = pd.concat(frames, ignore_index=True)
    allg["GAME_DATE"] = pd.to_datetime(allg["GAME_DATE"], errors="coerce")
    allg["team"] = allg["PLAYER_TEAM"].map(lambda t: canonical_team(t, strict=False))
    allg["MIN"] = pd.to_numeric(allg["MIN"], errors="coerce").fillna(0.0)
    allg["PTS"] = pd.to_numeric(allg.get("PTS"), errors="coerce").fillna(0.0)
    return allg.dropna(subset=["GAME_DATE"])


def build_team_availability(
    player_data_dir: Path = PLAYER_DATA_DIR, out_path: Path = TEAM_AVAILABILITY_PARQUET
) -> pd.DataFrame:
    allg = _load_all_logs(player_data_dir)
    if allg.empty:
        logger.warning("no player logs found; team availability not built")
        return pd.DataFrame()

    out_rows = []
    for team, tdf in allg.groupby("team"):
        by_date = {}
        for date, g in tdf.groupby("GAME_DATE"):
            roster = {r["slug"]: (float(r["MIN"]), float(r["PTS"]))
                      for _, r in g.iterrows() if r["MIN"] > 0}
            by_date[date] = roster

        window: deque = deque(maxlen=ROTATION_WINDOW)
        for date in sorted(by_date):
            today = by_date[date]
            agg = {}
            for r in window:
                for slug, (m, pp) in r.items():
                    a = agg.setdefault(slug, [0.0, 0.0, 0])
                    a[0] += m; a[1] += pp; a[2] += 1
            expected = {slug: (a[0] / a[2], a[1] / a[2])
                        for slug, a in agg.items() if (a[0] / a[2]) >= MIN_ROTATION_MINUTES}
            out = {slug: b for slug, b in expected.items() if slug not in today}
            top = max(expected, key=lambda s: expected[s][0]) if expected else None
            out_rows.append({
                "team": team, "game_date": date,
                "TM_OUT_MIN": round(sum(b[0] for b in out.values()), 2),
                "TM_OUT_PTS": round(sum(b[1] for b in out.values()), 2),
                "TM_OUT_COUNT": len(out),
                "TM_TOP_OUT": 1 if (top is not None and top in out) else 0,
                "TM_ROT_JSON": json.dumps({s: round(b[0], 2) for s, b in expected.items()}),
            })
            window.append(today)

    res = pd.DataFrame(out_rows)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    res.to_parquet(out_path, index=False)
    logger.info("team availability: %d team-games -> %s", len(res), out_path)
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--player-data", type=Path, default=PLAYER_DATA_DIR)
    ap.add_argument("--out", type=Path, default=TEAM_AVAILABILITY_PARQUET)
    args = ap.parse_args()
    build_team_availability(args.player_data, args.out)


if __name__ == "__main__":
    main()
