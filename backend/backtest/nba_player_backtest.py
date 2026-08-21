#!/usr/bin/env python3
"""Honest reliability check for the NBA player-prop (v2 anchored) models.

Mirror of ``nfl_player_backtest``: on the untouched holdout season, does the
anchored LightGBM model beat the naive baseline a fan uses for free — predicting
the player's trailing-10-game average (the anchor)?

The model is trained to predict ``stat - stat_L10`` (an adjustment to recent
form), so its stored ``holdout_mae`` — measured by an eval-model that never saw
the holdout season — is a level-MAE. The "last-10" baseline predicts adjustment
zero, so its MAE is ``mean(|stat - stat_L10|)`` on the SAME rotation-filtered
holdout rows. Skill = 1 - model/baseline; positive means the ML layer's
adjustment beats leaving the recent average alone. Apples-to-apples because both
use the identical rotation filter (MIN_L10 >= 8) the trainer applied.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import pandas as pd

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from config.paths import GLOBAL_MODEL_DIR, PLAYER_DATA_DIR
from feature_engine import TARGET_STATS

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

ROTATION_MIN_L10 = 8.0  # must match train_hybrid.ROTATION_MIN_L10


def _load_holdout(player_dir: Path, holdout_season: str, cols: list) -> pd.DataFrame:
    frames, skipped = [], 0
    for d in sorted(player_dir.iterdir()):
        if not d.is_dir():
            continue
        pq = d / f"{d.name}_features.parquet"
        if not pq.exists():
            continue
        try:
            df = pd.read_parquet(pq, columns=cols)
        except Exception:
            skipped += 1
            continue
        df = df[df["SEASON"].astype(str) == holdout_season]
        if len(df):
            frames.append(df)
    if skipped:
        logger.info("(skipped %d parquets missing columns)", skipped)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-dir", type=Path, default=GLOBAL_MODEL_DIR)
    ap.add_argument("--player-data", type=Path, default=PLAYER_DATA_DIR)
    args = ap.parse_args()

    metrics = json.load(open(args.model_dir / "hybrid_training_metrics.json"))
    holdout = metrics[TARGET_STATS[0]].get("holdout_season")
    need = ["SEASON", "MIN_L10"] + list(TARGET_STATS) + [f"{t}_L10" for t in TARGET_STATS]

    logger.info("NBA player backtest — holdout season %s (scanning player parquets)...", holdout)
    full = _load_holdout(args.player_data, holdout, need)
    if full.empty:
        logger.error("No holdout rows loaded — check season string / parquet columns.")
        return
    rot = full[pd.to_numeric(full["MIN_L10"], errors="coerce").fillna(0.0) >= ROTATION_MIN_L10]
    logger.info("holdout rotation rows: %d\n", len(rot))

    hdr = f"{'stat':<8}{'n':>8}{'model':>9}{'last-10':>10}{'skill':>9}"
    logger.info(hdr)
    logger.info("-" * len(hdr))
    for t in TARGET_STATS:
        a = pd.to_numeric(rot[t], errors="coerce")
        anc = pd.to_numeric(rot[f"{t}_L10"], errors="coerce")
        base = float((a - anc).abs().mean())            # predict trailing-10 avg
        model = float(metrics[t]["holdout_mae"])         # trainer's honest OOS MAE
        skill = (1.0 - model / base) * 100.0 if base else 0.0
        logger.info(f"{t:<8}{len(rot):>8}{model:>9.3f}{base:>10.3f}{skill:>8.1f}%")


if __name__ == "__main__":
    main()
