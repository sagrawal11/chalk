"""Turn market-blind walk-forward predictions into graded ledger rows for the public
track record.

Each game becomes ONE "winner" moneyline pick (the model's favored side). Rows are
ROI-INELIGIBLE (``odds_american=None`` -> ``units=NaN``) because no historical closing
moneyline exists in our data: the hero metric is straight-up winner accuracy +
predicted-score error, and real ROI accrues forward once live prices are captured.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from track_record.grade import append_ledger, grade_team_pick

SEED_SOURCE = "seed_backtest"


def build_seed_rows(preds: pd.DataFrame) -> pd.DataFrame:
    """``preds``: output of ``backtest.team_backtest.walk_forward_predictions`` (per
    game: sport, game_date, home, away, mu_margin, mu_total, pred/actual home/away pts).
    Returns ledger-schema rows (+ additive score-error columns), ungraded ROI."""
    if preds is None or preds.empty:
        return pd.DataFrame()
    rows = []
    for _, r in preds.iterrows():
        home_pts, away_pts = float(r["actual_home_pts"]), float(r["actual_away_pts"])
        pred_home, pred_away = float(r["pred_home_pts"]), float(r["pred_away_pts"])
        side = "home" if float(r["mu_margin"]) >= 0 else "away"
        subject = r["home"] if side == "home" else r["away"]
        result = grade_team_pick(
            {"market_family": "moneyline", "side": side, "line": None}, home_pts, away_pts)
        rows.append({
            "sport": r["sport"], "game_date": str(r["game_date"])[:10],
            "market_family": "moneyline", "subject": subject, "side": side,
            "line": None, "stat": None, "odds_american": None, "edge": None,
            "result": result, "units": float("nan"),
            "pred_home_pts": round(pred_home, 1), "pred_away_pts": round(pred_away, 1),
            "home_pts_err": round(abs(pred_home - home_pts), 2),
            "away_pts_err": round(abs(pred_away - away_pts), 2),
            "source": SEED_SOURCE,
        })
    return pd.DataFrame(rows)


def build_soccer_seed_rows(matches: pd.DataFrame, *, min_train_seasons: int = 1
                           ) -> pd.DataFrame:
    """Season-level leakage-safe walk-forward for the Poisson (Dixon-Coles-lite) soccer
    model -> graded, ROI-ineligible ledger rows.

    ``matches``: tidy EPL frame (season/date/home/away/fthg/ftag), e.g. the raw output
    of ``sports.soccer.team_features.build_epl_matches`` (its extra feature columns are
    ignored; ratings are recomputed per fold). For each season S with >= ``min_train_seasons``
    prior seasons, team ratings are built from matches BEFORE S only (``latest_team_ratings``
    naturally uses the most recent prior season), every match in S is predicted via
    ``predict_3way``, and the MORE-LIKELY of home/away is the market-blind winner (never a
    draw). A draw grades as a LOSS for the picked side (consistent with ``grade_team_pick``
    moneyline). Matches whose teams lack data-backed ratings (promoted sides, usage gate)
    are skipped. Predicted scores come from the Poisson lambdas (expected goals)."""
    from sports.soccer.team_features import latest_team_ratings, predict_3way

    if matches is None or matches.empty or "season" not in matches.columns:
        return pd.DataFrame()
    df = matches.copy()
    df["season"] = df["season"].astype(int)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["fthg"] = pd.to_numeric(df["fthg"], errors="coerce")
    df["ftag"] = pd.to_numeric(df["ftag"], errors="coerce")
    df = df.dropna(subset=["home", "away", "fthg", "ftag"])
    seasons = sorted(df["season"].unique())

    rows = []
    for i, s in enumerate(seasons):
        if i < min_train_seasons:            # need >= min_train_seasons prior seasons
            continue
        prior = df[df["season"] < s]
        ratings = latest_team_ratings(prior)   # most-recent prior season only (no leak)
        if not ratings:
            continue
        cur = df[df["season"] == s]
        for _, m in cur.iterrows():
            home, away = m["home"], m["away"]
            la = ratings.get(home, {}).get("league_avg")
            probs = (predict_3way(home, away, ratings, league_avg=la) if la
                     else predict_3way(home, away, ratings))
            if probs is None:                # either club lacks a data-backed rating
                continue
            side = "home" if probs["p_home"] >= probs["p_away"] else "away"  # never draw
            subject = home if side == "home" else away
            home_pts, away_pts = float(m["fthg"]), float(m["ftag"])
            result = grade_team_pick(
                {"market_family": "moneyline", "side": side, "line": None}, home_pts, away_pts)
            row = {
                "sport": "soccer", "game_date": str(pd.Timestamp(m["date"]).date()),
                "market_family": "moneyline", "subject": subject, "side": side,
                "line": None, "stat": None, "odds_american": None, "edge": None,
                "result": result, "units": float("nan"), "source": SEED_SOURCE,
            }
            # Predicted scores from the Poisson lambdas (expected goals), when present.
            lh, lawy = probs.get("lambda_home"), probs.get("lambda_away")
            if lh is not None and lawy is not None:
                row["pred_home_pts"] = round(float(lh), 1)
                row["pred_away_pts"] = round(float(lawy), 1)
                row["home_pts_err"] = round(abs(float(lh) - home_pts), 2)
                row["away_pts_err"] = round(abs(float(lawy) - away_pts), 2)
            rows.append(row)
    return pd.DataFrame(rows)


def write_seed(preds: pd.DataFrame) -> int:
    """Grade + append seed rows to the results ledger (idempotent). Returns #added."""
    return append_ledger(build_seed_rows(preds))


def write_soccer_seed(matches: pd.DataFrame, *, min_train_seasons: int = 1) -> int:
    """Build + append soccer seed rows to the results ledger (idempotent). Returns #added."""
    return append_ledger(build_soccer_seed_rows(matches, min_train_seasons=min_train_seasons))
