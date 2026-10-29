"""Turn walk-forward predictions into graded ledger rows for the public track record.

Each game is graded straight-up (did the model's favored side win) plus predicted-score
error. No betting: the metrics are winner accuracy + predicted-score MAE.
"""
from __future__ import annotations

import pandas as pd

from track_record.grade import append_ledger

SEED_SOURCE = "seed_backtest"


def _winner_result(side: str, home_pts: float, away_pts: float) -> str:
    """'win' iff the picked side matches the actual winner; a tie is a loss."""
    m = home_pts - away_pts
    if m == 0:
        return "loss"
    return "win" if (side == "home") == (m > 0) else "loss"


def build_seed_rows(preds: pd.DataFrame) -> pd.DataFrame:
    """``preds``: per-game frame (sport, game_date, home, away, mu_margin, pred/actual
    home/away pts). Returns ledger-schema rows graded on winner + predicted score."""
    if preds is None or preds.empty:
        return pd.DataFrame()
    rows = []
    for _, r in preds.iterrows():
        home_pts, away_pts = float(r["actual_home_pts"]), float(r["actual_away_pts"])
        pred_home, pred_away = float(r["pred_home_pts"]), float(r["pred_away_pts"])
        side = "home" if float(r["mu_margin"]) >= 0 else "away"
        subject = r["home"] if side == "home" else r["away"]
        rows.append({
            "sport": r["sport"], "game_date": str(r["game_date"])[:10],
            "home": r["home"], "away": r["away"], "subject": subject, "side": side,
            "result": _winner_result(side, home_pts, away_pts),
            "pred_home_pts": round(pred_home, 1), "pred_away_pts": round(pred_away, 1),
            "home_pts_err": round(abs(pred_home - home_pts), 2),
            "away_pts_err": round(abs(pred_away - away_pts), 2),
            "source": SEED_SOURCE,
        })
    return pd.DataFrame(rows)


def build_soccer_seed_rows(matches: pd.DataFrame, *, min_train_seasons: int = 1
                           ) -> pd.DataFrame:
    """Season-level leakage-safe walk-forward for the Poisson (Dixon-Coles-lite) soccer
    model -> graded ledger rows.

    ``matches``: tidy EPL frame (season/date/home/away/fthg/ftag). For each season S with
    >= ``min_train_seasons`` prior seasons, team ratings are built from matches BEFORE S
    only, every match in S is predicted via ``predict_3way``, and the MORE-LIKELY of
    home/away is the favored side (never a draw). A draw grades as a loss for the picked
    side. Matches whose teams lack data-backed ratings are skipped. Predicted scores come
    from the Poisson lambdas (expected goals)."""
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
        if i < min_train_seasons:
            continue
        prior = df[df["season"] < s]
        ratings = latest_team_ratings(prior)
        if not ratings:
            continue
        cur = df[df["season"] == s]
        for _, m in cur.iterrows():
            home, away = m["home"], m["away"]
            la = ratings.get(home, {}).get("league_avg")
            probs = (predict_3way(home, away, ratings, league_avg=la) if la
                     else predict_3way(home, away, ratings))
            if probs is None:
                continue
            side = "home" if probs["p_home"] >= probs["p_away"] else "away"
            subject = home if side == "home" else away
            home_pts, away_pts = float(m["fthg"]), float(m["ftag"])
            row = {
                "sport": "soccer", "game_date": str(pd.Timestamp(m["date"]).date()),
                "home": home, "away": away, "subject": subject, "side": side,
                "result": _winner_result(side, home_pts, away_pts), "source": SEED_SOURCE,
            }
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
