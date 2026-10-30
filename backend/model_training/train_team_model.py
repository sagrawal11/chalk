#!/usr/bin/env python3
"""Train the team score model: LightGBM for game **margin** (home-away) and
**total** (home+away), each paired with a holdout-fit residual sigma so it
becomes a calibrated normal. Win probability and predicted scores are derived
from these two normals at serve time (see models.team_predictor).

Uses the same honest walk-forward + untouched-holdout methodology as the player
trainer (model_training.validation).
"""
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

from config.paths import ARTIFACTS_DIR, KAGGLE_TEAM_GAMES_PARQUET
from model_training.validation import walk_forward_train
from sports.nba.team_features import TEAM_FEATURE_COLS, build_team_game_frame
from sports.nba.teams import season_int_to_str

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TEAM_MODEL_DIR = ARTIFACTS_DIR / "team"
TEAM_LGBM_PARAMS = dict(
    n_estimators=1500, learning_rate=0.02, num_leaves=31,
    max_depth=-1, min_child_samples=80, subsample=0.8, colsample_bytree=0.9,
)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=TEAM_MODEL_DIR)
    ap.add_argument("--parquet", type=Path, default=KAGGLE_TEAM_GAMES_PARQUET)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    frame = build_team_game_frame(args.parquet)
    logger.info(
        "Team game frame: %d games (seasons %s..%s)",
        len(frame), int(frame["season"].min()), int(frame["season"].max()),
    )

    X = frame[TEAM_FEATURE_COLS]
    seasons = frame["season"].map(season_int_to_str)
    dates = frame["game_date"]

    metrics = {}
    for target, col in (("margin", "y_margin"), ("total", "y_total")):
        model, m = walk_forward_train(X, frame[col], seasons, dates=dates, params=TEAM_LGBM_PARAMS)
        # Robust sigma from MAE (1.2533 = 1/E|Z| for a normal). The raw residual
        # std is inflated by heavy tails (OT/blowouts), which over-widens the
        # total interval (holdout total coverage_80 was 0.92 vs nominal 0.80).
        ho_mae = m.get("holdout_mae")
        sigma = float(1.2533 * ho_mae if ho_mae else (m.get("holdout_resid_std") or np.std(frame[col])))
        joblib.dump(
            {"model": model, "target": target, "sigma": sigma,
             "feature_cols": TEAM_FEATURE_COLS, "metrics": m},
            args.out / f"team_{target}.joblib",
        )
        metrics[target] = {
            "cv_mae": m.get("cv_mae"), "holdout_mae": m.get("holdout_mae"),
            "holdout_resid_std": m.get("holdout_resid_std"),
            "holdout_season": m.get("holdout_season"),
            "best_iteration": m.get("best_iteration"), "sigma": sigma,
        }
        logger.info(
            "team %s: holdout_mae=%.3f sigma=%.3f (holdout %s)",
            target, m.get("holdout_mae", float("nan")), sigma, m.get("holdout_season"),
        )

    with open(args.out / "team_training_metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
    logger.info("Done. Team artifacts in %s", args.out)


if __name__ == "__main__":
    main()
