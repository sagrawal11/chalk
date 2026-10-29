"""Soccer 3-way (1X2) champion/challenger path: the Poisson analog of the binary
harness. Reuses the ChampionConfig schema, the append-only ledger, and the
pre-registered roadmap; swaps in the 3-way Poisson eval (backtest.soccer_backtest)
because soccer's outcome (H/D/A) and champion model (parametric Poisson, not a
LightGBM margin regressor) both differ from the other sports.

Market-blind: a soccer champion is a set of Poisson MODEL PARAMS; the betting line
is never one of them. The two shared CLIs (eval_champion / run_experiment /
honest_readout) delegate here when --sport soccer, so the UX is identical.

    python -m experiments.eval_champion  --sport soccer --seed
    python -m experiments.eval_champion  --sport soccer --write
    python -m experiments.run_experiment --sport soccer --id SOC-02 --write
    python -m experiments.honest_readout --sport soccer
"""
from __future__ import annotations

import datetime as dt
from typing import Optional

from backtest.soccer_backtest import summarize_3way, walk_forward_3way
from experiments import ledger, roadmap
from experiments.champion import (ChampionConfig, bump_version, load_champion,
                                  resolve_model_params, save_champion)
from experiments.run_experiment import _decide
from sports.soccer.team_features import load_epl_raw

SEASONS = (2021, 2022, 2023, 2024)
_METRIC_KEYS = ("three_way_logloss", "three_way_acc", "total_mae", "draw_pred", "draw_act")

_SEED = dict(
    model_version="soccer-v1", rung=1,
    active_feature_builders=["SOC-01"],
    notes="Day-1 soccer champion (M7): baseline independent-Poisson team-strength "
          "3-way model (EPL, market-blind). Soccer is the most efficient market of "
          "all: the widest blind-vs-market gap, and draws make it genuinely 3-way.",
)


def _eval_params(params: dict, seasons=SEASONS) -> dict:
    """Walk-forward 3-way over TRAIN+CV seasons only; the most recent season is held
    UNTOUCHED (never in the selection window), exactly like the binary harness."""
    raw = load_epl_raw(seasons)
    present = sorted(int(s) for s in raw["season"].dropna().astype(int).unique())
    holdout = int(max(present)) if present else None
    traincv = raw[raw["season"].astype(int) < holdout].copy() if holdout else raw
    bt = walk_forward_3way(traincv, params)
    labels = [int(s) for s in bt["season"].tolist()] if not bt.empty else []
    return {
        "metrics": summarize_3way(bt),
        "per_season": bt.to_dict(orient="records"),
        "eval_window": f"{labels[0]}–{labels[-1]}" if labels else None,
        "holdout_season": holdout,
        "n_seasons_available": len(present),
        "final_season_excluded": holdout not in labels,
    }


def evaluate(champ: ChampionConfig) -> dict:
    return _eval_params(champ.model_params)


def seed() -> ChampionConfig:
    champ = ChampionConfig.new(sport="soccer", created_at=dt.date.today().isoformat(), **_SEED)
    save_champion(champ)
    return champ


def run_experiment(exp_id: Optional[str] = None, *, write: bool = False) -> dict:
    rm = roadmap.load_roadmap()
    champ = load_champion("soccer")
    exp = (roadmap.get_experiment(rm, "soccer", exp_id) if exp_id
           else roadmap.next_unrun(rm, "soccer", ledger.run_ids("soccer")))
    if exp is None:
        raise SystemExit("[soccer] no experiment to run (queue empty or all run)")
    if exp.get("status") == "needs_builder":
        raise SystemExit(f"[soccer] {exp['id']} needs a builder first")

    rule = roadmap.keep_rule_for(rm, "soccer", exp)
    added = [b for b in exp["builders"] if b not in champ.active_feature_builders]
    chal_builders = list(champ.active_feature_builders) + added
    chal_params = resolve_model_params("soccer", chal_builders)

    if champ.cumulative_metrics and "three_way_logloss" in champ.cumulative_metrics:
        champ_m = champ.cumulative_metrics
    else:
        champ_m = evaluate(champ)["metrics"]
    chal = _eval_params(chal_params)
    chal_m = chal["metrics"]

    decision, primary_delta, guard_ok = _decide(champ_m, chal_m, rule)
    challenger_version = bump_version(champ.model_version)
    result = {
        "id": exp["id"], "sport": "soccer", "rung": exp.get("rung"), "name": exp.get("name"),
        "run_at": dt.datetime.now().isoformat(timespec="seconds"),
        "champion_version": champ.model_version, "challenger_version": challenger_version,
        "builder_added": added, "eval_window": chal["eval_window"], "n_games": chal_m.get("games"),
        "champion_metrics": {k: champ_m.get(k) for k in _METRIC_KEYS},
        "challenger_metrics": {k: chal_m.get(k) for k in _METRIC_KEYS},
        "delta_logloss": round((chal_m.get("three_way_logloss") or 0) - (champ_m.get("three_way_logloss") or 0), 4),
        "delta_acc": round((chal_m.get("three_way_acc") or 0) - (champ_m.get("three_way_acc") or 0), 4),
        "keep_rule": rule, "primary_delta": primary_delta, "decision": decision,
        "act": exp.get("act"), "hypothesis": exp.get("hypothesis"),
    }
    if write:
        ledger.append_result(result)
    if decision == "keep":
        promoted = ChampionConfig.new(
            "soccer", challenger_version, max(champ.rung, int(exp.get("rung", champ.rung))),
            chal_builders, cumulative_metrics={**chal_m, "eval_window": chal["eval_window"],
                                               "measured_at": dt.date.today().isoformat()},
            holdout_season=chal["holdout_season"], eval_window=chal["eval_window"],
            created_at=dt.date.today().isoformat(),
            notes=f"Promoted from {champ.model_version} by {exp['id']} ({exp.get('name')}).")
        result["promoted_to"] = challenger_version
        if write:
            save_champion(promoted)
    return result


def honest_readout() -> dict:
    champ = load_champion("soccer")
    raw = load_epl_raw(SEASONS)
    present = sorted(int(s) for s in raw["season"].dropna().astype(int).unique())
    holdout = int(max(present)) if present else None
    bt = walk_forward_3way(raw, champ.model_params)   # full frame incl. the holdout season
    row = bt[bt["season"] == holdout] if not bt.empty else bt
    untouched = row.iloc[0].to_dict() if not row.empty else {}
    selected = champ.cumulative_metrics or {}

    def gap(k):
        u, s = untouched.get(k), selected.get(k)
        return round(u - s, 4) if (u is not None and s is not None) else None

    return {
        "champion": champ.model_version, "rung": champ.rung, "holdout_season": holdout,
        "untouched_test": {k: untouched.get(k) for k in ("n", "three_way_logloss", "three_way_acc", "total_mae")},
        "selected_traincv": {k: selected.get(k) for k in ("three_way_logloss", "three_way_acc", "total_mae")},
        "gap_untouched_minus_selected": {k: gap(k) for k in ("three_way_logloss", "three_way_acc")},
        "multiple_comparisons": ledger.counts("soccer"),
    }


# --- CLI helpers (the shared entrypoints delegate here for --sport soccer) --------
def _print_eval(champ: ChampionConfig, res: dict) -> None:
    m = res["metrics"]
    print(f"\n=== SOCCER champion {champ.model_version} (rung {champ.rung}) "
          f"- market-blind 3-way walk-forward (EPL) ===")
    print(f"builders: {', '.join(champ.active_feature_builders)}")
    print(f"params: {champ.model_params}")
    print(f"eval window: {res['eval_window']}   holdout (untouched): {res['holdout_season']}")
    print(f"N matches (train+CV): {m.get('games')}   seasons scored: {m.get('seasons')}")
    print(f"3-way logloss: {m.get('three_way_logloss')}   3-way acc: {m.get('three_way_acc')}")
    print(f"total MAE:     {m.get('total_mae')}   draw pred/act: {m.get('draw_pred')}/{m.get('draw_act')}")
    print("\nper-season:")
    for r in res["per_season"]:
        print(f"  {r['season']}: n={r['n']:>4}  LL={r['three_way_logloss']}  acc={r['three_way_acc']}  "
              f"totalMAE={r['total_mae']}  draw p/a={r['draw_pred']}/{r['draw_act']}")


def eval_cli(args) -> None:
    if args.seed:
        champ = seed()
        print(f"seeded soccer champion {champ.model_version} (rung {champ.rung}); "
              f"params: {champ.model_params}")
        return
    champ = load_champion("soccer")
    res = evaluate(champ)
    _print_eval(champ, res)
    if args.write:
        m = res["metrics"]
        champ.cumulative_metrics = {**m, "eval_window": res["eval_window"],
                                    "measured_at": dt.date.today().isoformat()}
        champ.holdout_season = res["holdout_season"]
        champ.eval_window = res["eval_window"]
        p = save_champion(champ)
        print(f"\nwrote metrics -> {p}")


def run_cli(args) -> None:
    r = run_experiment(exp_id=args.id, write=args.write)
    cm, hm = r["champion_metrics"], r["challenger_metrics"]
    verdict = "KEEP  -> " + r.get("promoted_to", "") if r["decision"] == "keep" else "DROP (champion unchanged)"
    print(f"\n=== EXPERIMENT {r['id']}: {r['name']} (Rung {r['rung']}) ===")
    print(f"TESTED : {r['hypothesis']}")
    print(f"champion {r['champion_version']} vs challenger {r['challenger_version']} (+{r['builder_added']})")
    print(f"eval window {r['eval_window']} · N={r['n_games']}")
    print(f"  {'metric':<18}{'champion':>12}{'challenger':>12}{'delta':>10}")
    print(f"  {'3-way logloss':<18}{cm.get('three_way_logloss'):>12}{hm.get('three_way_logloss'):>12}{r['delta_logloss']:>+10}")
    print(f"  {'3-way acc':<18}{cm.get('three_way_acc'):>12}{hm.get('three_way_acc'):>12}{r['delta_acc']:>+10}")
    kr = r["keep_rule"]
    print(f"keep-rule (pre-registered): {kr.get('metric')} must improve by >= {kr.get('min_delta')} "
          f"and {kr.get('guard_metric')} must not worsen")
    print(f"RESULT : {verdict}")
    if args.write:
        print(f"\nledger += {r['id']} ({r['decision']}); "
              + (f"champion -> {r.get('promoted_to')}" if r["decision"] == "keep" else "champion unchanged"))


def readout_cli(args) -> None:
    r = honest_readout()
    u, s, g = r["untouched_test"], r["selected_traincv"], r["gap_untouched_minus_selected"]
    mc = r["multiple_comparisons"]
    print(f"\n=== HONEST READOUT: {r['champion']} (Rung {r['rung']}) [soccer, 3-way] ===")
    print(f"untouched test season: {r['holdout_season']}  (N={u.get('n')}) - never used for selection")
    print(f"  {'metric':<18}{'selected(CV)':>14}{'untouched':>12}{'gap':>10}")
    print(f"  {'3-way logloss':<18}{s.get('three_way_logloss'):>14}{u.get('three_way_logloss'):>12}{g.get('three_way_logloss'):>+10}")
    print(f"  {'3-way acc':<18}{s.get('three_way_acc'):>14}{u.get('three_way_acc'):>12}{g.get('three_way_acc'):>+10}")
    print(f"multiple-comparisons exposure: {mc['run']} run, {mc['kept']} kept, {mc['dropped']} dropped")
