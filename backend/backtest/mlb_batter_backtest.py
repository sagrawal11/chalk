#!/usr/bin/env python3
"""Honest reliability check for the MLB batter hitting-prop models.

Same question as the other player-prop backtests: on the untouched holdout season,
does each anchored LightGBM model beat the naive baselines a fan uses for free -
the batter's trailing-5 and trailing-10 game averages?

The trainer reserves the max season as an untouched holdout; its stored
``holdout_mae`` was measured by an eval-model that never saw it (the shipped model
refits on ALL seasons, so re-predicting would be in-sample). We compare that honest
MAE to the L5/L10 baselines on the SAME usage-gated holdout rows. Skill = 1 -
model/last-5; positive means the ML adjustment earns its place. Home runs are
near-irreducible per game (mostly 0), so ~0 skill there is expected and honest.
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

from config.paths import ARTIFACTS_DIR
from sports.mlb.batter_features import (ANCHOR_COLS, MIN_PRIOR_GAMES, PROP_TARGETS,
                                        build_batter_frame)

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

MLB_BATTER_DIR = ARTIFACTS_DIR / "mlb_batter"
# last-10 column per prop (FEATURE_COLS uses TB_/HR_ not the raw target name)
_L10 = {"hits": "hits_L10", "totalBases": "TB_L10", "homeRuns": "HR_L10"}


def _mae(a, b) -> float:
    return float((pd.to_numeric(a, errors="coerce") - pd.to_numeric(b, errors="coerce")).abs().mean())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=2022)
    ap.add_argument("--end", type=int, default=2025)
    ap.add_argument("--model-dir", type=Path, default=MLB_BATTER_DIR)
    args = ap.parse_args()

    frame = build_batter_frame(range(args.start, args.end + 1))
    frame = frame[pd.to_numeric(frame["_n_prior"], errors="coerce").fillna(0) >= MIN_PRIOR_GAMES]
    holdout = str(frame["season"].astype(str).max())
    hold = frame[frame["season"].astype(str) == holdout]
    logger.info("MLB batter backtest - holdout season %s (%d gated batter-games, %d in holdout)\n",
                holdout, len(frame), len(hold))

    metrics = json.load(open(args.model_dir / "mlb_batter_metrics.json"))["targets"]
    hdr = f"{'prop':<12}{'n_hold':>8}{'model':>9}{'last-5':>9}{'last-10':>10}{'skill vs L5':>13}"
    logger.info(hdr)
    logger.info("-" * len(hdr))
    for t in PROP_TARGETS:
        base_l5 = _mae(hold[t], hold[ANCHOR_COLS[t]])     # predict trailing-5 avg (the anchor)
        base_l10 = _mae(hold[t], hold[_L10[t]])           # predict trailing-10 avg
        if t not in metrics:
            # served naive (not modeled, e.g. homeRuns): the served value IS the last-5 anchor
            logger.info(f"{t:<12}{len(hold):>8}{'naive':>9}{base_l5:>9.3f}{base_l10:>10.3f}{'served naive':>13}")
            continue
        model_mae = float(metrics[t]["holdout_mae"])
        skill = (1.0 - model_mae / base_l5) * 100.0 if base_l5 else 0.0
        logger.info(f"{t:<12}{len(hold):>8}{model_mae:>9.3f}{base_l5:>9.3f}{base_l10:>10.3f}{skill:>12.1f}%")


if __name__ == "__main__":
    main()
