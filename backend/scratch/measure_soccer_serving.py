"""Production-simulating walk-forward on the SERVED soccer estimator.

The backtest referee (backtest.soccer_backtest) grades the rolling add_team_features
path. The SERVED predictor instead uses latest_team_ratings (most-recent actual
games, cross_season blend) + predict_3way -- a different estimator, the drift the
soccer memory warned about. This script grades THAT path honestly: for each match
(seasons >= 2022, so a cross-season prior exists), build ratings from strictly-prior
matches only, predict 1X2 with predict_3way, and grade 3-way log-loss + accuracy.

Baseline reference (cross_season ON, home_field 1.19): serving 3way_logloss ~1.0579,
acc ~0.5262 over the gated n~956. Pass home_field to compare the home-bias fix.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from sports.soccer.team_features import HOME_FIELD, latest_team_ratings, predict_3way
from sports.soccer.team_features import load_epl_raw
import pandas as pd

_OUTCOMES = np.array(["H", "D", "A"])


def _outcome(h, a) -> str:
    return "H" if h > a else ("A" if h < a else "D")


def measure(hf: float, eval_from_season: int = 2022) -> dict:
    df = load_epl_raw()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date", "fthg", "ftag"]).sort_values("date").reset_index(drop=True)
    outc, ph, pdw, pa = [], [], [], []
    for _, m in df.iterrows():
        if int(m["season"]) < eval_from_season:
            continue
        prior = df[df["date"] < m["date"]]
        if prior.empty:
            continue
        ratings = latest_team_ratings(prior, cross_season=True)
        la = ratings.get(m["home"], {}).get("league_avg")
        probs = (predict_3way(m["home"], m["away"], ratings, league_avg=la, home_field=hf)
                 if la else predict_3way(m["home"], m["away"], ratings, home_field=hf))
        if probs is None:  # usage gate: a team lacks min_prior games -> served falls back, skip
            continue
        outc.append(_outcome(m["fthg"], m["ftag"]))
        ph.append(probs["p_home"]); pdw.append(probs["p_draw"]); pa.append(probs["p_away"])
    outc = np.array(outc)
    ph, pdw, pa = np.array(ph), np.array(pdw), np.array(pa)
    ll_idx = {"H": ph, "D": pdw, "A": pa}
    ll = float(np.mean([-np.log(max(1e-15, ll_idx[o][i])) for i, o in enumerate(outc)]))
    pick = _OUTCOMES[np.vstack([ph, pdw, pa]).T.argmax(1)]
    return {"home_field": hf, "n": int(len(outc)), "logloss": round(ll, 4),
            "acc": round(float((pick == outc).mean()), 4),
            "pred_H": round(float(ph.mean()), 3), "obs_H": round(float((outc == "H").mean()), 3)}


if __name__ == "__main__":
    for hf in (1.19, HOME_FIELD):
        r = measure(hf)
        print(f"home_field={r['home_field']:<5} n={r['n']} logloss={r['logloss']} "
              f"acc={r['acc']} pred_H={r['pred_H']} obs_H={r['obs_H']}")
