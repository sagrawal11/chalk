"""The feature-experiment runner (ARCHITECTURE §5d) — the M2 centerpiece.

Pops the next pre-registered experiment (or a given --id), assembles a challenger
(champion's builders + this experiment's builder), runs the EXISTING walk-forward
backtest (backtest/team_backtest) for champion (cached) + challenger on TRAIN+CV only,
computes Δ metrics, applies the PRE-REGISTERED keep-rule, records the result to the
ledger REGARDLESS of outcome (duds are content), and — if kept — promotes: bump
model_version, rewrite champion.json, optionally refit the shipped model. Returns a
structured ExperimentResult (the input to the M3 feature-post generator).

Reuses walk_forward_backtest — it does NOT re-implement evaluation.

Usage:
    python -m experiments.run_experiment --sport nfl --write          # next queued
    python -m experiments.run_experiment --sport nfl --id NFL-10 --write --refit
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import logging

from experiments import ledger, roadmap
from experiments.champion import (ChampionConfig, bump_version, load_champion,
                                   resolve_feature_cols, save_champion)
from experiments.eval_champion import backtest_feature_set

logger = logging.getLogger(__name__)


def _decide(champ_m: dict, chal_m: dict, rule: dict):
    """Apply the pre-registered keep-rule. Returns (decision, primary_delta, guard_ok)."""
    metric = rule.get("metric", "winner_logloss")
    lower = rule.get("improve", "lower") == "lower"
    cv, hv = champ_m.get(metric), chal_m.get(metric)
    if cv is None or hv is None:
        return "drop", None, False
    delta = (cv - hv) if lower else (hv - cv)          # positive = challenger better
    passed = delta >= float(rule.get("min_delta", 0.0))
    guard_ok = True
    gm = rule.get("guard_metric")
    if gm and champ_m.get(gm) is not None and chal_m.get(gm) is not None:
        guard_ok = (chal_m[gm] <= champ_m[gm]) if rule.get("guard_improve", "lower") == "lower" \
            else (chal_m[gm] >= champ_m[gm])
    return ("keep" if passed and guard_ok else "drop"), round(delta, 4), guard_ok


def _pick(champ_m: dict, keys=("su_acc", "winner_logloss", "margin_mae", "total_mae")):
    return {k: champ_m.get(k) for k in keys}


def run_experiment(sport: str, *, exp_id=None, start: int, end: int,
                   write: bool = False, refit: bool = False) -> dict:
    rm = roadmap.load_roadmap()
    champ = load_champion(sport)
    exp = (roadmap.get_experiment(rm, sport, exp_id) if exp_id
           else roadmap.next_unrun(rm, sport, ledger.run_ids(sport)))
    if exp is None:
        raise SystemExit(f"[{sport}] no experiment to run (queue empty or all run)")
    if exp.get("status") == "needs_builder":
        raise SystemExit(f"[{sport}] {exp['id']} needs a feature-builder first (not buildable from the cached frame)")

    rule = roadmap.keep_rule_for(rm, sport, exp)
    added = [b for b in exp["builders"] if b not in champ.active_feature_builders]
    chal_builders = list(champ.active_feature_builders) + added
    chal_cols = resolve_feature_cols(sport, chal_builders)

    # Champion metrics: reuse the cached (identical-window) numbers if present, else compute.
    if champ.cumulative_metrics and "winner_logloss" in champ.cumulative_metrics:
        champ_m, champ_window = champ.cumulative_metrics, champ.eval_window
    else:
        cr = backtest_feature_set(sport, champ.feature_cols, start=start, end=end)
        champ_m, champ_window = cr["metrics"], cr["eval_window"]

    chal = backtest_feature_set(sport, chal_cols, start=start, end=end)
    chal_m = chal["metrics"]

    decision, primary_delta, guard_ok = _decide(champ_m, chal_m, rule)
    challenger_version = bump_version(champ.model_version)

    result = {
        "id": exp["id"], "sport": sport, "rung": exp.get("rung"), "name": exp.get("name"),
        "run_at": dt.datetime.now().isoformat(timespec="seconds"),
        "champion_version": champ.model_version,
        "challenger_version": challenger_version,
        "builder_added": added,
        "eval_window": chal["eval_window"], "n_games": chal_m.get("games"),
        "champion_metrics": _pick(champ_m), "challenger_metrics": _pick(chal_m),
        "delta_accuracy": round((chal_m.get("su_acc") or 0) - (champ_m.get("su_acc") or 0), 4),
        "delta_logloss": round((chal_m.get("winner_logloss") or 0) - (champ_m.get("winner_logloss") or 0), 4),
        "delta_mae": round((chal_m.get("margin_mae") or 0) - (champ_m.get("margin_mae") or 0), 3),
        "keep_rule": rule, "primary_delta": primary_delta, "decision": decision,
        "act": exp.get("act"), "hypothesis": exp.get("hypothesis"),
    }

    if write:
        ledger.append_result(result)
    if decision == "keep":
        promoted = ChampionConfig.new(
            sport, challenger_version, max(champ.rung, int(exp.get("rung", champ.rung))),
            chal_builders, cumulative_metrics={**chal_m, "eval_window": chal["eval_window"],
                                               "measured_at": dt.date.today().isoformat()},
            holdout_season=chal["holdout_season"], eval_window=chal["eval_window"],
            created_at=dt.date.today().isoformat(),
            notes=f"Promoted from {champ.model_version} by {exp['id']} ({exp.get('name')}).")
        result["promoted_to"] = challenger_version
        if write:
            save_champion(promoted)
            if refit:
                from experiments.eval_champion import _refit_shipped
                _refit_shipped(promoted, start=start, end=end)
    return result


def _print(r: dict) -> None:
    cm, hm = r["champion_metrics"], r["challenger_metrics"]
    verdict = "KEEP  -> " + r.get("promoted_to", "") if r["decision"] == "keep" else "DROP (champion unchanged)"
    print(f"\n=== EXPERIMENT {r['id']} — {r['name']} (Rung {r['rung']}, act {r['act']}) ===")
    print(f"TESTED : {r['hypothesis']}")
    print(f"champion {r['champion_version']}  vs  challenger {r['challenger_version']}  (+{r['builder_added']})")
    print(f"eval window {r['eval_window']} · N={r['n_games']}")
    print(f"  {'metric':<16}{'champion':>12}{'challenger':>12}{'delta':>10}")
    print(f"  {'SU accuracy':<16}{cm.get('su_acc'):>12}{hm.get('su_acc'):>12}{r['delta_accuracy']:>+10}")
    print(f"  {'winner logloss':<16}{cm.get('winner_logloss'):>12}{hm.get('winner_logloss'):>12}{r['delta_logloss']:>+10}")
    print(f"  {'margin MAE':<16}{cm.get('margin_mae'):>12}{hm.get('margin_mae'):>12}{r['delta_mae']:>+10}")
    kr = r["keep_rule"]
    print(f"keep-rule (pre-registered): {kr.get('metric')} must improve by >= {kr.get('min_delta')} "
          f"and {kr.get('guard_metric')} must not worsen")
    print(f"RESULT : {verdict}")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(description="Run one pre-registered feature experiment.")
    ap.add_argument("--sport", default="nfl")
    ap.add_argument("--id", default=None, help="specific experiment id (else next queued)")
    ap.add_argument("--start", type=int, default=1999)
    ap.add_argument("--end", type=int, default=dt.date.today().year)
    ap.add_argument("--write", action="store_true", help="persist to the ledger + promote a kept challenger")
    ap.add_argument("--refit", action="store_true", help="on a keep, also refit the shipped model")
    args = ap.parse_args()
    if args.sport == "soccer":   # 3-way Poisson path (different model + metric)
        from experiments import soccer as soccer_exp
        return soccer_exp.run_cli(args)
    r = run_experiment(args.sport, exp_id=args.id, start=args.start, end=args.end,
                       write=args.write, refit=args.refit)
    _print(r)
    if args.write:
        print(f"\nledger += {r['id']} ({r['decision']}); "
              + (f"champion -> {r.get('promoted_to')}" if r["decision"] == "keep" else "champion unchanged"))


if __name__ == "__main__":
    main()
