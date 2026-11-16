#!/usr/bin/env python3
"""Honest reliability check for the NHL skater prop (v2 anchored) models.

Same question as the NFL/NBA/CFB player backtests: on a held-out slice the model
never trained on, does the anchored LightGBM layer beat the naive baseline a fan
uses for free (predict the skater's trailing-5-game average, the anchor)?

Only two skater seasons are cached (2023-24), so ``walk_forward_train`` uses its
degenerate temporal-80/20 path (no season-level CV). This backtest reproduces
THAT split exactly - gate the frame, order by date, hold out the last 20% - then
fits the identical deterministic eval-model on the first 80% and scores the
holdout. Because the split and params match the trainer, ``model`` here reproduces
the served model's stored ``holdout_mae``; the point is to measure the L5/L10
baselines on the SAME rows (the trainer's inline skill used a full-sample baseline
because the degenerate path reports ``holdout_season=None``), so model-vs-baseline
is finally apples-to-apples. Skill = 1 - model/last-5; positive means the ML
adjustment earns its place.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from model_training.train_nhl_skater_model import PARAMS
from model_training.validation import _inner_split  # same deterministic inner split
from sports.nhl.skater_features import (FEATURE_COLS, MIN_PRIOR_GAMES,
                                        PROP_TARGETS, build_skater_frame)

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def _mae(a, b) -> float:
    return float((pd.to_numeric(a, errors="coerce") - pd.to_numeric(b, errors="coerce")).abs().mean())


def main() -> None:
    from lightgbm import LGBMRegressor, early_stopping

    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=2023)
    ap.add_argument("--end", type=int, default=2024)
    ap.add_argument("--holdout-frac", type=float, default=0.2)
    args = ap.parse_args()

    frame = build_skater_frame(range(args.start, args.end + 1))
    frame = frame[frame["_n_prior"] >= MIN_PRIOR_GAMES].reset_index(drop=True)
    frame = frame.sort_values("date", kind="stable").reset_index(drop=True)
    split = int(len(frame) * (1.0 - args.holdout_frac))
    hold = frame.iloc[split:]
    logger.info("NHL skater backtest - temporal 80/20 on %d gated games (%d-%d), "
                "holdout last %d\n", len(frame), args.start, args.end, len(hold))

    hdr = f"{'prop':<10}{'n_hold':>8}{'model':>9}{'last-5':>9}{'last-10':>10}{'skill vs L5':>13}"
    logger.info(hdr)
    logger.info("-" * len(hdr))

    # Diagnostic: probe each prop with a last-5-anchored model vs the last-5 and
    # last-10 naive baselines on the holdout. This is why shots is served with a
    # model and points is served naive (its last-10): shots' model beats both
    # baselines, points' model loses to the last-10 average.
    X = frame[FEATURE_COLS].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    for t in PROP_TARGETS:
        anchor = pd.to_numeric(frame[f"{t}_L5"], errors="coerce").fillna(0.0)
        y_adj = pd.to_numeric(frame[t], errors="coerce").fillna(0.0) - anchor
        tr = frame.index[:split]
        fit_idx, val_idx = _inner_split(pd.Index(tr), None, 0.15)
        model = LGBMRegressor(**PARAMS)
        model.fit(X.loc[fit_idx], y_adj.loc[fit_idx],
                  eval_set=[(X.loc[val_idx], y_adj.loc[val_idx])],
                  callbacks=[early_stopping(100, verbose=False)])
        pred = anchor.iloc[split:].to_numpy() + model.predict(X.iloc[split:])

        model_mae = _mae(hold[t], pred)
        base_l5 = _mae(hold[t], hold[f"{t}_L5"])          # predict trailing-5 avg
        base_l10 = _mae(hold[t], hold[f"{t}_L10"])        # predict trailing-10 avg
        skill = (1.0 - model_mae / base_l5) * 100.0 if base_l5 else 0.0
        logger.info(f"{t:<10}{len(hold):>8}{model_mae:>9.3f}{base_l5:>9.3f}{base_l10:>10.3f}{skill:>12.1f}%")


if __name__ == "__main__":
    main()
