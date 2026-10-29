#!/usr/bin/env python3
"""Seed the public track record with an HONEST market-blind backtest.

For each team sport, walk forward season by season (a game is only ever predicted by a
model that never saw it), turn each game into a market-blind winner + predicted-score
pick, grade it against the known final, and append to the results ledger. Produces the
hero metrics on day one: straight-up winner accuracy + predicted-score MAE, with ROI
left n/a (no historical closing moneyline exists; it accrues forward from live prices).

Soccer predicts 3-way via a Poisson (Dixon-Coles-lite) model, not the margin/total
regression the other sports walk-forward covers, so it uses a SEASON-level leakage-safe
walk-forward (``track_record.seed_writer.build_soccer_seed_rows``): for each season S,
ratings are built from matches BEFORE S only, each match in S is predicted, and the
more-likely of home/away is the market-blind winner (never a draw; a draw grades as a
loss). Run:  python -m pipeline.seed_track_record --sport all
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from backtest.team_backtest import walk_forward_predictions
from track_record.aggregate import headline, score_mae
from track_record.grade import RESULTS_LEDGER
from track_record.seed_writer import (build_seed_rows, build_soccer_seed_rows,
                                      write_seed, write_soccer_seed)

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

TEAM_SPORTS = ["nba", "nfl", "mlb", "nhl"]
ALL_SPORTS = [*TEAM_SPORTS, "soccer"]
# Year range per sport (NBA reads its full parquet and ignores this).
_DEFAULT_YEARS = {"nfl": (2010, 2024), "mlb": (2016, 2024), "nhl": (2016, 2024)}
# Soccer (EPL) season START years to load from football-data.co.uk (cached parquets).
_SOCCER_SEASONS = (2021, 2022, 2023, 2024)


def _frame_and_cols(sport: str, start: int, end: int):
    """Build the market-blind team frame + its feature columns. NFL MUST use
    RESIDUAL_FEATURE_COLS: its TEAM_FEATURE_COLS includes the market line."""
    if sport == "nba":
        from sports.nba.team_features import TEAM_FEATURE_COLS, build_team_game_frame
        return build_team_game_frame(), TEAM_FEATURE_COLS
    if sport == "nfl":
        from sports.nfl.team_features import RESIDUAL_FEATURE_COLS, build_team_game_frame
        return build_team_game_frame(range(start, end + 1)), RESIDUAL_FEATURE_COLS
    if sport == "mlb":
        from sports.mlb.team_features import TEAM_FEATURE_COLS, build_team_game_frame
        return build_team_game_frame(range(start, end + 1)), TEAM_FEATURE_COLS
    if sport == "nhl":
        from sports.nhl.team_features import TEAM_FEATURE_COLS, build_team_game_frame
        return build_team_game_frame(range(start, end + 1)), TEAM_FEATURE_COLS
    raise ValueError(f"unsupported sport: {sport}")


def seed_soccer(min_train_seasons: int = 1, dry_run: bool = False,
                matches=None):
    """Season-level leakage-safe seed for the Poisson soccer model. ``matches`` is
    injectable (tests pass a synthetic frame); by default the cached EPL results are
    loaded via ``build_epl_matches`` (offline once the per-season parquets exist)."""
    if matches is None:
        from sports.soccer.team_features import build_epl_matches
        matches = build_epl_matches(_SOCCER_SEASONS)
    if matches is None or matches.empty:
        logger.warning("[soccer] no match data, skipped")
        return None
    rows = build_soccer_seed_rows(matches, min_train_seasons=min_train_seasons)
    if rows.empty:
        logger.warning("[soccer] not enough seasons for walk-forward, skipped")
        return None
    h, mae = headline(rows), score_mae(rows)
    wp = f"{h['win_pct']:.1%}" if h["win_pct"] is not None else "n/a"
    logger.info("[soccer] %5d games | SU win%% %s (draws grade as loss) | score MAE %s | record %s",
                len(rows), wp, mae, h["record"])
    if not dry_run:
        added = write_soccer_seed(matches, min_train_seasons=min_train_seasons)
        logger.info("[soccer] wrote %d rows -> %s", added, RESULTS_LEDGER)
    return h


def seed_sport(sport: str, start=None, end=None, min_train_seasons: int = 3,
               dry_run: bool = False):
    if sport == "soccer":
        # Soccer uses a season-level walk-forward with a 1-prior-season gate (the
        # 3-season team-model gate would leave almost nothing predictable).
        return seed_soccer(min_train_seasons=1, dry_run=dry_run)
    ds, de = _DEFAULT_YEARS.get(sport, (None, None))
    start, end = start or ds, end or de
    frame, cols = _frame_and_cols(sport, start, end)
    if frame is None or frame.empty:
        logger.warning("[%s] no data, skipped", sport)
        return None
    preds = walk_forward_predictions(frame, sport=sport, feature_cols=cols,
                                     min_train_seasons=min_train_seasons)
    if preds.empty:
        logger.warning("[%s] not enough seasons for walk-forward, skipped", sport)
        return None
    rows = build_seed_rows(preds)
    h, mae = headline(rows), score_mae(rows)
    wp = f"{h['win_pct']:.1%}" if h["win_pct"] is not None else "n/a"
    logger.info("[%s] %5d games | SU win%% %s | score MAE %s | record %s",
                sport, len(rows), wp, mae, h["record"])
    if not dry_run:
        added = write_seed(preds)
        logger.info("[%s] wrote %d rows -> %s", sport, added, RESULTS_LEDGER)
    return h


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sport", default="all", choices=["all", *ALL_SPORTS])
    ap.add_argument("--start", type=int, default=None)
    ap.add_argument("--end", type=int, default=None)
    ap.add_argument("--min-train-seasons", type=int, default=3)
    ap.add_argument("--dry-run", action="store_true", help="compute metrics, do not write the ledger")
    args = ap.parse_args()
    sports = ALL_SPORTS if args.sport == "all" else [args.sport]
    for sp in sports:
        try:
            seed_sport(sp, args.start, args.end, args.min_train_seasons, args.dry_run)
        except Exception as e:  # one sport's data outage never aborts the rest
            logger.warning("[%s] seeding failed: %s", sp, e)


if __name__ == "__main__":
    main()
