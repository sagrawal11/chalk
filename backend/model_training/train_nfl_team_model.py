#!/usr/bin/env python3
"""Train the NFL team score model (margin & total) with the shared honest
walk-forward trainer + a robust MAE-based sigma, identical methodology to NBA,
proving the pipeline is sport-agnostic (only the feature engine differs)."""
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
from sports.nfl.team_features import TEAM_FEATURE_COLS, build_team_game_frame

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

NFL_TEAM_MODEL_DIR = ARTIFACTS_DIR / "nfl_team"
NFL_LGBM_PARAMS = dict(
    n_estimators=1200, learning_rate=0.02, num_leaves=15,
    max_depth=-1, min_child_samples=40, subsample=0.9, colsample_bytree=0.9,
)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=2010)
    ap.add_argument("--end", type=int, default=2024)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    out = args.out or NFL_TEAM_MODEL_DIR
    out.mkdir(parents=True, exist_ok=True)

    frame = build_team_game_frame(range(args.start, args.end + 1))
    logger.info("NFL team frame: %d games (%d-%d)", len(frame), args.start, args.end)

    X = frame[TEAM_FEATURE_COLS]
    seasons = frame["season"].astype(str)
    dates = frame["game_date"]

    # Learn the ABSOLUTE margin/total from team features only (no betting line).
    metrics = {}
    for target, col in (("margin", "y_margin"), ("total", "y_total")):
        y = frame[col]
        model, m = walk_forward_train(X, y, seasons, dates=dates, params=NFL_LGBM_PARAMS)
        ho = m.get("holdout_mae")
        sigma = float(1.2533 * ho if ho else (m.get("holdout_resid_std") or np.std(y)))
        joblib.dump(
            {"model": model, "target": target, "sigma": sigma,
             "feature_cols": TEAM_FEATURE_COLS, "metrics": m},
            out / f"team_{target}.joblib",
        )
        metrics[target] = {
            "cv_mae": m.get("cv_mae"), "holdout_mae": ho, "holdout_season": m.get("holdout_season"),
            "best_iteration": m.get("best_iteration"), "sigma": sigma,
        }
        logger.info("nfl %s: holdout_mae=%.3f sigma=%.3f (holdout %s)",
                    target, ho if ho else -1, sigma, m.get("holdout_season"))

    with open(out / "nfl_team_training_metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
    logger.info("Done. NFL team artifacts in %s", out)


if __name__ == "__main__":
    main()
