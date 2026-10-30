#!/usr/bin/env python3
"""Train the MLB starting-pitcher strikeout-prop model (the #1 MLB prop).

Same v2 methodology as the other sports' player props: anchored (predict
K - K_L5, add back) and usage-gated (>= MIN_PRIOR_STARTS of history), via the
shared honest walk-forward trainer. Reports skill vs the recent-average baseline.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from config.paths import ARTIFACTS_DIR
from model_training.validation import walk_forward_train
from sports.mlb.pitcher_features import (ANCHOR_COL, FEATURE_COLS, MIN_PRIOR_STARTS,
                                         build_pitcher_frame)

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

MLB_PITCHER_DIR = ARTIFACTS_DIR / "mlb_pitcher"
PARAMS = dict(n_estimators=700, learning_rate=0.03, num_leaves=31,
              min_child_samples=40, subsample=0.9, colsample_bytree=0.9, reg_lambda=1.0)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=2022)
    ap.add_argument("--end", type=int, default=2025)
    ap.add_argument("--out", type=Path, default=MLB_PITCHER_DIR)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    frame = build_pitcher_frame(range(args.start, args.end + 1))
    if frame.empty or "_n_prior" not in frame.columns:
        logger.warning("MLB pitcher frame empty (no data fetched %d-%d) - skipping training.",
                       args.start, args.end)
        return
    frame = frame[frame["_n_prior"] >= MIN_PRIOR_STARTS].reset_index(drop=True)
    logger.info("MLB pitcher frame: %d gated starts (%d-%d)", len(frame), args.start, args.end)

    anchor = pd.to_numeric(frame[ANCHOR_COL], errors="coerce").fillna(0.0)
    y_adj = pd.to_numeric(frame["K"], errors="coerce").fillna(0.0) - anchor
    X = frame[FEATURE_COLS].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    model, m = walk_forward_train(X, y_adj, frame["season"].astype(str),
                                  dates=frame["date"], params=PARAMS)

    ho = frame["season"].astype(str) == str(m.get("holdout_season"))
    baseline = float(y_adj[ho].abs().mean())            # predict K_L5 (adj 0)
    skill = (1.0 - m["holdout_mae"] / baseline) * 100.0 if baseline else 0.0

    joblib.dump({"model": model, "target": "K", "anchor_col": ANCHOR_COL,
                 "feature_cols": FEATURE_COLS, "metrics": m},
                args.out / "pitcher_K.joblib")
    with open(args.out / "mlb_pitcher_metrics.json", "w") as f:
        json.dump({"n": int(len(frame)), "holdout_mae": m["holdout_mae"], "cv_mae": m.get("cv_mae"),
                   "baseline_l5": baseline, "skill_pct": round(skill, 2),
                   "best_iteration": m.get("best_iteration"), "holdout_season": m.get("holdout_season")}, f, indent=2)
    logger.info("K: holdout_mae=%.3f cv_mae=%s best_it=%s | baseline(K_L5)=%.3f | skill=%.1f%%",
                m["holdout_mae"], f"{m.get('cv_mae'):.3f}" if m.get("cv_mae") else "n/a",
                m.get("best_iteration"), baseline, skill)
    logger.info("Done. MLB pitcher artifacts in %s", args.out)


if __name__ == "__main__":
    main()
