#!/usr/bin/env python3
"""
Train Hybrid Models: Global LightGBM regressors + player-specific Ridge residual
models.

Validation is honest (PLANNING.md 8.x, via ``model_training.validation``): a
truly-held-out final season, no early-stopping on scored data, one param set.
Residuals are keyed on the canonical player slug (9.1), gated on out-of-sample
improvement (9.2), and standardized (9.3).
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from config.paths import GLOBAL_MODEL_DIR, PLAYER_DATA_DIR
from feature_engine import (
    FeatureEngine,
    TARGET_STATS,
    save_feature_columns,
    default_engine,
    split_features_targets,
)
from model_training.validation import walk_forward_train
from models.distribution import nb_dispersion_from_moments
from utils.names import player_slug

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# A residual model is shipped only if it beats global-only on the player's
# held-out games by at least this relative margin (PLANNING.md 9.2).
MIN_RESIDUAL_GAMES = 150
RESIDUAL_MIN_IMPROVEMENT = 0.02
RESIDUAL_MIN_VAL_ROWS = 10
# Player model v2: only train on rotation-player games (recent minutes >= this),
# and predict each stat as an ADJUSTMENT to its recent average (anchor = <STAT>_L10).
ROTATION_MIN_L10 = 8.0


def _downcast_floats(df: pd.DataFrame) -> pd.DataFrame:
    """Halve the peak memory of the concatenated training matrix. In float64 the
    full matrix is ~3.9 GB and pd.concat + split's df.copy() briefly hold two copies
    (~8 GB) — enough to OOM-kill the 7 GB CI runner mid-load. float32 is lossless
    enough here (features/targets are small counting stats; LightGBM bins to float
    internally) and split_features_targets selects on np.number, so float32 columns
    are picked up identically."""
    fcols = df.select_dtypes("float64").columns
    if len(fcols):
        df[fcols] = df[fcols].astype("float32")
    return df


def _load_or_build_features(
    engine: FeatureEngine, player_data_dir: Path, max_players: Optional[int]
) -> pd.DataFrame:
    frames: List[pd.DataFrame] = []
    dirs = sorted([p for p in player_data_dir.iterdir() if p.is_dir()])
    if max_players:
        dirs = dirs[:max_players]
    for d in dirs:
        slug = d.name
        name = slug.replace("_", " ")
        pq = d / f"{slug}_features.parquet"

        loaded = False
        if pq.exists():
            try:
                df = pd.read_parquet(pq)
                if "ARCH_PROB_0" in df.columns:
                    frames.append(_downcast_floats(df))
                    loaded = True
            except Exception:
                pass

        if not loaded:
            built = engine.build_training_features(name, save_parquet=True)
            if built is not None and len(built) > 0:
                frames.append(_downcast_floats(built))
    if not frames:
        raise RuntimeError("No feature rows found. Run feature build or ensure player_data exists.")
    full = pd.concat(frames, ignore_index=True)
    del frames  # release the ~2 GB list of per-player frames; keep only the matrix
    # concat can re-promote a few columns to float64 when frames disagree on dtype
    # (or a column is absent in some) — downcast the result so the matrix is uniformly float32.
    return _downcast_floats(full)


def _feature_target_split(df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str], List[str], pd.Series]:
    """Delegates to the single source of truth so train_global and train_hybrid
    always select an identical feature set (no train-serve skew)."""
    return split_features_targets(df)


def train_global_model(
    X: pd.DataFrame, y: pd.Series, seasons: pd.Series, dates: Optional[pd.Series] = None
) -> Tuple[object, Dict[str, Any]]:
    """Thin wrapper around the shared honest trainer (kept for callers/tests)."""
    return walk_forward_train(X, y, seasons, dates=dates)


def train_residuals(
    X_full: pd.DataFrame,
    y_full: pd.Series,
    global_model: Any,
    slugs: pd.Series,
    dates: Optional[pd.Series] = None,
) -> Tuple[Dict[str, Any], int]:
    """Fit per-player Ridge on the global model's residuals, keyed by slug, and
    keep only models that improve the player's HELD-OUT (later games) MAE."""
    X_clean = X_full.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    y_clean = y_full.replace([np.inf, -np.inf], np.nan)
    valid = y_clean.notna()
    X = X_clean.loc[valid]
    y = y_clean.loc[valid]
    sl = slugs.loc[valid].astype(str)
    dt = (
        pd.to_datetime(dates.loc[valid], errors="coerce")
        if dates is not None
        else pd.Series(pd.RangeIndex(len(X)), index=X.index)
    )

    gpred = pd.Series(global_model.predict(X), index=X.index)
    resid = y - gpred

    frame = pd.DataFrame({"slug": sl, "date": dt})
    local_models: Dict[str, Any] = {}
    kept = considered = 0

    for slug, grp in frame.groupby("slug"):
        if len(grp) < MIN_RESIDUAL_GAMES:
            continue
        considered += 1
        order = grp.sort_values("date", kind="stable").index
        split = max(1, int(len(order) * 0.8))
        tr, va = order[:split], order[split:]
        if len(va) < RESIDUAL_MIN_VAL_ROWS:
            continue

        pipe = Pipeline([("sc", StandardScaler()), ("ridge", Ridge(alpha=1.0))])
        pipe.fit(X.loc[tr], resid.loc[tr])

        base_mae = float(np.mean(np.abs(resid.loc[va])))              # global-only
        adj_mae = float(np.mean(np.abs(resid.loc[va] - pipe.predict(X.loc[va]))))  # +residual
        if base_mae > 0 and adj_mae <= base_mae * (1.0 - RESIDUAL_MIN_IMPROVEMENT):
            full_pipe = Pipeline([("sc", StandardScaler()), ("ridge", Ridge(alpha=1.0))])
            full_pipe.fit(X.loc[order], resid.loc[order])   # refit on all the player's rows
            local_models[str(slug)] = full_pipe
            kept += 1

    logger.info("Residuals: kept %d / %d eligible players", kept, considered)
    return local_models, kept


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--player-data", type=Path, default=PLAYER_DATA_DIR)
    ap.add_argument("--out", type=Path, default=GLOBAL_MODEL_DIR)
    ap.add_argument("--max-players", type=int, default=None)
    ap.add_argument("--max-cv-folds", type=int, default=4,
                    help="Cap walk-forward CV to the most recent N folds (cost control)")
    args = ap.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)

    engine = default_engine()
    logger.info("Loading/building feature matrix...")
    full = _load_or_build_features(engine, args.player_data, args.max_players)
    if "PLAYER_NAME" not in full.columns:
        raise RuntimeError("PLAYER_NAME column missing, cannot train residuals.")

    X_frame, feature_cols, y_cols, seasons = _feature_target_split(full)
    if not feature_cols:
        raise RuntimeError("No numeric feature columns after split")

    save_feature_columns(feature_cols)
    dates = full["GAME_DATE"] if "GAME_DATE" in full.columns else None
    slugs = full["PLAYER_NAME"].map(player_slug)

    # v2 rotation filter: drop deep-bench / garbage-time games so the model isn't
    # diluted toward low scoring (MIN_L10 is prior-only, so this is leakage-safe).
    if "MIN_L10" in full.columns:
        rot = (pd.to_numeric(full["MIN_L10"], errors="coerce").fillna(0.0) >= ROTATION_MIN_L10).to_numpy()
    else:
        rot = np.ones(len(full), dtype=bool)
    full = full[rot].reset_index(drop=True)
    X_frame = X_frame[rot].reset_index(drop=True)
    seasons = seasons[rot].reset_index(drop=True)
    if dates is not None:
        dates = dates[rot].reset_index(drop=True)
    slugs = slugs[rot].reset_index(drop=True)
    logger.info("Features: %d rotation rows (MIN_L10>=%.0f), %d X cols, targets=%s",
                len(full), ROTATION_MIN_L10, len(feature_cols), y_cols)

    metrics_all: Dict[str, object] = {}
    dispersions: Dict[str, Any] = {}
    for target in TARGET_STATS:
        if target not in full.columns:
            logger.warning("Skipping %s — not in data", target)
            continue
        try:
            # v2 anchoring: predict the ADJUSTMENT to the stat's recent average so
            # the level tracks the player's form (holdout_mae on the adjustment
            # equals the level MAE, since the anchor cancels).
            anchor_col = f"{target}_L10"
            if anchor_col in full.columns:
                anchor = pd.to_numeric(full[anchor_col], errors="coerce").fillna(0.0)
            else:
                anchor_col = None
                anchor = pd.Series(0.0, index=full.index)
            y_adj = full[target] - anchor

            model, m = walk_forward_train(
                X_frame[feature_cols], y_adj, seasons, dates=dates, max_cv_folds=args.max_cv_folds
            )
            joblib.dump(
                {"model": model, "target": target, "anchor_col": anchor_col, "metrics": m},
                args.out / f"global_lgbm_{target}.joblib",
            )

            # NB dispersion for prop P(over): residual variance is identical for the
            # adjustment and the level; combine it with the stat's level moments.
            rstd = m.get("holdout_resid_std") or 0.0
            lvl = pd.to_numeric(full[target], errors="coerce")
            disp = nb_dispersion_from_moments(float(lvl.mean()), float((lvl ** 2).mean()), rstd ** 2)
            dispersions[target] = None if not np.isfinite(disp) else round(disp, 4)

            local_models, residual_count = train_residuals(
                X_frame[feature_cols], y_adj, model, slugs, dates
            )
            joblib.dump(local_models, args.out / f"residuals_{target}.joblib")

            m["residual_models_trained"] = residual_count
            m["nb_dispersion"] = dispersions[target]
            m["anchored"] = anchor_col is not None
            metrics_all[target] = m
            logger.info(
                "Trained %s | holdout_mae(level)=%.3f cv_mae=%s | residuals=%d | anchor=%s",
                target, m.get("holdout_mae", float("nan")),
                f"{m.get('cv_mae'):.3f}" if m.get("cv_mae") is not None else "n/a",
                residual_count, anchor_col,
            )
        except Exception as e:
            logger.exception("Failed training %s: %s", target, e)

    with open(args.out / "hybrid_training_metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics_all, f, indent=2)
    with open(args.out / "stat_dispersions.json", "w", encoding="utf-8") as f:
        json.dump(dispersions, f, indent=2)
    logger.info("Done. Artifacts in %s", args.out)


if __name__ == "__main__":
    main()
