"""Honest walk-forward of the SERVING soccer estimator (latest_team_ratings).

The standard soccer backtest measures the add_team_features path. The served
predictor instead uses latest_team_ratings, a separate estimator the backtest never
exercises. This simulates production: for each match in a test season, build ratings
from ONLY the matches strictly before that match's date (leakage-safe), predict 3-way,
and grade log-loss. Compares cross_season OFF vs ON on the identical gated match set.
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np

warnings.filterwarnings("ignore")
BACKEND = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from sports.soccer.team_features import (latest_team_ratings, load_epl_raw,
                                         predict_3way)


def _outcome(h, a):
    return "H" if h > a else ("A" if h < a else "D")


def serving_walk_forward(matches, test_seasons, cross_season):
    m = matches.copy()
    m["date"] = __import__("pandas").to_datetime(m["date"], errors="coerce")
    m = m.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    ll, n, correct = [], 0, 0
    cache = {}  # date -> ratings built from strictly-prior matches
    for _, r in m[m["season"].astype(str).isin([str(s) for s in test_seasons])].iterrows():
        d = r["date"]
        if d not in cache:
            prior = m[m["date"] < d]
            cache[d] = latest_team_ratings(prior, cross_season=cross_season)
        ratings = cache[d]
        la = ratings.get(r["home"], {}).get("league_avg")
        probs = (predict_3way(r["home"], r["away"], ratings, league_avg=la)
                 if la else predict_3way(r["home"], r["away"], ratings))
        if probs is None:
            continue
        o = _outcome(float(r["fthg"]), float(r["ftag"]))
        p = {"H": probs["p_home"], "D": probs["p_draw"], "A": probs["p_away"]}[o]
        ll.append(-np.log(max(p, 1e-15)))
        pick = max(("H", "D", "A"), key=lambda k: {"H": probs["p_home"], "D": probs["p_draw"],
                                                   "A": probs["p_away"]}[k])
        correct += int(pick == o)
        n += 1
    return {"n": n, "logloss": round(float(np.mean(ll)), 4) if ll else None,
            "acc": round(correct / n, 4) if n else None}


if __name__ == "__main__":
    matches = load_epl_raw()
    test_seasons = [2022, 2023, 2024]  # each has a prior season present for the blend
    off = serving_walk_forward(matches, test_seasons, cross_season=False)
    on = serving_walk_forward(matches, test_seasons, cross_season=True)
    print(f"SERVING walk-forward over seasons {test_seasons} (gated matches only)")
    print(f"  cross_season=OFF: {off}")
    print(f"  cross_season=ON : {on}")
    if off["logloss"] and on["logloss"]:
        print(f"  delta logloss (neg=better): {round(on['logloss'] - off['logloss'], 4):+}")
        print(f"  delta acc    (pos=better): {round(on['acc'] - off['acc'], 4):+}")
