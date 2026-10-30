#!/usr/bin/env python3
"""Train the clean NBA player-prop models (v3), replacing the degenerate
global_lgbm path with a focused, curated feature set (recent-form windows +
per-minute rate + teammate availability + light context).

Per stat: rotation-gated (MIN_L10>=8), anchored (predict stat - stat_L10), honest
walk-forward holdout via the shared trainer (which now excludes stub seasons via
min_season_frac). Saved with feature_cols + anchor; the projection is the
predicted stat value (stat_L10 + adjustment).
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
from sports.nba.player_features import (ROTATION_MIN_L10, TARGET_STATS, build_player_frame,
                                        features_for)

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

NBA_PLAYER_V3_DIR = ARTIFACTS_DIR / "nba_player_v3"
# Curated feature set is small + clean, so we can afford full depth; early
# stopping resolves the tree count (non-degenerate on this feature set).
PARAMS = dict(n_estimators=2000, learning_rate=0.03, num_leaves=63,
              min_child_samples=100, subsample=0.8, colsample_bytree=0.8, reg_lambda=1.0)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=NBA_PLAYER_V3_DIR)
    ap.add_argument("--max-players", type=int, default=None)
    ap.add_argument("--max-cv-folds", type=int, default=4)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    frame = build_player_frame(max_players=args.max_players)
    logger.info("NBA player v3 frame: %d player-games", len(frame))
    rot = pd.to_numeric(frame["MIN_L10"], errors="coerce").fillna(0.0) >= ROTATION_MIN_L10
    frame = frame[rot].reset_index(drop=True)
    seasons = frame["SEASON"].astype(str)
    dates = frame["GAME_DATE"]
    logger.info("rotation rows (MIN_L10>=%.0f): %d\n", ROTATION_MIN_L10, len(frame))

    metrics = {}
    logger.info(f"{'stat':<6}{'n':>9}{'holdout_mae':>13}{'cv_mae':>9}{'best_it':>9}{'baseline':>10}{'skill':>8}")
    for t in TARGET_STATS:
        cols = features_for(t)
        anchor = pd.to_numeric(frame[f"{t}_L10"], errors="coerce").fillna(0.0)
        y_adj = pd.to_numeric(frame[t], errors="coerce").fillna(0.0) - anchor
        X = frame[cols].replace([np.inf, -np.inf], np.nan).fillna(0.0)
        model, m = walk_forward_train(X, y_adj, seasons, dates=dates,
                                      params=PARAMS, max_cv_folds=args.max_cv_folds)
        # honest skill vs the L10 baseline on the same holdout season
        ho = seasons == m["holdout_season"]
        baseline = float(y_adj[ho].abs().mean())               # predict L10 (adj 0)
        skill = (1.0 - m["holdout_mae"] / baseline) * 100.0 if baseline else 0.0

        joblib.dump({"model": model, "target": t, "anchor_col": f"{t}_L10",
                     "feature_cols": cols, "metrics": m},
                    args.out / f"player_{t}.joblib")
        metrics[t] = {"n": int(len(frame)), "holdout_mae": m["holdout_mae"], "cv_mae": m.get("cv_mae"),
                      "best_iteration": m.get("best_iteration"), "baseline_l10": baseline,
                      "skill_pct": round(skill, 2), "holdout_season": m.get("holdout_season")}
        logger.info(f"{t:<6}{len(frame):>9}{m['holdout_mae']:>13.3f}"
                    f"{(m.get('cv_mae') or 0):>9.3f}{m.get('best_iteration', -1):>9}"
                    f"{baseline:>10.3f}{skill:>7.1f}%")

    with open(args.out / "nba_player_v3_metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)
    logger.info("\nDone. Artifacts in %s", args.out)


if __name__ == "__main__":
    main()
