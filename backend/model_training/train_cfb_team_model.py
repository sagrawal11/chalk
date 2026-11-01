#!/usr/bin/env python3
"""Train the CFB team score model (margin & total) with the shared honest
walk-forward trainer, identical methodology to NFL (only the feature engine +
data source differ). Needs CFBD_API_KEY (env or backend/.env)."""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import joblib
import numpy as np

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from config.paths import ARTIFACTS_DIR
from model_training.validation import walk_forward_train
from sports.cfb.team_features import TEAM_FEATURE_COLS, build_team_game_frame

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CFB_TEAM_MODEL_DIR = ARTIFACTS_DIR / "cfb_team"
CFB_LGBM_PARAMS = dict(
    n_estimators=1200, learning_rate=0.02, num_leaves=15,
    max_depth=-1, min_child_samples=40, subsample=0.9, colsample_bytree=0.9,
)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=2015)
    ap.add_argument("--end", type=int, default=2025)
    ap.add_argument("--out", type=Path, default=CFB_TEAM_MODEL_DIR)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    frame = build_team_game_frame(range(args.start, args.end + 1))
    logger.info("CFB team frame: %d games (%d-%d)", len(frame), args.start, args.end)

    X = frame[TEAM_FEATURE_COLS]
    seasons = frame["season"].astype(str)
    dates = frame["game_date"]

    metrics = {}
    for target, col in (("margin", "y_margin"), ("total", "y_total")):
        model, m = walk_forward_train(X, frame[col], seasons, dates=dates, params=CFB_LGBM_PARAMS)
        ho = m.get("holdout_mae")
        sigma = float(1.2533 * ho if ho else (m.get("holdout_resid_std") or np.std(frame[col])))
        joblib.dump({"model": model, "target": target, "sigma": sigma,
                     "feature_cols": TEAM_FEATURE_COLS, "metrics": m},
                    args.out / f"team_{target}.joblib")
        metrics[target] = {"cv_mae": m.get("cv_mae"), "holdout_mae": ho,
                           "holdout_season": m.get("holdout_season"), "sigma": sigma}
        logger.info("cfb %s: holdout_mae=%.3f sigma=%.3f (holdout %s)",
                    target, ho if ho else -1, sigma, m.get("holdout_season"))

    with open(args.out / "cfb_team_training_metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
    logger.info("Done. CFB team artifacts in %s", args.out)


if __name__ == "__main__":
    main()
