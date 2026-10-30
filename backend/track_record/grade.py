"""Grade a locked slate against actual final scores and append to the results ledger.

Each locked game prediction is graded on two honest things: did the model's favored
side win straight-up, and how far off was the predicted score (per-side absolute
error). No betting: no lines, no odds, no units.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

import pandas as pd

from config.paths import DATA_DIR
from track_record.lock import load_lock

logger = logging.getLogger(__name__)
RESULTS_LEDGER = DATA_DIR / "predictions" / "results_ledger.parquet"
PROP_RESULTS_LEDGER = DATA_DIR / "predictions" / "prop_results_ledger.parquet"


def grade_game(pred: Dict[str, Any], home_pts: float, away_pts: float) -> Dict[str, Any]:
    """Grade one locked GamePrediction dict against the final score. The predicted
    winner is the favored side (mu_margin sign). A tie grades as a loss (neither side
    won straight-up)."""
    pred_side = "home" if float(pred["mu_margin"]) >= 0 else "away"
    actual_margin = home_pts - away_pts
    if actual_margin == 0:
        result = "loss"
    else:
        result = "win" if (pred_side == "home") == (actual_margin > 0) else "loss"
    ph, pa = float(pred["pred_home_pts"]), float(pred["pred_away_pts"])
    return {
        "side": pred_side,
        "result": result,
        "pred_home_pts": round(ph, 1),
        "pred_away_pts": round(pa, 1),
        "home_pts_err": round(abs(ph - home_pts), 2),
        "away_pts_err": round(abs(pa - away_pts), 2),
    }


def _game_key(sport: str, game_date: str, pred: Dict[str, Any]) -> str:
    return f"{sport}:{game_date}:{pred['away']}@{pred['home']}"


def grade_date(
    sport: str,
    game_date: str,
    team_outcomes: Dict[str, Dict[str, float]],
) -> pd.DataFrame:
    """Grade a locked slate's game predictions against final scores. ``team_outcomes``
    maps ``"{sport}:{date}:{away}@{home}"`` -> {home_pts, away_pts}. Games without a
    known outcome are skipped."""
    doc = load_lock(sport, game_date)
    rows = []
    for gp in doc.get("game_predictions", []):
        o = team_outcomes.get(_game_key(sport, game_date, gp))
        if not o:
            continue
        g = grade_game(gp, float(o["home_pts"]), float(o["away_pts"]))
        subject = gp["home"] if g["side"] == "home" else gp["away"]
        rows.append({
            "sport": sport, "game_date": game_date,
            "home": gp["home"], "away": gp["away"], "subject": subject,
            **g, "source": "live",
        })
    return pd.DataFrame(rows)


def _upsert(df: pd.DataFrame, path, key: list) -> int:
    """Idempotent append: concat with any existing ledger, de-dupe on ``key``
    (keep latest), rewrite. Returns net rows added."""
    if df is None or df.empty:
        return 0
    if path.exists():
        old = pd.read_parquet(path)
        n_old = len(old)
        combined = pd.concat([old, df], ignore_index=True)
    else:
        n_old = 0
        combined = df
    combined = combined.drop_duplicates(subset=key, keep="last")
    path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_parquet(path, index=False)
    return len(combined) - n_old


def append_ledger(df: pd.DataFrame) -> int:
    return _upsert(df, RESULTS_LEDGER, ["sport", "game_date", "home", "away"])


# --------------------------------------------------------------------------- #
# Player props: grade each projected stat against the real box-score value.    #
# No line, no over/under: just the predicted number vs the actual number.      #
# --------------------------------------------------------------------------- #
def grade_prop(pred: Dict[str, Any], actual: float) -> Dict[str, Any]:
    """Grade one locked PlayerPropPrediction dict against the real stat value:
    the signed and absolute error of the projected stat."""
    mu, actual = float(pred["mu"]), float(actual)
    return {
        "pred": round(mu, 2),
        "actual": round(actual, 2),
        "err": round(mu - actual, 2),
        "abs_err": round(abs(mu - actual), 2),
    }


def _prop_key(pred: Dict[str, Any]) -> str:
    return f"{pred['player_slug']}:{pred['stat']}"


def grade_props_date(
    sport: str,
    game_date: str,
    actuals: Dict[str, float],
) -> pd.DataFrame:
    """Grade a locked slate's prop predictions against actual stat values.
    ``actuals`` maps ``"{player_slug}:{stat}"`` -> the real stat value; props
    without a known actual are skipped."""
    doc = load_lock(sport, game_date)
    rows = []
    for pp in doc.get("prop_predictions", []):
        a = actuals.get(_prop_key(pp))
        if a is None:
            continue
        rows.append({
            "sport": sport, "game_date": game_date,
            "player_slug": pp["player_slug"], "player_name": pp.get("player_name", ""),
            "stat": pp["stat"], **grade_prop(pp, a), "source": "live",
        })
    return pd.DataFrame(rows)


def append_prop_ledger(df: pd.DataFrame) -> int:
    return _upsert(df, PROP_RESULTS_LEDGER, ["sport", "game_date", "player_slug", "stat"])
