#!/usr/bin/env python3
"""Honest reliability check for the MLB starting-pitcher strikeout model.

Same question as the other player-prop backtests: on the untouched holdout season,
does the anchored LightGBM model beat the naive baselines a fan uses for free -
the pitcher's trailing-5 and trailing-10 start strikeout averages?

The trainer reserves the max season as an untouched holdout; its stored
``holdout_mae`` was measured by an eval-model that never saw it (the shipped model
refits on ALL seasons, so re-predicting the holdout would be in-sample and
optimistic). We compare that honest MAE to the L5/L10 baselines on the SAME
usage-gated holdout rows. Skill = 1 - model/last-5; positive means the ML
adjustment earns its place.
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
from sports.mlb.pitcher_features import MIN_PRIOR_STARTS, build_pitcher_frame

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

MLB_PITCHER_DIR = ARTIFACTS_DIR / "mlb_pitcher"


def _mae(a, b) -> float:
    return float((pd.to_numeric(a, errors="coerce") - pd.to_numeric(b, errors="coerce")).abs().mean())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=2022)
    ap.add_argument("--end", type=int, default=2025)
    ap.add_argument("--model-dir", type=Path, default=MLB_PITCHER_DIR)
    args = ap.parse_args()

    frame = build_pitcher_frame(range(args.start, args.end + 1))
    frame = frame[pd.to_numeric(frame["_n_prior"], errors="coerce").fillna(0) >= MIN_PRIOR_STARTS]
    holdout = str(frame["season"].astype(str).max())
    hold = frame[frame["season"].astype(str) == holdout]
    logger.info("MLB pitcher backtest - holdout season %s (%d gated starts, %d in holdout)\n",
                holdout, len(frame), len(hold))

    model_mae = float(json.load(open(args.model_dir / "mlb_pitcher_metrics.json"))["holdout_mae"])
    base_l5 = _mae(hold["K"], hold["K_L5"])            # predict trailing-5 avg (the anchor)
    base_l10 = _mae(hold["K"], hold["K_L10"])          # predict trailing-10 avg
    skill = (1.0 - model_mae / base_l5) * 100.0 if base_l5 else 0.0

    hdr = f"{'prop':<8}{'n_hold':>8}{'model':>9}{'last-5':>9}{'last-10':>10}{'skill vs L5':>13}"
    logger.info(hdr)
    logger.info("-" * len(hdr))
    logger.info(f"{'K':<8}{len(hold):>8}{model_mae:>9.3f}{base_l5:>9.3f}{base_l10:>10.3f}{skill:>12.1f}%")


if __name__ == "__main__":
    main()
