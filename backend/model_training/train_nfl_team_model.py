#!/usr/bin/env python3
"""Train the NFL team score model (margin & total) with the shared honest
walk-forward trainer + a robust MAE-based sigma — identical methodology to NBA,
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
from sports.nfl.team_features import (MARGIN_ANCHOR, RESIDUAL_FEATURE_COLS, TOTAL_ANCHOR,
                                      build_team_game_frame)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

NFL_TEAM_MODEL_DIR = ARTIFACTS_DIR / "nfl_team"
NFL_TEAM_BLIND_DIR = ARTIFACTS_DIR / "nfl_team_blind"  # market-blind (absolute target)
NFL_LGBM_PARAMS = dict(
    n_estimators=1200, learning_rate=0.02, num_leaves=15,
    max_depth=-1, min_child_samples=40, subsample=0.9, colsample_bytree=0.9,
)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=2010)
    ap.add_argument("--end", type=int, default=2024)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--blind", action="store_true",
                    help="Train a MARKET-BLIND model on the absolute margin/total (no "
                         "market anchor) -> models/artifacts/nfl_team_blind/.")
    args = ap.parse_args()
    out = args.out or (NFL_TEAM_BLIND_DIR if args.blind else NFL_TEAM_MODEL_DIR)
    out.mkdir(parents=True, exist_ok=True)

    frame = build_team_game_frame(range(args.start, args.end + 1))
    logger.info("NFL team frame: %d games (%d-%d)%s", len(frame), args.start, args.end,
                " [market-blind]" if args.blind else "")

    X = frame[RESIDUAL_FEATURE_COLS]  # excludes MARKET_SPREAD/MARKET_TOTAL in both modes
    seasons = frame["season"].astype(str)
    dates = frame["game_date"]

    # Blind: learn the ABSOLUTE margin/total from team features only (no line).
    # Anchored: learn only the residual off the market line (~66% SU ceiling; kept
    # for opt-in ROI settlement). RESIDUAL_FEATURE_COLS is market-free either way.
    metrics = {}
    for target, col, anchor in (("margin", "y_margin", MARGIN_ANCHOR),
                                ("total", "y_total", TOTAL_ANCHOR)):
        y = frame[col] if args.blind else (frame[col] - frame[anchor])
        anchor_col = None if args.blind else anchor
        model, m = walk_forward_train(X, y, seasons, dates=dates, params=NFL_LGBM_PARAMS)
        ho = m.get("holdout_mae")
        sigma = float(1.2533 * ho if ho else (m.get("holdout_resid_std") or np.std(y)))
        joblib.dump(
            {"model": model, "target": target, "sigma": sigma, "anchor_col": anchor_col,
             "feature_cols": RESIDUAL_FEATURE_COLS, "metrics": m},
            out / f"team_{target}.joblib",
        )
        metrics[target] = {
            "cv_mae": m.get("cv_mae"), "holdout_mae": ho, "holdout_season": m.get("holdout_season"),
            "best_iteration": m.get("best_iteration"), "sigma": sigma,
            "anchor": anchor_col, "market_blind": bool(args.blind),
        }
        logger.info("nfl %s: holdout_mae=%.3f sigma=%.3f (holdout %s)%s",
                    target, ho if ho else -1, sigma, m.get("holdout_season"),
                    " [blind]" if args.blind else "")

    with open(out / "nfl_team_training_metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
    logger.info("Done. NFL team artifacts in %s", out)


if __name__ == "__main__":
    main()
