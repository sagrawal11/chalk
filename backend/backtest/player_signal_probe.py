#!/usr/bin/env python3
"""ROI probe: can teammate-availability + minutes structure beat the L10 baseline
for player PTS, honestly (train on <2024-25, test on 2024-25)?

Target = PTS - PTS_L10 (the deviation the L10 baseline can't predict). Baseline
MAE = mean|deviation| (i.e., predict deviation 0 = 'just use the L10 average').
If an availability-aware model's holdout MAE beats that baseline, the signal is
worth wiring into the full feature engine + retrain.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from config.paths import PLAYER_DATA_DIR, TEAM_AVAILABILITY_PARQUET
from sports.nba.teams import canonical_team

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

TRAIN_MAX = "2023-24"
HOLDOUT = "2024-25"
FEATS = ["MIN_L10", "MIN_L3", "PTS_L10", "rate_L10", "IS_HOME",
         "TM_OUT_MIN", "TM_OUT_PTS", "TM_OUT_COUNT", "TM_TOP_OUT"]


def _build() -> pd.DataFrame:
    av = pd.read_parquet(TEAM_AVAILABILITY_PARQUET)
    av["game_date"] = pd.to_datetime(av["game_date"])
    frames = []
    for d in sorted(PLAYER_DATA_DIR.iterdir()):
        if not d.is_dir():
            continue
        csv = d / f"{d.name}_data.csv"
        if not csv.exists():
            continue
        try:
            df = pd.read_csv(csv, usecols=["GAME_DATE", "SEASON", "PLAYER_TEAM", "IS_HOME", "MIN", "PTS"])
        except Exception:
            continue
        df["MIN"] = pd.to_numeric(df["MIN"], errors="coerce")
        df = df.dropna(subset=["MIN"])
        df = df[df["MIN"] > 0]
        if len(df) < 20:
            continue
        df = df.sort_values("GAME_DATE").reset_index(drop=True)
        df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"])
        df["PTS"] = pd.to_numeric(df["PTS"], errors="coerce")
        df["IS_HOME"] = pd.to_numeric(df.get("IS_HOME"), errors="coerce").fillna(0).astype(int)
        df["team"] = df["PLAYER_TEAM"].map(lambda t: canonical_team(t, strict=False))
        df["MIN_L10"] = df["MIN"].shift(1).rolling(10, min_periods=5).mean()
        df["MIN_L3"] = df["MIN"].shift(1).rolling(3, min_periods=2).mean()
        df["PTS_L10"] = df["PTS"].shift(1).rolling(10, min_periods=5).mean()
        df["rate_L10"] = (df["PTS"].shift(1).rolling(10, min_periods=5).sum()
                          / df["MIN"].shift(1).rolling(10, min_periods=5).sum())
        df = df[df["SEASON"] >= "2015-16"]
        frames.append(df[["SEASON", "team", "GAME_DATE", "IS_HOME", "MIN", "PTS",
                           "MIN_L10", "MIN_L3", "PTS_L10", "rate_L10"]])
    allp = pd.concat(frames, ignore_index=True)
    allp = allp.merge(av, left_on=["team", "GAME_DATE"], right_on=["team", "game_date"], how="left")
    for c in ["TM_OUT_MIN", "TM_OUT_PTS", "TM_OUT_COUNT", "TM_TOP_OUT"]:
        allp[c] = pd.to_numeric(allp[c], errors="coerce").fillna(0.0)
    allp = allp[(allp["MIN_L10"] >= 8) & allp["PTS_L10"].notna() & allp["rate_L10"].notna()]
    allp["dPTS"] = allp["PTS"] - allp["PTS_L10"]
    return allp


def main() -> None:
    from lightgbm import LGBMRegressor, early_stopping

    df = _build()
    tr = df[df["SEASON"] <= TRAIN_MAX]
    ho = df[df["SEASON"] == HOLDOUT]
    logger.info("train rows=%d  holdout rows=%d", len(tr), len(ho))

    # inner val split (random) for early stopping
    rng = np.random.RandomState(42)
    perm = rng.permutation(len(tr))
    k = int(len(tr) * 0.15)
    va_idx, fit_idx = perm[:k], perm[k:]
    Xtr, ytr = tr[FEATS].fillna(0.0), tr["dPTS"]
    m = LGBMRegressor(n_estimators=2000, learning_rate=0.03, num_leaves=63,
                      min_child_samples=100, subsample=0.8, colsample_bytree=0.8, verbose=-1)
    m.fit(Xtr.iloc[fit_idx], ytr.iloc[fit_idx],
          eval_set=[(Xtr.iloc[va_idx], ytr.iloc[va_idx])],
          callbacks=[early_stopping(100, verbose=False)])

    base_mae = float(ho["dPTS"].abs().mean())                       # predict L10 (dPTS=0)
    logger.info("PTS L10 baseline MAE=%.4f", base_mae)

    no_avail = [f for f in FEATS if not f.startswith("TM_")]
    for label, cols in [("recent-form only", no_avail), ("+ availability", FEATS)]:
        mm = LGBMRegressor(n_estimators=2000, learning_rate=0.03, num_leaves=63,
                           min_child_samples=100, subsample=0.8, colsample_bytree=0.8, verbose=-1)
        mm.fit(Xtr[cols].iloc[fit_idx], ytr.iloc[fit_idx],
               eval_set=[(Xtr[cols].iloc[va_idx], ytr.iloc[va_idx])],
               callbacks=[early_stopping(100, verbose=False)])
        pred_d = mm.predict(ho[cols].fillna(0.0))
        model_mae = float(np.abs(pred_d - ho["dPTS"]).mean())
        logger.info("  %-18s iter=%4s predStd=%.3f  MAE=%.4f  improvement=%+.2f%%",
                    label, mm.best_iteration_, float(np.std(pred_d)), model_mae, (1 - model_mae / base_mae) * 100)
    imp = pd.Series(m.feature_importances_, index=FEATS).sort_values(ascending=False)
    logger.info("top features (+availability model):\n%s", imp.to_string())


if __name__ == "__main__":
    main()
