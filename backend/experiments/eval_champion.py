"""Evaluate a champion's market-blind walk-forward number (M1 harness proof).

Builds the sport's team-game frame, then runs the EXISTING walk-forward backtest
(``backtest/team_backtest.walk_forward_backtest``) on the champion's ``feature_cols``
over the TRAIN+CV seasons only — the final (most recent full) season is held
UNTOUCHED (never in the selection window; it's the honest test set M2's
``honest_readout`` will use). Reports SU accuracy, winner log-loss, margin/total
MAE, N, and the eval window.

Deterministic: fixed seed + single thread + LightGBM deterministic mode, so the
same seasons + config reproduce the same metrics.

Usage:
    # one-time: create the champion descriptor (no data / network needed)
    python -m experiments.eval_champion --sport nfl --seed
    # the reproducible number (fetches nflverse data; needs nfl_data_py):
    python -m experiments.eval_champion --sport nfl --write
"""
from __future__ import annotations

import argparse
import datetime as dt
import logging

import numpy as np
import pandas as pd

from backtest.team_backtest import summarize, walk_forward_backtest
from experiments.champion import ChampionConfig, load_champion, save_champion

logger = logging.getLogger(__name__)

# Reproducibility: pin seed, single thread, LightGBM deterministic mode. Passed
# through walk_forward_backtest -> _fit -> LGBMRegressor.
DETERMINISTIC_PARAMS = {
    "random_state": 42, "n_jobs": 1, "deterministic": True,
    "force_row_wise": True, "verbose": -1,
}

# Initial champions seeded by --seed (M1 = NFL; M7 = MLB fan-out).
_SEEDS = {
    "nfl": dict(
        model_version="nfl-v1", rung=1,
        active_feature_builders=["NFL-01", "NFL-02", "NFL-03", "NFL-04", "NFL-05"],
        notes="Day-1 NFL champion (M1): deliberately-simple Rung-1 box-score "
              "baseline, market-blind. Unimpressive by design — the climb starts here.",
    ),
    "mlb": dict(
        model_version="mlb-v1", rung=1,
        active_feature_builders=["MLB-01", "MLB-02", "MLB-03", "MLB-04", "MLB-05"],
        notes="Day-1 MLB champion (M7): deliberately-simple Rung-1 box-score "
              "baseline (runs for/against, win%, run-diff, prior-year carryover), "
              "market-blind. MLB is low-signal from team stats alone — the starting "
              "pitcher is the climb.",
    ),
    "nhl": dict(
        model_version="nhl-v1", rung=1,
        active_feature_builders=["NHL-01", "NHL-02", "NHL-03", "NHL-04", "NHL-05"],
        notes="Day-1 NHL champion (M7): deliberately-simple Rung-1 box-score "
              "baseline (goals for/against, win%, goal-diff, prior-year carryover), "
              "market-blind. More team signal than MLB; the starting goalie is the "
              "eventual climb (needs the boxscore endpoint).",
    ),
}


def _build_frame(sport: str, start: int, end: int, feature_cols: list | None = None) -> pd.DataFrame:
    if sport == "nfl":
        from sports.nfl.team_features import build_team_game_frame
        return build_team_game_frame(range(start, end + 1))
    if sport == "mlb":
        from sports.mlb.team_features import build_team_game_frame
        # Only pay the per-pitcher SP_ERA backfill when an SP_ERA column is under
        # test; the box-score / SP_RA ladder builds from the schedule alone.
        need_era = feature_cols is None or any("SP_ERA" in c for c in feature_cols)
        return build_team_game_frame(range(start, end + 1), fetch_sp_era=need_era)
    if sport == "nhl":
        from sports.nhl.team_features import build_team_game_frame
        return build_team_game_frame(range(start, end + 1))
    raise ValueError(f"eval_champion: sport '{sport}' not wired yet (M1=nfl, M7=mlb/nhl)")


def _pick_holdout(frame: pd.DataFrame, min_frac: float = 0.5) -> int:
    """Most-recent FULL season = the untouched holdout. Drop clearly-partial
    seasons (e.g., an in-progress current season) so the holdout is a real season."""
    counts = frame.groupby("season").size()
    full = counts[counts >= min_frac * counts.median()]
    return int(full.index.max())


def backtest_feature_set(sport: str, feature_cols: list, *, start: int, end: int) -> dict:
    """Walk-forward backtest of an arbitrary feature set over TRAIN+CV seasons only
    (the final full season is held untouched). Shared by the champion eval and the
    experiment runner so champion + challenger are measured on identical windows."""
    frame = _build_frame(sport, start, end, feature_cols)
    frame["season"] = frame["season"].astype(int)
    holdout = _pick_holdout(frame)
    traincv = frame[frame["season"] < holdout].copy()   # final season stays UNTOUCHED
    bt = walk_forward_backtest(traincv, sport=sport, feature_cols=feature_cols,
                               params=DETERMINISTIC_PARAMS)
    labels = bt["season"].tolist() if not bt.empty else []
    return {
        "metrics": summarize(bt),
        "per_season": bt.to_dict(orient="records"),
        "eval_window": f"{labels[0]}–{labels[-1]}" if labels else None,
        "holdout_season": holdout,
        "n_seasons_available": int(frame["season"].nunique()),
        "final_season_excluded": holdout not in set(int(x) for x in traincv["season"].unique()),
    }


def evaluate(champ: ChampionConfig, *, start: int, end: int) -> dict:
    return backtest_feature_set(champ.sport, champ.feature_cols, start=start, end=end)


def _refit_shipped(champ: ChampionConfig, *, start: int, end: int) -> None:
    """Refit the shipped margin+total models on ALL rows at the validated iteration
    count (walk_forward_train), keyed by model_version. Artifacts are gitignored /
    R2-synced (models/artifacts/), never committed."""
    import joblib

    from config.paths import ARTIFACTS_DIR
    from model_training.validation import walk_forward_train

    frame = _build_frame(champ.sport, start, end, champ.feature_cols)
    frame["season"] = frame["season"].astype(int)
    X = frame[champ.feature_cols].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    out = ARTIFACTS_DIR / champ.sport / champ.model_version
    out.mkdir(parents=True, exist_ok=True)
    for target in ("y_margin", "y_total"):
        model, meta = walk_forward_train(
            X, frame[target], frame["season"], dates=frame["game_date"],
            params=DETERMINISTIC_PARAMS,
        )
        ho_mae = meta.get("holdout_mae")
        sigma = float(1.2533 * ho_mae) if ho_mae else float(
            meta.get("holdout_resid_std") or np.std(frame[target]))
        joblib.dump({"model": model, "target": target, "sigma": sigma,
                     "feature_cols": champ.feature_cols, "model_version": champ.model_version,
                     "market_blind": True, "metrics": meta}, out / f"{target}.joblib")
        print(f"  refit {target}: holdout_mae={ho_mae} best_iter={meta.get('best_iteration')}"
              f" -> {out / f'{target}.joblib'}")


def _seed(sport: str) -> ChampionConfig:
    champ = ChampionConfig.new(sport=sport, created_at=dt.date.today().isoformat(),
                               **_SEEDS[sport])
    save_champion(champ)
    return champ


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(description="Evaluate a market-blind champion (walk-forward).")
    ap.add_argument("--sport", default="nfl")
    ap.add_argument("--start", type=int, default=1999)
    ap.add_argument("--end", type=int, default=dt.date.today().year)
    ap.add_argument("--seed", action="store_true", help="write the initial champion descriptor and exit")
    ap.add_argument("--write", action="store_true", help="persist metrics into champion.json")
    ap.add_argument("--refit", action="store_true", help="also refit + save the shipped model")
    args = ap.parse_args()

    if args.seed:
        champ = _seed(args.sport)
        print(f"seeded {champ.sport} champion {champ.model_version} (rung {champ.rung}); "
              f"features ({len(champ.feature_cols)}): {', '.join(champ.feature_cols)}")
        return

    champ = load_champion(args.sport)
    res = evaluate(champ, start=args.start, end=args.end)
    m = res["metrics"]
    print(f"\n=== {champ.sport.upper()} champion {champ.model_version} (rung {champ.rung}) "
          f"— market-blind walk-forward ===")
    print(f"builders: {', '.join(champ.active_feature_builders)}")
    print(f"features ({len(champ.feature_cols)}): {', '.join(champ.feature_cols)}")
    print(f"eval window: {res['eval_window']}   holdout (untouched): {res['holdout_season']}   "
          f"final-season-excluded: {res['final_season_excluded']}")
    print(f"N games (train+CV OOS): {m.get('games')}   seasons scored: {m.get('seasons')}")
    print(f"SU accuracy:    {m.get('su_acc')}")
    print(f"winner logloss: {m.get('winner_logloss')}")
    print(f"margin MAE:     {m.get('margin_mae')}")
    print(f"total MAE:      {m.get('total_mae')}")
    print("\nper-season:")
    for r in res["per_season"]:
        print(f"  {r['season']}: n={r['n']:>4}  SU={r['su_acc']}  LL={r.get('winner_logloss')}  "
              f"marginMAE={r['margin_mae']}  totalMAE={r['total_mae']}")

    if args.write:
        champ.cumulative_metrics = {**m, "eval_window": res["eval_window"],
                                    "measured_at": dt.date.today().isoformat()}
        champ.holdout_season = res["holdout_season"]
        champ.eval_window = res["eval_window"]
        p = save_champion(champ)
        print(f"\nwrote metrics -> {p}")

    if args.refit:
        print("\nrefitting shipped model...")
        _refit_shipped(champ, start=args.start, end=args.end)


if __name__ == "__main__":
    main()
