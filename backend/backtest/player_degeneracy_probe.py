#!/usr/bin/env python3
"""Isolate the degeneracy fix: on the CURRENT full feature set (no availability
yet), does stronger regularization stop the anchored player model collapsing to
1-9 trees, and does it then beat the L10 baseline?

Honest split: train <= 2023-24, holdout 2024-25 (full season). Target = stat -
stat_L10 (anchored); baseline = predict 0 (i.e. use the L10 average).
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from feature_engine import default_engine, split_features_targets
from model_training.train_hybrid import _load_or_build_features, ROTATION_MIN_L10

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

HOLDOUT = "2024-25"
PARAMS = dict(num_leaves=31, min_child_samples=100, colsample_bytree=0.7,
              subsample=0.8, reg_lambda=1.0)
STATS = ["PTS", "AST", "FG3M"]

# Curated signal set (prefixes/exacts) — the hypothesis is that pruning the 321
# noisy/collinear features to these ~50 stops the tree-1 inner-val overfit.
CURATED_PREFIXES = ("MIN_L", "PTS_L", "PTS_PER100_L", "USG_PCT_L", "TS_PCT_L",
                    "DVP_", "OPP_PRIOR_AVG_", "HA_HOME_", "HA_AWAY_", "TRV_")
CURATED_EXACT = {"MIN_CV_L10", "OPP_DEF_RATING", "OPP_OFF_RATING", "OPPONENT_STRENGTH",
                 "DAYS_REST", "IS_B2B", "REST_FACTOR", "IS_HOME", "GAMES_LAST_7",
                 "TEAM_PACE", "OPP_DAYS_REST", "OPP_IS_B2B"}


def _curated(feats, stat):
    keep = [c for c in feats if c in CURATED_EXACT or any(c.startswith(p) for p in CURATED_PREFIXES)]
    keep += [c for c in feats if c.startswith(f"{stat}_L")]  # the target's own rolls
    return sorted(set(keep))


def main() -> None:
    from lightgbm import LGBMRegressor, early_stopping

    eng = default_engine()
    full = _load_or_build_features(eng, eng.player_data_dir, None)
    X_all, feats, ycols, seasons = split_features_targets(full)
    rot = pd.to_numeric(full.get("MIN_L10", 0), errors="coerce").fillna(0.0) >= ROTATION_MIN_L10
    full, X_all, seasons = full[rot].reset_index(drop=True), X_all[rot].reset_index(drop=True), seasons[rot].reset_index(drop=True)
    # drop the undersized-season stub the guard would exclude
    vc = seasons.value_counts()
    keep = set(vc[vc >= 0.2 * vc.median()].index)
    tr_mask = seasons.isin(keep) & (seasons < HOLDOUT)
    ho_mask = seasons == HOLDOUT
    logger.info("features=%d  train rows=%d  holdout rows=%d\n", len(feats), int(tr_mask.sum()), int(ho_mask.sum()))

    rng = np.random.RandomState(42)
    for stat in STATS:
        anc = pd.to_numeric(full[f"{stat}_L10"], errors="coerce").fillna(0.0)
        y = pd.to_numeric(full[stat], errors="coerce") - anc
        base = float(y[ho_mask].abs().mean())  # predict L10
        actual = pd.to_numeric(full[stat], errors="coerce")
        line = f"{stat:<6} L10base={base:.3f} |"
        for name, cols in [("all(321)", feats), ("curated", _curated(feats, stat))]:
            Xtr = X_all[cols][tr_mask].fillna(0.0)
            perm = rng.permutation(len(Xtr)); k = int(len(Xtr) * 0.15)
            va, fit = perm[:k], perm[k:]
            m = LGBMRegressor(n_estimators=2000, learning_rate=0.03, subsample_freq=1,
                              random_state=42, n_jobs=-1, verbose=-1, **PARAMS)
            m.fit(Xtr.iloc[fit], y[tr_mask].iloc[fit], eval_set=[(Xtr.iloc[va], y[tr_mask].iloc[va])],
                  callbacks=[early_stopping(100, verbose=False)])
            pred = m.predict(X_all[cols][ho_mask].fillna(0.0))
            lvl_mae = float(np.abs(pred + anc[ho_mask] - actual[ho_mask]).mean())
            line += f"  {name}(n={len(cols)}): iter={m.best_iteration_:>4} adjStd={np.std(pred):.3f} MAE={lvl_mae:.3f} ({(1-lvl_mae/base)*100:+.1f}%)"
        logger.info(line)


if __name__ == "__main__":
    main()
