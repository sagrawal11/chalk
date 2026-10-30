#!/usr/bin/env python3
"""Train the NHL skater points/shots prop models.

Same v2 methodology as the other sports' player props: each target is anchored
(predict stat - stat_L5, add back) and usage-gated (>= MIN_PRIOR_GAMES of
history), via the shared honest walk-forward trainer. Reports skill vs the
recent-average baseline for each target.
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
from sports.nhl.skater_features import (ANCHOR_COLS, FEATURE_COLS, MIN_PRIOR_GAMES,
                                        PROP_TARGETS, build_skater_frame)

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

NHL_SKATER_DIR = ARTIFACTS_DIR / "nhl_skater"
PARAMS = dict(n_estimators=700, learning_rate=0.03, num_leaves=31,
              min_child_samples=60, subsample=0.9, colsample_bytree=0.9, reg_lambda=1.0)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=2023)
    ap.add_argument("--end", type=int, default=2024)
    ap.add_argument("--out", type=Path, default=NHL_SKATER_DIR)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    frame = build_skater_frame(range(args.start, args.end + 1))
    if frame.empty or "_n_prior" not in frame.columns:
        logger.warning("NHL skater frame empty (no data fetched %d-%d) - skipping training.",
                       args.start, args.end)
        return
    frame = frame[frame["_n_prior"] >= MIN_PRIOR_GAMES].reset_index(drop=True)
    logger.info("NHL skater frame: %d gated games (%d-%d)", len(frame), args.start, args.end)

    summary = {"n": int(len(frame)), "targets": {}}
    for target in PROP_TARGETS:
        anchor_col = ANCHOR_COLS[target]
        anchor = pd.to_numeric(frame[anchor_col], errors="coerce").fillna(0.0)
        y_adj = pd.to_numeric(frame[target], errors="coerce").fillna(0.0) - anchor
        X = frame[FEATURE_COLS].replace([np.inf, -np.inf], np.nan).fillna(0.0)
        model, m = walk_forward_train(X, y_adj, frame["season"].astype(str),
                                      dates=frame["date"], params=PARAMS)

        ho = frame["season"].astype(str) == str(m.get("holdout_season"))
        # baseline: predict stat_L5 (adjustment 0). If no season holdout was
        # picked (few seasons -> temporal split), fall back to the full-sample
        # adjustment magnitude so skill% is still meaningful.
        baseline = float(y_adj[ho].abs().mean()) if ho.any() else float(y_adj.abs().mean())
        skill = (1.0 - m["holdout_mae"] / baseline) * 100.0 if baseline else 0.0

        joblib.dump({"model": model, "target": target, "anchor_col": anchor_col,
                     "feature_cols": FEATURE_COLS, "metrics": m},
                    args.out / f"skater_{target}.joblib")
        summary["targets"][target] = {
            "holdout_mae": m["holdout_mae"], "cv_mae": m.get("cv_mae"),
            "baseline_l5": baseline, "skill_pct": round(skill, 2),
            "best_iteration": m.get("best_iteration"), "holdout_season": m.get("holdout_season")}
        logger.info("%s: holdout_mae=%.3f cv_mae=%s best_it=%s | baseline(%s)=%.3f | skill=%.1f%%",
                    target, m["holdout_mae"],
                    f"{m.get('cv_mae'):.3f}" if m.get("cv_mae") else "n/a",
                    m.get("best_iteration"), anchor_col, baseline, skill)

    with open(args.out / "nhl_skater_metrics.json", "w") as f:
        json.dump(summary, f, indent=2)
    logger.info("Done. NHL skater artifacts in %s", args.out)


if __name__ == "__main__":
    main()
