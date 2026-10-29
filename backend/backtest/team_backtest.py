"""Walk-forward team-market backtest: for each season S, train margin & total on
seasons < S, predict S out-of-sample, and grade straight-up (winner) accuracy +
MAE + winner log-loss. If historical odds are supplied (game_key -> {spread_home,
total}), also grade against-the-spread and over/under hit rates.

Honest by construction: a season is only ever predicted by a model that never
saw it. This is the "would our picks have won" reliability check. It is
market-blind by construction: the line is NEVER a model input; ``odds`` is used
only to grade ATS/O-U. This is the shared eval the experiment harness reuses.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd
from scipy.stats import norm

from model_training.train_team_model import TEAM_LGBM_PARAMS
from predictions.schema import make_game_key
from sports.nba.team_features import TEAM_FEATURE_COLS, build_team_game_frame
from sports.nba.teams import season_int_to_str

logger = logging.getLogger(__name__)


def _season_label(sport: str, s: int) -> str:
    """Format a season int for display. NBA/NHL span two calendar years
    (2024 -> '2024-25'); NFL/CFB/MLB/soccer are single-year (2024 -> '2024')."""
    if str(sport).lower() in ("nba", "nhl"):
        return season_int_to_str(int(s))
    return str(int(s))


def _fit(train_df: pd.DataFrame, col: str, params: Dict[str, Any], feature_cols):
    """Fit one LightGBM regressor with a random inner-val early stop (same
    philosophy as model_training.validation, random split avoids era drift).
    Returns ``(model, sigma)`` where sigma is the inner-val residual std."""
    from lightgbm import LGBMRegressor, early_stopping

    X = train_df[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    y = train_df[col]
    n = len(X)
    k = max(1, int(n * 0.15))
    perm = np.random.RandomState(0).permutation(n)
    vi, fi = perm[:k], perm[k:]
    m = LGBMRegressor(**params)
    m.fit(X.iloc[fi], y.iloc[fi], eval_set=[(X.iloc[vi], y.iloc[vi])],
          callbacks=[early_stopping(80, verbose=False)])
    sigma = float(np.std(y.iloc[vi].to_numpy() - m.predict(X.iloc[vi])))
    return m, sigma


def _grade_market(te: pd.DataFrame, mu_margin, mu_total, odds: Dict[str, Dict[str, float]], sport: str):
    """ATS + O/U hit rate: our side vs the posted line, graded on actual result."""
    ats_correct = ou_correct = graded = 0
    for i, (_, r) in enumerate(te.iterrows()):
        gk = make_game_key(sport, str(r["game_date"])[:10], r["away"], r["home"])
        line = odds.get(gk)
        if not line:
            continue
        graded += 1
        # Spread: home line s; our side = home if predicted margin beats the line.
        if line.get("spread_home") is not None:
            s = float(line["spread_home"])
            our_home = (mu_margin[i] + s) > 0
            home_covered = (r["y_margin"] + s) > 0
            ats_correct += int(our_home == home_covered)
        # Total: our side = over if predicted total above the line.
        if line.get("total") is not None:
            t = float(line["total"])
            our_over = mu_total[i] > t
            went_over = r["y_total"] > t
            ou_correct += int(our_over == went_over)
    return (
        round(ats_correct / graded, 4) if graded else None,
        round(ou_correct / graded, 4) if graded else None,
        graded,
    )


def walk_forward_backtest(
    frame: Optional[pd.DataFrame] = None,
    *,
    sport: str = "nba",
    feature_cols: Optional[list] = None,
    min_train_seasons: int = 3,
    odds: Optional[Dict[str, Dict[str, float]]] = None,
    params: Optional[Dict[str, Any]] = None,
) -> pd.DataFrame:
    params = {**TEAM_LGBM_PARAMS, **(params or {})}
    if frame is None:
        frame = build_team_game_frame()
    if feature_cols is None:
        feature_cols = TEAM_FEATURE_COLS
    frame = frame.copy()
    frame["season"] = frame["season"].astype(int)
    seasons = sorted(frame["season"].unique())

    rows = []
    for i, s in enumerate(seasons):
        if i < min_train_seasons:
            continue
        tr = frame[frame["season"] < s]
        te = frame[frame["season"] == s]
        if len(te) < 50 or len(tr) < 500:
            continue

        mm, sigma_m = _fit(tr, "y_margin", params, feature_cols)
        mt, _ = _fit(tr, "y_total", params, feature_cols)
        Xte = te[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(0.0)
        mu_m = mm.predict(Xte)
        mu_t = mt.predict(Xte)
        am = te["y_margin"].to_numpy()
        at = te["y_total"].to_numpy()

        # Winner probability from the margin distribution (market-blind):
        # P(home win) = P(margin > 0) = Phi(mu_margin / sigma_margin).
        sd = max(float(sigma_m), 1e-6)
        p_home = np.clip(norm.cdf(mu_m / sd), 1e-15, 1 - 1e-15)
        home_won = (am > 0).astype(float)
        winner_logloss = float(-np.mean(home_won * np.log(p_home) + (1 - home_won) * np.log(1 - p_home)))

        row = {
            "season": _season_label(sport, s),
            "n": int(len(te)),
            "su_acc": round(float(((mu_m > 0) == (am > 0)).mean()), 4),
            "winner_logloss": round(winner_logloss, 4),
            "margin_mae": round(float(np.mean(np.abs(mu_m - am))), 3),
            "total_mae": round(float(np.mean(np.abs(mu_t - at))), 3),
        }
        if odds is not None:
            ats, ou, graded = _grade_market(te, mu_m, mu_t, odds, sport)
            row.update({"ats_pct": ats, "ou_pct": ou, "market_games": graded})
        rows.append(row)

    return pd.DataFrame(rows)


def walk_forward_predictions(
    frame: pd.DataFrame,
    *,
    sport: str = "nba",
    feature_cols: Optional[list] = None,
    min_train_seasons: int = 3,
    params: Optional[Dict[str, Any]] = None,
) -> pd.DataFrame:
    """Per-GAME out-of-sample predictions (market-blind: team features only) for
    seeding the public track record. Same honest walk-forward as
    ``walk_forward_backtest``: every game is predicted by a model that never saw its
    season, but returns one row per game with predicted + actual scores."""
    params = {**TEAM_LGBM_PARAMS, "verbose": -1, **(params or {})}
    if feature_cols is None:
        feature_cols = TEAM_FEATURE_COLS
    if frame is None or frame.empty:
        return pd.DataFrame()
    frame = frame.copy()
    frame["season"] = frame["season"].astype(int)
    seasons = sorted(frame["season"].unique())

    out = []
    for i, s in enumerate(seasons):
        if i < min_train_seasons:
            continue
        tr = frame[frame["season"] < s]
        te = frame[frame["season"] == s]
        if len(te) < 50 or len(tr) < 500:
            continue
        mm, _ = _fit(tr, "y_margin", params, feature_cols)
        mt, _ = _fit(tr, "y_total", params, feature_cols)
        Xte = te[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(0.0)
        mu_m = mm.predict(Xte)
        mu_t = mt.predict(Xte)
        te = te.reset_index(drop=True)
        for j in range(len(te)):
            r = te.iloc[j]
            ym, yt = float(r["y_margin"]), float(r["y_total"])
            mmj, mtj = float(mu_m[j]), float(mu_t[j])
            out.append({
                "sport": sport,
                "game_date": str(pd.Timestamp(r["game_date"]).date()),
                "home": r["home"], "away": r["away"],
                "mu_margin": round(mmj, 3), "mu_total": round(mtj, 3),
                "pred_home_pts": round((mtj + mmj) / 2.0, 2),
                "pred_away_pts": round((mtj - mmj) / 2.0, 2),
                "actual_home_pts": round((yt + ym) / 2.0, 1),
                "actual_away_pts": round((yt - ym) / 2.0, 1),
            })
    return pd.DataFrame(out)


def summarize(bt: pd.DataFrame) -> Dict[str, Any]:
    if bt is None or bt.empty:
        return {}
    out = {
        "seasons": int(len(bt)),
        "games": int(bt["n"].sum()),
        "su_acc": round(float((bt["su_acc"] * bt["n"]).sum() / bt["n"].sum()), 4),
        "margin_mae": round(float((bt["margin_mae"] * bt["n"]).sum() / bt["n"].sum()), 3),
        "total_mae": round(float((bt["total_mae"] * bt["n"]).sum() / bt["n"].sum()), 3),
    }
    if "winner_logloss" in bt.columns and bt["winner_logloss"].notna().any():
        w = bt.dropna(subset=["winner_logloss"])
        out["winner_logloss"] = round(float((w["winner_logloss"] * w["n"]).sum() / w["n"].sum()), 4)
    if "ats_pct" in bt.columns and bt["ats_pct"].notna().any():
        w = bt.dropna(subset=["ats_pct"])
        out["ats_pct"] = round(float((w["ats_pct"] * w["market_games"]).sum() / w["market_games"].sum()), 4)
        out["ou_pct"] = round(float((w["ou_pct"] * w["market_games"]).sum() / w["market_games"].sum()), 4)
    return out
