"""Sweep the soccer HOME_FIELD multiplier on the backtest referee (cross_season ON).

For each candidate home_field, run the honest walk-forward 3-way path
(backtest.soccer_backtest.predict_matches, which is what walk_forward_3way +
summarize_3way aggregate) and report, pooled over all gated 2021-2024 matches:
  3way_logloss (primary), 3way_acc (guard), total_mae, and the calibration means
  pred/obs for H/D/A (what evaluate_soccer_calibration checks).

Pooling all matches == summarize_3way's n-weighted season average for logloss/acc/
total_mae (all are plain means), so this reproduces the referee exactly while also
giving the per-outcome calibration in one pass.

Baseline to beat (cross_season ON, home_field 1.19): 3way_logloss 1.0500, acc 0.5212,
pred_home 0.538 vs obs 0.450 (the +0.088 home bias the calibration pass found).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from backtest.soccer_backtest import predict_matches, three_way_logloss
from sports.soccer.team_features import build_epl_matches

_OUTCOMES = np.array(["H", "D", "A"])


def _row(matches, hf: float) -> dict:
    df = predict_matches(matches, {"cross_season": True, "home_field": hf})
    df = df.dropna(subset=["p_home", "p_draw", "p_away", "outcome"])
    outc = df["outcome"].to_numpy()
    pick = _OUTCOMES[df[["p_home", "p_draw", "p_away"]].to_numpy().argmax(1)]
    tot_act = (df["fthg"] + df["ftag"]).to_numpy()
    return {
        "home_field": hf,
        "n": int(len(df)),
        "logloss": round(three_way_logloss(outc, df["p_home"], df["p_draw"], df["p_away"]), 4),
        "acc": round(float((pick == outc).mean()), 4),
        "total_mae": round(float(np.mean(np.abs(df["pred_total"].to_numpy() - tot_act))), 3),
        "pred_H": round(float(df["p_home"].mean()), 3),
        "obs_H": round(float((outc == "H").mean()), 3),
        "pred_D": round(float(df["p_draw"].mean()), 3),
        "obs_D": round(float((outc == "D").mean()), 3),
        "pred_A": round(float(df["p_away"].mean()), 3),
        "obs_A": round(float((outc == "A").mean()), 3),
    }


def main() -> None:
    matches = build_epl_matches()
    grid = [1.19, 1.15, 1.10, 1.05, 1.00, 0.95, 0.90, 0.85, 0.80]
    rows = [_row(matches, hf) for hf in grid]
    hdr = ("hf", "n", "logloss", "acc", "tot_mae", "predH", "obsH", "predD", "obsD", "predA", "obsA")
    print("  ".join(f"{h:>8}" for h in hdr))
    for r in rows:
        print("  ".join(f"{v:>8}" for v in (
            r["home_field"], r["n"], r["logloss"], r["acc"], r["total_mae"],
            r["pred_H"], r["obs_H"], r["pred_D"], r["obs_D"], r["pred_A"], r["obs_A"])))
    best = min(rows, key=lambda r: r["logloss"])
    print(f"\nbest logloss: home_field={best['home_field']} -> {best['logloss']} (acc {best['acc']})")


if __name__ == "__main__":
    main()
