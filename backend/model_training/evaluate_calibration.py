"""Calibration metrics + a team-model calibration report (Phase 1C gate).

For a public track record, calibration IS the product: if we say 62%, it should
hit ~62%. This module scores probability quality: Brier, log-loss, PIT
uniformity, reliability bins, and central-interval coverage. It produces a
``calibration_report.json`` for the team model on its untouched holdout season.

Out-of-sample by construction (honesty fix): the report does NOT score the
shipped model. The shipped model is refit on ALL seasons (incl. the holdout) at
``best_iteration`` (see ``validation.walk_forward_train``), so scoring it on the
holdout is mildly in-sample and yields optimistic Brier / PIT / reliability. We
instead train a CLEAN **eval-model on seasons < holdout only**, with the exact
same LGBM params and inner-split early-stopping ``walk_forward_train`` uses for
its honest holdout estimate, and score THAT on the untouched holdout season.
The resulting numbers are (as expected) slightly worse than the old in-sample
ones; that gap is the optimism we were previously hiding.

Sport-agnostic: ``--sport nba`` and ``--sport nfl`` score the level-predicting
team model for that sport (``sports.<sport>.team_features``); both learn the
absolute margin/total from team features only (no betting line).
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from statistics import NormalDist
from typing import Any, Dict, List, Sequence, Tuple

import numpy as np
import pandas as pd

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from config.paths import ARTIFACTS_DIR, KAGGLE_TEAM_GAMES_PARQUET

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 1/E|Z| for a standard normal: converts a robust MAE into an equivalent sigma
# (matches the sigma the team trainers persist). Keeping this local so the eval
# model's sigma is derived the same way as the shipped one.
_MAE_TO_SIGMA = 1.2533


def brier_score(p: Sequence[float], y: Sequence[float]) -> float:
    p = np.asarray(p, float)
    y = np.asarray(y, float)
    return float(np.mean((p - y) ** 2))


def log_loss(p: Sequence[float], y: Sequence[float], eps: float = 1e-12) -> float:
    p = np.clip(np.asarray(p, float), eps, 1 - eps)
    y = np.asarray(y, float)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def pit_values(actual: Sequence[float], mu: Sequence[float], sigma: Sequence[float]) -> np.ndarray:
    """Probability Integral Transform: CDF(actual) under each row's normal.
    Uniform on [0,1] iff the predictive distribution is calibrated."""
    actual, mu, sigma = np.asarray(actual, float), np.asarray(mu, float), np.asarray(sigma, float)
    return np.array([NormalDist(m, max(s, 1e-9)).cdf(a) for a, m, s in zip(actual, mu, sigma)])


def pit_uniformity(pit: np.ndarray, nbins: int = 10) -> Dict[str, Any]:
    counts, _ = np.histogram(pit, bins=nbins, range=(0.0, 1.0))
    exp = len(pit) / nbins if len(pit) else 0.0
    chi2 = float(np.sum((counts - exp) ** 2 / exp)) if exp > 0 else float("nan")
    return {"nbins": nbins, "chi2": chi2, "counts": counts.tolist(), "expected_per_bin": exp}


def interval_coverage(pit: np.ndarray, level: float) -> float:
    lo, hi = (1 - level) / 2, 1 - (1 - level) / 2
    return float(np.mean((pit >= lo) & (pit <= hi)))


def reliability_bins(p: Sequence[float], y: Sequence[float], nbins: int = 10) -> List[Dict[str, Any]]:
    p, y = np.asarray(p, float), np.asarray(y, float)
    edges = np.linspace(0.0, 1.0, nbins + 1)
    out = []
    for i in range(nbins):
        hi = edges[i + 1] if i < nbins - 1 else 1.0 + 1e-9
        m = (p >= edges[i]) & (p < hi)
        if m.sum() == 0:
            continue
        out.append({
            "bin": [float(edges[i]), float(edges[i + 1])],
            "pred_mean": float(p[m].mean()), "obs_rate": float(y[m].mean()), "n": int(m.sum()),
        })
    return out


def evaluate_normal_target(mu, sigma, actual, name: str) -> Dict[str, Any]:
    pit = pit_values(actual, mu, sigma)
    return {
        "target": name, "n": int(len(actual)),
        "pit_uniformity": pit_uniformity(pit),
        "coverage_50": interval_coverage(pit, 0.5),
        "coverage_80": interval_coverage(pit, 0.8),
    }


# --------------------------------------------------------------------------- #
# Clean out-of-sample eval model (the honesty fix)                            #
# --------------------------------------------------------------------------- #
def _oos_holdout_predictions(
    frame: pd.DataFrame,
    feature_cols: List[str],
    target_col: str,
    seasons: pd.Series,
    dates: pd.Series,
    params: Dict[str, Any],
) -> Tuple[str, np.ndarray, np.ndarray, float]:
    """Train a clean eval-model on seasons < holdout and predict the holdout.

    Returns ``(holdout_season, mu_level, y_true_level, sigma)`` on the natural
    (level) scale; ``sigma`` is derived from the eval-model's OWN holdout MAE via
    the same MAE->sigma factor the trainers persist.
    """
    from lightgbm import LGBMRegressor, early_stopping

    from model_training.validation import (DEFAULT_LGBM_PARAMS, EARLY_STOPPING_ROUNDS,
                                            INNER_VAL_FRACTION, _inner_split)

    lgbm_params = {**DEFAULT_LGBM_PARAMS, **params}

    X = frame[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    y_level = frame[target_col].astype(float)
    y_model = y_level

    uniq = sorted(seasons.unique().tolist())
    if len(uniq) < 2:
        raise ValueError(f"Need >=2 seasons for an out-of-sample holdout; got {uniq}")
    holdout_season = uniq[-1]
    cv_idx = seasons[seasons.isin(uniq[:-1])].index
    holdout_idx = seasons[seasons == holdout_season].index

    # Same seeded inner-split + early stopping as the trainer's honest eval-model.
    fit_idx, val_idx = _inner_split(cv_idx, dates, INNER_VAL_FRACTION)
    model = LGBMRegressor(**lgbm_params)
    model.fit(
        X.loc[fit_idx], y_model.loc[fit_idx],
        eval_set=[(X.loc[val_idx], y_model.loc[val_idx])],
        callbacks=[early_stopping(EARLY_STOPPING_ROUNDS, verbose=False)],
    )

    mu_level = model.predict(X.loc[holdout_idx])
    y_true_level = y_level.loc[holdout_idx].to_numpy()

    # Sigma from this eval-model's own out-of-sample residuals, mirrors the
    # trainer's sigma.
    ho_mae = float(np.mean(np.abs(mu_level - y_true_level)))
    sigma = float(_MAE_TO_SIGMA * ho_mae) if ho_mae else float(np.std(y_true_level - mu_level) or 1.0)
    logger.info("eval-model %s: holdout=%s n=%d oos_mae=%.3f sigma=%.3f best_iter=%s",
                target_col, holdout_season, len(holdout_idx), ho_mae, sigma,
                getattr(model, "best_iteration_", None))
    return holdout_season, mu_level, y_true_level, sigma


# --------------------------------------------------------------------------- #
# Per-sport configuration                                                     #
# --------------------------------------------------------------------------- #
def _nba_config(parquet: Path) -> Dict[str, Any]:
    from sports.nba.team_features import TEAM_FEATURE_COLS, build_team_game_frame
    from sports.nba.teams import season_int_to_str
    from model_training.train_team_model import TEAM_LGBM_PARAMS

    frame = build_team_game_frame(parquet)
    return {
        "sport": "nba",
        "frame": frame,
        "feature_cols": TEAM_FEATURE_COLS,
        "seasons": frame["season"].map(season_int_to_str),
        "dates": frame["game_date"],
        "params": TEAM_LGBM_PARAMS,
        "model_dir": ARTIFACTS_DIR / "team",
    }


def _nfl_config(start: int, end: int) -> Dict[str, Any]:
    from sports.nfl.team_features import TEAM_FEATURE_COLS, build_team_game_frame
    from model_training.train_nfl_team_model import NFL_LGBM_PARAMS

    frame = build_team_game_frame(range(start, end + 1))
    return {
        "sport": "nfl",
        "frame": frame,
        "feature_cols": TEAM_FEATURE_COLS,
        "seasons": frame["season"].astype(str),
        "dates": frame["game_date"],
        "params": NFL_LGBM_PARAMS,
        "model_dir": ARTIFACTS_DIR / "nfl_team",
    }


def evaluate_team_model(
    sport: str = "nba",
    parquet: Path = KAGGLE_TEAM_GAMES_PARQUET,
    nfl_start: int = 2010,
    nfl_end: int = 2024,
) -> Dict[str, Any]:
    """Out-of-sample calibration report for a team score model.

    Trains a clean eval-model on seasons < holdout (same params / inner-split as
    the honest trainer) and scores its holdout predictions, so Brier / PIT /
    reliability are genuinely out-of-sample, unlike the old shipped-model path.
    """
    if sport == "nba":
        cfg = _nba_config(parquet)
    elif sport == "nfl":
        cfg = _nfl_config(nfl_start, nfl_end)
    else:  # pragma: no cover - guarded by argparse choices
        raise ValueError(f"unknown sport {sport!r} (expected 'nba' or 'nfl')")

    frame, feats = cfg["frame"], cfg["feature_cols"]
    seasons, dates, params = cfg["seasons"], cfg["dates"], cfg["params"]

    hs_m, mu_margin, y_margin, sig_margin = _oos_holdout_predictions(
        frame, feats, "y_margin", seasons, dates, params)
    hs_t, mu_total, y_total, sig_total = _oos_holdout_predictions(
        frame, feats, "y_total", seasons, dates, params)

    y_win = (y_margin > 0).astype(float)
    p_home = np.array([1.0 - NormalDist(m, sig_margin).cdf(0.0) for m in mu_margin])
    n = int(len(y_margin))

    return {
        "sport": sport,
        "eval": "out_of_sample",  # clean OOS eval-model (seasons < holdout only)
        "holdout_season": hs_m,
        "n_games": n,
        "sigma_margin": sig_margin,
        "sigma_total": sig_total,
        "home_win_rate_actual": float(y_win.mean()),
        "home_win_prob_mean": float(p_home.mean()),
        "moneyline_brier": brier_score(p_home, y_win),
        "moneyline_logloss": log_loss(p_home, y_win),
        "margin": evaluate_normal_target(mu_margin, np.full(n, sig_margin), y_margin, "margin"),
        "total": evaluate_normal_target(mu_total, np.full(n, sig_total), y_total, "total"),
        "reliability_moneyline": reliability_bins(p_home, y_win, nbins=8),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sport", choices=["nba", "nfl"], default="nba")
    ap.add_argument("--parquet", type=Path, default=KAGGLE_TEAM_GAMES_PARQUET,
                    help="NBA team-games parquet")
    ap.add_argument("--nfl-start", type=int, default=2010)
    ap.add_argument("--nfl-end", type=int, default=2024)
    ap.add_argument("--out", type=Path, default=None,
                    help="override output path (defaults to the sport's artifact dir)")
    args = ap.parse_args()

    report = evaluate_team_model(
        sport=args.sport, parquet=args.parquet,
        nfl_start=args.nfl_start, nfl_end=args.nfl_end,
    )
    default_dir = ARTIFACTS_DIR / ("team" if args.sport == "nba" else "nfl_team")
    default_dir.mkdir(parents=True, exist_ok=True)
    out = args.out or (default_dir / "calibration_report.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    logger.info(
        "%s calibration (OOS) | holdout=%s n=%d | home win: actual=%.3f pred=%.3f | "
        "ML Brier=%.4f | margin cov80=%.2f total cov80=%.2f",
        args.sport.upper(), report["holdout_season"], report["n_games"],
        report["home_win_rate_actual"], report["home_win_prob_mean"],
        report["moneyline_brier"], report["margin"]["coverage_80"], report["total"]["coverage_80"],
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
