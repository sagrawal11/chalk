"""Honest walk-forward CV + untouched-holdout training (shared by all trainers).

Fixes the optimistic bias the old trainers carried (PLANNING.md 8.1/8.2/8.3):

- **Untouched final holdout (8.2):** the last season is reserved and never used
  as a CV fold nor as an early-stopping eval set, so ``holdout_mae`` is an honest
  out-of-sample estimate.
- **No early-stopping on the scored data (8.1):** early stopping uses an INNER
  validation split carved (by date) from the training window; a fold's scoring
  season is never in its ``eval_set``.
- **One hyperparameter set (8.3):** the same params drive CV folds and the
  shipped model; ``n_estimators`` is an upper bound resolved by early stopping.

Used by ``train_hybrid`` (player stats) and ``train_team_model`` (team markets).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

DEFAULT_LGBM_PARAMS: Dict[str, Any] = dict(
    n_estimators=2000,          # upper bound; early stopping resolves the real count
    learning_rate=0.03,
    num_leaves=63,
    max_depth=-1,
    min_child_samples=50,
    subsample=0.8,
    colsample_bytree=0.8,
    subsample_freq=1,
    random_state=42,
    n_jobs=-1,
    verbose=-1,
)
EARLY_STOPPING_ROUNDS = 100
INNER_VAL_FRACTION = 0.15


def _ordered(idx: pd.Index, dates: Optional[pd.Series]) -> pd.Index:
    if dates is not None:
        return dates.loc[idx].sort_values(kind="stable").index
    return idx


def _inner_split(
    train_idx: pd.Index, dates: Optional[pd.Series], frac: float
) -> Tuple[pd.Index, pd.Index]:
    """RANDOM (seeded) inner-validation split for early-stopping tree-count
    selection.

    A tail-by-date inner-val suffered era/scoring drift on the highest-magnitude
    targets (PTS/FGM): the validation loss worsened after the first tree, so
    early stopping quit at ~1 tree and the model collapsed to a near-constant.
    A random split removes that drift for the purpose of choosing the number of
    trees. The honest out-of-sample estimate is unaffected: it is still the
    untouched final season, which this split never touches.
    """
    labels = np.asarray(list(train_idx))
    k = max(1, int(round(len(labels) * frac)))
    perm = np.random.RandomState(42).permutation(labels)
    return pd.Index(perm[k:]), pd.Index(perm[:k])


def _importance(model: Any, X: pd.DataFrame) -> List[Dict[str, Any]]:
    try:
        imp = pd.DataFrame(
            {"feature": list(X.columns), "importance": model.feature_importances_}
        ).sort_values("importance", ascending=False)
        return imp.head(20).to_dict(orient="records")
    except Exception:  # pragma: no cover - importance is best-effort metadata
        return []


def _best_iter(model: Any, fallback: int) -> int:
    bi = getattr(model, "best_iteration_", None)
    return int(bi) if bi and bi > 0 else int(fallback)


def walk_forward_train(
    X: pd.DataFrame,
    y: pd.Series,
    seasons: pd.Series,
    *,
    dates: Optional[pd.Series] = None,
    params: Optional[Dict[str, Any]] = None,
    early_stopping_rounds: int = EARLY_STOPPING_ROUNDS,
    max_cv_folds: Optional[int] = None,
    min_season_frac: float = 0.2,
) -> Tuple[Any, Dict[str, Any]]:
    """Train one regressor honestly. Returns ``(shipped_model, metrics)`` where
    metrics carry both ``cv_mae`` and a truly-held-out ``holdout_mae``.

    The shipped model is refit on ALL rows at the early-stopping-validated
    iteration count (holdout rows are used for training only, never for the
    estimate) to maximize the data available at inference.
    """
    from lightgbm import LGBMRegressor, early_stopping

    params = {**DEFAULT_LGBM_PARAMS, **(params or {})}

    X = X.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    y = y.replace([np.inf, -np.inf], np.nan)
    valid = y.notna()
    X, y, seasons = X.loc[valid], y.loc[valid], seasons.loc[valid]
    if dates is not None:
        dates = pd.to_datetime(dates.loc[valid], errors="coerce")
    if len(X) < 50:
        raise ValueError("Not enough rows to train")

    # Guard against a partial/stub season (e.g., an in-progress current season with
    # only a handful of games) being auto-picked as the scoring holdout, which gives
    # a meaningless holdout_mae (measured on ~200 rows) and can degenerate per-stat
    # metrics. Drop any season far smaller than the median season; such rows are
    # neither a valid holdout nor complete enough to train on when validating the
    # prior full season. The threshold is RELATIVE so it holds across sports
    # (NBA ~23k rows/season, NFL ~300) and across player vs team granularity.
    season_counts = seasons.value_counts()
    if min_season_frac and len(season_counts) >= 2:
        floor = min_season_frac * float(season_counts.median())
        keep = set(season_counts[season_counts >= floor].index)
        dropped = [s for s in season_counts.index if s not in keep]
        if dropped and len(keep) >= 2:  # never strand ourselves below CV+holdout
            logger.info("Excluding %d undersized season(s) from CV/holdout: %s "
                        "(median=%.0f rows, floor=%.0f)",
                        len(dropped), sorted(map(str, dropped)), season_counts.median(), floor)
            mask = seasons.isin(keep)
            X, y, seasons = X.loc[mask], y.loc[mask], seasons.loc[mask]
            if dates is not None:
                dates = dates.loc[mask]

    def _fit_es(train_idx: pd.Index) -> Any:
        fit_idx, val_idx = _inner_split(train_idx, dates, INNER_VAL_FRACTION)
        model = LGBMRegressor(**params)
        model.fit(
            X.loc[fit_idx], y.loc[fit_idx],
            eval_set=[(X.loc[val_idx], y.loc[val_idx])],
            callbacks=[early_stopping(early_stopping_rounds, verbose=False)],
        )
        return model

    uniq = sorted(seasons.unique().tolist())

    # Degenerate case: too few seasons for CV + holdout. Temporal 80/20.
    if len(uniq) < 3:
        order = _ordered(X.index, dates)
        split = max(1, int(len(order) * 0.8))
        tr, ho = order[:split], order[split:]
        model = _fit_es(tr)
        if len(ho):
            ho_pred = model.predict(X.loc[ho])
            r = ho_pred - y.loc[ho]
            mae = float(np.mean(np.abs(r)))
            rmse = float(np.sqrt(np.mean(r ** 2)))
            rstd = float(np.std(r))
            mu_mean = float(np.mean(ho_pred))
            mu_sq_mean = float(np.mean(ho_pred ** 2))
        else:
            mae = rmse = rstd = mu_mean = mu_sq_mean = float("nan")
        return model, {
            "cv_mae": None, "cv_metrics": [], "holdout_mae": mae,
            "holdout_rmse": rmse, "holdout_resid_std": rstd,
            "holdout_mu_mean": mu_mean, "holdout_mu_sq_mean": mu_sq_mean,
            "holdout_season": None, "best_iteration": _best_iter(model, params["n_estimators"]),
            "n_train": int(len(tr)), "n_holdout": int(len(ho)),
            "params": {k: params[k] for k in ("learning_rate", "num_leaves", "max_depth")},
            "top_features": _importance(model, X),
        }

    holdout_season = uniq[-1]
    cv_seasons = uniq[:-1]
    holdout_idx = seasons[seasons == holdout_season].index

    # Walk-forward CV strictly inside cv_seasons (never touches the holdout).
    cv_metrics: List[Dict[str, Any]] = []
    fold_starts = list(range(1, len(cv_seasons)))
    if max_cv_folds:
        fold_starts = fold_starts[-max_cv_folds:]  # keep the most recent folds
    for i in fold_starts:
        tr_idx = seasons[seasons.isin(cv_seasons[:i])].index
        te_idx = seasons[seasons == cv_seasons[i]].index
        if len(tr_idx) < 50 or len(te_idx) < 10:
            continue
        model = _fit_es(tr_idx)  # early stop on an inner split of the TRAIN window
        mae = float(np.mean(np.abs(model.predict(X.loc[te_idx]) - y.loc[te_idx])))
        cv_metrics.append(
            {"season": cv_seasons[i], "mae": mae, "n_train": int(len(tr_idx)), "n_test": int(len(te_idx))}
        )
    cv_mae = float(np.mean([m["mae"] for m in cv_metrics])) if cv_metrics else None

    # Evaluation model: train on all cv_seasons, score the untouched holdout.
    eval_model = _fit_es(seasons[seasons.isin(cv_seasons)].index)
    best_iter = _best_iter(eval_model, params["n_estimators"])
    ho_pred = eval_model.predict(X.loc[holdout_idx])
    ho_resid = ho_pred - y.loc[holdout_idx]
    holdout_mae = float(np.mean(np.abs(ho_resid)))
    holdout_rmse = float(np.sqrt(np.mean(ho_resid ** 2)))
    holdout_resid_std = float(np.std(ho_resid))
    holdout_mu_mean = float(np.mean(ho_pred))
    holdout_mu_sq_mean = float(np.mean(ho_pred ** 2))

    # Shipped model: refit on ALL rows at the validated iteration count.
    ship_params = {**params, "n_estimators": max(1, best_iter)}
    shipped = LGBMRegressor(**ship_params)
    shipped.fit(X, y)

    return shipped, {
        "cv_mae": cv_mae, "cv_metrics": cv_metrics,
        "holdout_mae": holdout_mae, "holdout_rmse": holdout_rmse,
        "holdout_resid_std": holdout_resid_std,
        "holdout_mu_mean": holdout_mu_mean, "holdout_mu_sq_mean": holdout_mu_sq_mean,
        "holdout_season": holdout_season,
        "best_iteration": best_iter, "n_train_final": int(len(X)),
        "params": {k: params[k] for k in ("learning_rate", "num_leaves", "max_depth")},
        "top_features": _importance(shipped, X),
    }
