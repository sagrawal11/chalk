"""Walk-forward 3-way (1X2) backtest for the soccer Poisson champion.

Soccer breaks the binary margin-sign harness: a draw is a real outcome (~25% of
matches), and the market-blind champion is the parametric Poisson team-strength
model (``sports.soccer.team_features``), not a LightGBM margin regressor. So soccer
gets its own honest eval here: for each match, predict 1X2 from that team's
PRIOR-only ratings (leakage-safe within season; optional cross-season prior), then
grade three-way log-loss (primary), three-way accuracy, total-goals MAE, and draw
calibration. Still market-blind: the betting line is never an input.

Reused by ``experiments.soccer`` (champion/challenger) exactly the way the binary
sports reuse ``team_backtest.walk_forward_backtest``.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from sports.soccer.team_features import add_team_features, three_way_from_lambdas

# The soccer-v1 baseline Poisson params; each experiment overrides individual keys.
BASELINE_PARAMS: Dict[str, Any] = {
    "roll": 6, "home_field": 1.19, "min_prior": 3, "max_goals": 10,
    "dixon_coles": False, "dc_rho": -0.13, "cross_season": False,
}
_OUTCOMES = np.array(["H", "D", "A"])


def _outcome(fthg: float, ftag: float) -> str:
    return "H" if fthg > ftag else ("A" if fthg < ftag else "D")


def three_way_logloss(outcomes, p_home, p_draw, p_away) -> float:
    """Mean −log(prob assigned to the ACTUAL outcome) over H/D/A, the primary
    soccer metric (lower is better), the 3-way analog of winner_logloss."""
    cols = {"H": np.clip(np.asarray(p_home, float), 1e-15, 1.0),
            "D": np.clip(np.asarray(p_draw, float), 1e-15, 1.0),
            "A": np.clip(np.asarray(p_away, float), 1e-15, 1.0)}
    outcomes = list(outcomes)
    if not outcomes:
        return float("nan")
    ll = [-np.log(cols[o][i]) for i, o in enumerate(outcomes)]
    return float(np.mean(ll))


def predict_matches(matches: pd.DataFrame, params: Optional[dict] = None) -> pd.DataFrame:
    """Attach 1X2 probs + predicted total to each gated match, from prior-only
    ratings built with the given params (market-blind)."""
    p = {**BASELINE_PARAMS, **(params or {})}
    df = add_team_features(matches, roll=int(p["roll"]), cross_season=bool(p["cross_season"]))
    if df.empty:
        return df
    df = df.copy()
    df["fthg"] = pd.to_numeric(df["fthg"], errors="coerce")
    df["ftag"] = pd.to_numeric(df["ftag"], errors="coerce")
    gate = (df["home_n_prior"] >= p["min_prior"]) & (df["away_n_prior"] >= p["min_prior"])
    df = df[gate].dropna(subset=["fthg", "ftag"]).reset_index(drop=True)
    if df.empty:
        return df
    la = df["league_avg"].astype(float).to_numpy()
    hf = float(p["home_field"])
    lam_h = np.clip(df["home_attack"].to_numpy() * df["away_defense"].to_numpy() * hf * la, 0.05, 6.0)
    lam_a = np.clip(df["away_attack"].to_numpy() * df["home_defense"].to_numpy() * la, 0.05, 6.0)
    rho = float(p["dc_rho"]) if p["dixon_coles"] else 0.0
    mg = int(p["max_goals"])
    ph: List[float] = []
    pdr: List[float] = []
    pa: List[float] = []
    for lh, laa in zip(lam_h, lam_a):
        pr = three_way_from_lambdas(float(lh), float(laa), mg, dixon_coles_rho=rho)
        ph.append(pr["p_home"]); pdr.append(pr["p_draw"]); pa.append(pr["p_away"])
    df["p_home"], df["p_draw"], df["p_away"] = ph, pdr, pa
    df["pred_total"] = lam_h + lam_a
    df["outcome"] = [_outcome(h, a) for h, a in zip(df["fthg"], df["ftag"])]
    return df


def walk_forward_3way(matches: pd.DataFrame, params: Optional[dict] = None) -> pd.DataFrame:
    """Per-season 3-way metrics. Each match is predicted from its team's prior-only
    ratings (honest by construction): there is no cross-season fit, so the eval
    simply grades every gated match and aggregates by season."""
    df = predict_matches(matches, params)
    if df.empty:
        return pd.DataFrame()
    df["season"] = df["season"].astype(int)
    rows = []
    for s, sdf in df.groupby("season"):
        outc = sdf["outcome"].to_numpy()
        ll = three_way_logloss(outc, sdf["p_home"], sdf["p_draw"], sdf["p_away"])
        pick = _OUTCOMES[sdf[["p_home", "p_draw", "p_away"]].to_numpy().argmax(1)]
        tot_act = (sdf["fthg"] + sdf["ftag"]).to_numpy()
        rows.append({
            "season": int(s), "n": int(len(sdf)),
            "three_way_logloss": round(ll, 4),
            "three_way_acc": round(float((pick == outc).mean()), 4),
            "total_mae": round(float(np.mean(np.abs(sdf["pred_total"].to_numpy() - tot_act))), 3),
            "draw_pred": round(float(sdf["p_draw"].mean()), 4),
            "draw_act": round(float((outc == "D").mean()), 4),
        })
    return pd.DataFrame(rows)


def summarize_3way(bt: pd.DataFrame) -> Dict[str, Any]:
    if bt is None or bt.empty:
        return {}
    n = float(bt["n"].sum())
    wavg = lambda c: round(float((bt[c] * bt["n"]).sum() / n), 4)
    return {
        "seasons": int(len(bt)), "games": int(n),
        "three_way_logloss": wavg("three_way_logloss"),
        "three_way_acc": wavg("three_way_acc"),
        "total_mae": round(float((bt["total_mae"] * bt["n"]).sum() / n), 3),
        "draw_pred": wavg("draw_pred"), "draw_act": wavg("draw_act"),
    }
