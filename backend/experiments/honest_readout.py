"""Honest readout — the overfitting canary (ARCHITECTURE §5d).

Evaluates the CURRENT champion on the UNTOUCHED final season (never used for keep/drop
selection), and reports the gap between the selected (train+CV walk-forward) number and
the untouched-test number — a widening gap is the monitored (and postable) overfitting
signal. Also reports the cumulative multiple-comparisons exposure (experiments run vs
kept). Reuses walk_forward_backtest: the holdout season's row is produced by a model
trained on all prior (train+CV) seasons.

Usage:  python -m experiments.honest_readout --sport nfl
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import logging

from backtest.team_backtest import _season_label, walk_forward_backtest
from experiments import ledger
from experiments.champion import load_champion
from experiments.eval_champion import DETERMINISTIC_PARAMS, _build_frame, _pick_holdout

logger = logging.getLogger(__name__)


def honest_readout(sport: str, *, start: int, end: int) -> dict:
    champ = load_champion(sport)
    frame = _build_frame(sport, start, end, champ.feature_cols)
    frame["season"] = frame["season"].astype(int)
    holdout = _pick_holdout(frame)

    # Walk-forward over the FULL frame; the holdout season is predicted by a model
    # trained on every prior (train+CV) season — the honest untouched-test number.
    bt = walk_forward_backtest(frame, sport=sport, feature_cols=champ.feature_cols,
                               params=DETERMINISTIC_PARAMS)
    # Match the holdout row by the sport's own season label — two-year sports
    # (NHL/NBA) label 2025 as "2025-26", so str(holdout) would never match.
    row = bt[bt["season"] == _season_label(sport, holdout)]
    untouched = row.iloc[0].to_dict() if not row.empty else {}
    selected = champ.cumulative_metrics or {}

    def gap(k):
        u, s = untouched.get(k), selected.get(k)
        return round(u - s, 4) if (u is not None and s is not None) else None

    return {
        "champion": champ.model_version, "rung": champ.rung, "holdout_season": holdout,
        "untouched_test": {k: untouched.get(k) for k in ("n", "su_acc", "winner_logloss", "margin_mae", "total_mae")},
        "selected_traincv": {k: selected.get(k) for k in ("su_acc", "winner_logloss", "margin_mae", "total_mae")},
        "gap_untouched_minus_selected": {k: gap(k) for k in ("su_acc", "winner_logloss", "margin_mae")},
        "multiple_comparisons": ledger.counts(sport),
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(description="Honest readout on the untouched test season.")
    ap.add_argument("--sport", default="nfl")
    ap.add_argument("--start", type=int, default=1999)
    ap.add_argument("--end", type=int, default=dt.date.today().year)
    args = ap.parse_args()
    r = honest_readout(args.sport, start=args.start, end=args.end)
    u, s, g, mc = (r["untouched_test"], r["selected_traincv"],
                   r["gap_untouched_minus_selected"], r["multiple_comparisons"])
    print(f"\n=== HONEST READOUT — {r['champion']} (Rung {r['rung']}) ===")
    print(f"untouched test season: {r['holdout_season']}  (N={u.get('n')}) — never used for selection")
    print(f"  {'metric':<16}{'selected(CV)':>14}{'untouched':>12}{'gap':>10}")
    print(f"  {'SU accuracy':<16}{s.get('su_acc'):>14}{u.get('su_acc'):>12}{g.get('su_acc'):>+10}")
    print(f"  {'winner logloss':<16}{s.get('winner_logloss'):>14}{u.get('winner_logloss'):>12}{g.get('winner_logloss'):>+10}")
    print(f"  {'margin MAE':<16}{s.get('margin_mae'):>14}{u.get('margin_mae'):>12}{g.get('margin_mae'):>+10}")
    print(f"multiple-comparisons exposure: {mc['run']} run, {mc['kept']} kept, {mc['dropped']} dropped")
    print("(a large negative SU gap / positive logloss gap = overfitting signal to watch)")


if __name__ == "__main__":
    main()
