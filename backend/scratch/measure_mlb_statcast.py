#!/usr/bin/env python3
"""Measure the LEAN Statcast prior: does prior-SEASON xwOBA lower the pitcher-K /
batter hits+TB models' honest holdout MAE?

Apples-to-apples: build the gated frame ONCE, then run the SAME honest
walk_forward_train twice per target - baseline FEATURE_COLS vs FEATURE_COLS +
['xwOBA_prior'] - on identical rows/target/seasons/dates. Compare holdout_mae on the
untouched final season (2025). Keep the feature only if it lowers holdout_mae without
a reproducibility caveat (retraining the baseline here must reproduce the served
number: pitcher K 1.841, batter hits 0.688, TB 1.319).

Run from backend/:  python -m scratch.measure_mlb_statcast --kind pitcher
                    python -m scratch.measure_mlb_statcast --kind batter
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from model_training.validation import walk_forward_train
from sports.mlb.statcast_data import NEUTRAL_XWOBA, add_prior_xwoba

logging.basicConfig(level=logging.WARNING, format="%(message)s")
logger = logging.getLogger("measure")
logger.setLevel(logging.INFO)

NEW = "xwOBA_prior"
# Mirror the served player-prop trainer params exactly (train_mlb_{pitcher,batter}_model).
PARAMS = dict(n_estimators=700, learning_rate=0.03, num_leaves=31,
              min_child_samples=40, subsample=0.9, colsample_bytree=0.9, reg_lambda=1.0)


def _train_mae(frame, feat_cols, target, anchor_col):
    anchor = pd.to_numeric(frame[anchor_col], errors="coerce").fillna(0.0)
    y_adj = pd.to_numeric(frame[target], errors="coerce").fillna(0.0) - anchor
    X = frame[feat_cols].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    _, m = walk_forward_train(X, y_adj, frame["season"].astype(str),
                              dates=frame["date"], params=PARAMS)
    return m["holdout_mae"], m.get("holdout_season"), len(X)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", choices=["pitcher", "batter"], required=True)
    ap.add_argument("--start", type=int, default=2022)
    ap.add_argument("--end", type=int, default=2025)
    args = ap.parse_args()
    years = range(args.start, args.end + 1)

    if args.kind == "pitcher":
        from sports.mlb.pitcher_features import (ANCHOR_COL, FEATURE_COLS,
                                                 MIN_PRIOR_STARTS, build_pitcher_frame)
        frame = build_pitcher_frame(years)
        frame = frame[frame["_n_prior"] >= MIN_PRIOR_STARTS].reset_index(drop=True)
        frame = add_prior_xwoba(frame, "pitcher", "pitcher_id")
        targets = [("K", ANCHOR_COL)]
        base_cols = list(FEATURE_COLS)
    else:
        from sports.mlb.batter_features import (ANCHOR_COLS, FEATURE_COLS, MIN_PRIOR_GAMES,
                                                MODELED_TARGETS, build_batter_frame)
        frame = build_batter_frame(years)
        frame = frame[frame["_n_prior"] >= MIN_PRIOR_GAMES].reset_index(drop=True)
        frame = add_prior_xwoba(frame, "batter", "batter_id")
        targets = [(t, ANCHOR_COLS[t]) for t in MODELED_TARGETS]
        base_cols = list(FEATURE_COLS)

    cov = float((frame[NEW] != NEUTRAL_XWOBA).mean()) * 100.0
    logger.info("MLB %s statcast prior - %d gated rows (%d-%d) | prior-xwOBA coverage %.1f%% "
                "(rest neutral %.3f)\n", args.kind, len(frame), args.start, args.end, cov, NEUTRAL_XWOBA)

    hdr = f"{'target':<12}{'holdout':>9}{'base_mae':>10}{'+xwOBA':>9}{'delta':>9}{'result':>9}"
    logger.info(hdr)
    logger.info("-" * len(hdr))
    for target, anchor_col in targets:
        base_mae, ho, n = _train_mae(frame, base_cols, target, anchor_col)
        new_mae, _, _ = _train_mae(frame, base_cols + [NEW], target, anchor_col)
        delta = new_mae - base_mae
        verdict = "KEEP" if delta < 0 else "drop"
        logger.info(f"{target:<12}{str(ho):>9}{base_mae:>10.4f}{new_mae:>9.4f}{delta:>+9.4f}{verdict:>9}")


if __name__ == "__main__":
    main()
