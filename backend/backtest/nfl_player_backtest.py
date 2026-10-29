#!/usr/bin/env python3
"""Honest reliability check for NFL player-prop models.

Player props have no abundant historical betting lines to grade against, so the
meaningful backtest is *projection skill*: on the untouched holdout season, does
the anchored LightGBM model beat the naive baselines a human would use for free?

  - baseline "last-3":    predict the player's trailing-3-game average (the anchor)
  - baseline "season avg": predict the player's season-to-date average

MAE is computed on the SAME usage-gated holdout rows the model reserved (the max
season, which walk_forward_train holds out), so model vs baseline is apples-to-
apples. Skill = 1 - model_mae / baseline_mae; positive means the ML layer earns
its place. Anchor cancels in the difference, so the model's stored holdout_mae is
already a level-MAE and directly comparable to these baselines.

IMPORTANT (honesty): the *shipped* model is refit on ALL seasons incl. the
holdout (validation.py:183, maximizes inference data), so re-predicting the
holdout with it would be in-sample and optimistic. We therefore report the
trainer's stored ``holdout_mae``, which was measured by a separate eval-model
that never saw the holdout season.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import joblib
import pandas as pd

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from config.paths import ARTIFACTS_DIR
from sports.nfl.player_features import PROP_TARGETS, USAGE_GATE, build_player_frame

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

NFL_PLAYER_MODEL_DIR = ARTIFACTS_DIR / "nfl_player"


def _mae(a: pd.Series, b: pd.Series) -> float:
    return float((pd.to_numeric(a, errors="coerce") - pd.to_numeric(b, errors="coerce")).abs().mean())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=2015)
    ap.add_argument("--end", type=int, default=2024)
    ap.add_argument("--model-dir", type=Path, default=NFL_PLAYER_MODEL_DIR)
    args = ap.parse_args()

    frame = build_player_frame(range(args.start, args.end + 1))
    holdout = str(frame["season"].astype(str).max())
    logger.info("NFL player backtest - holdout season %s (%d player-weeks total)\n", holdout, len(frame))

    hdr = f"{'prop':<16}{'n_hold':>8}{'model':>9}{'last-3':>9}{'seas-avg':>10}{'skill vs L3':>13}"
    logger.info(hdr)
    logger.info("-" * len(hdr))

    for t in PROP_TARGETS:
        gate_col, gate_val = USAGE_GATE[t]
        rel = frame[pd.to_numeric(frame[gate_col], errors="coerce").fillna(0.0) >= gate_val]
        hold = rel[rel["season"].astype(str) == holdout]
        if hold.empty:
            continue

        # naive baselines on the same holdout rows
        base_l3 = _mae(hold[t], hold[f"{t}_L3"])          # predict trailing-3 avg
        base_avg = _mae(hold[t], hold[f"{t}_STD"])        # predict season-to-date avg

        # model MAE: the trainer's honest OOS estimate (eval-model never saw the
        # holdout season). NOT a re-predict with the shipped model, which refits
        # on all seasons and would be in-sample here.
        blob = joblib.load(args.model_dir / f"player_{t}.joblib")
        model_mae = float(blob["metrics"]["holdout_mae"])

        skill = (1.0 - model_mae / base_l3) * 100.0 if base_l3 else 0.0
        logger.info(f"{t:<16}{len(hold):>8}{model_mae:>9.2f}{base_l3:>9.2f}{base_avg:>10.2f}{skill:>12.1f}%")


if __name__ == "__main__":
    main()
