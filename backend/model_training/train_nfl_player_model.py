#!/usr/bin/env python3
"""Train NFL player-prop models (passing/rushing/receiving yards, receptions).

Same v2 methodology as NBA players: anchored (predict stat - stat_L3, add back)
and usage-gated (each stat trained only on players who produce it), via the
shared honest walk-forward trainer.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import joblib
import pandas as pd

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from config.paths import ARTIFACTS_DIR
from model_training.validation import walk_forward_train
from sports.nfl.player_features import FEATURE_COLS, PROP_TARGETS, USAGE_GATE, build_player_frame

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

NFL_PLAYER_MODEL_DIR = ARTIFACTS_DIR / "nfl_player"
NFL_PLAYER_PARAMS = dict(
    n_estimators=800, learning_rate=0.03, num_leaves=31,
    max_depth=-1, min_child_samples=40, subsample=0.9, colsample_bytree=0.9,
)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=2015)
    ap.add_argument("--end", type=int, default=2024)
    ap.add_argument("--out", type=Path, default=NFL_PLAYER_MODEL_DIR)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    frame = build_player_frame(range(args.start, args.end + 1))
    logger.info("NFL player frame: %d player-weeks (%d-%d)", len(frame), args.start, args.end)

    metrics = {}
    for target in PROP_TARGETS:
        gate_col, gate_val = USAGE_GATE[target]
        rel = frame[pd.to_numeric(frame[gate_col], errors="coerce").fillna(0.0) >= gate_val]
        anchor = pd.to_numeric(rel[f"{target}_L3"], errors="coerce").fillna(0.0)
        y_adj = pd.to_numeric(rel[target], errors="coerce").fillna(0.0) - anchor
        model, m = walk_forward_train(rel[FEATURE_COLS], y_adj, rel["season"].astype(str),
                                      params=NFL_PLAYER_PARAMS)
        joblib.dump(
            {"model": model, "target": target, "anchor_col": f"{target}_L3",
             "feature_cols": FEATURE_COLS, "metrics": m},
            args.out / f"player_{target}.joblib",
        )
        metrics[target] = {"n": int(len(rel)), "holdout_mae": m.get("holdout_mae"),
                           "cv_mae": m.get("cv_mae"), "holdout_season": m.get("holdout_season")}
        logger.info("nfl player %s: n=%d holdout_mae(level)=%.2f (holdout %s)",
                    target, len(rel), m.get("holdout_mae", -1), m.get("holdout_season"))

    with open(args.out / "nfl_player_training_metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
    logger.info("Done. NFL player artifacts in %s", args.out)


if __name__ == "__main__":
    main()
