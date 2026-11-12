#!/usr/bin/env python3
"""Live daily track record: lock tonight's predictions, grade finals, aggregate.

The honest out-of-sample record, driven as a nightly pair plus an on-demand report:

  python -m pipeline.track_record lock   --sport nhl [--date YYYY-MM-DD]   # pre-game
  python -m pipeline.track_record grade  --sport nhl [--date YYYY-MM-DD]   # post-game
  python -m pipeline.track_record report [--sport nhl] [--all-sources]

`lock` predicts each game on the date from the matchup only (never the score) and
writes an immutable, hashed lock (track_record.lock) -- so there is no hindsight
editing. `grade` loads that lock and grades it against the final scores, appending
to the results ledger (track_record.grade): did the favored side win, and how far
off was the predicted score. `report` rolls the ledger into the win% / streak /
score-MAE headline (track_record.aggregate). No betting lines anywhere.

Only the per-sport slate+finals source (`_games_on`) is new glue -- the lock / grade
/ aggregate primitives already existed but were never driven by a live loop (the
ledger was backtest-seed-only). NHL is wired live: sports.nhl.data.load_schedules
refetches the current season on the fly and reads cached parquets for past ones, so
`lock --date today` gets tonight's real slate and a past date replays offline. Soccer
is wired from the cached EPL results (replay only; no free live fixtures feed). Add a
sport by adding one branch to `_games_on`.

Schedule it yourself (e.g. launchd / cron): lock after the slate is set but before
tip-off, grade the next morning. This module deliberately does NOT install any cron.
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from predictions.schema import make_game_key
from sports.base import get_sport
from track_record.aggregate import headline, summarize
from track_record.grade import RESULTS_LEDGER, append_ledger, grade_date
from track_record.lock import lock_path, lock_predictions

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# Sports with a wired slate+finals source in `_games_on`. Others are skipped until a
# feed is added (one branch each) -- we never build a live feed speculatively.
WIRED_SPORTS = ["nhl", "soccer"]


def _nhl_season_year(date: str) -> int:
    """NHL season START year for a calendar date (the season spans Oct->Jun)."""
    d = datetime.strptime(date, "%Y-%m-%d")
    return d.year - 1 if d.month <= 6 else d.year


def _games_on(sport: str, date: str) -> Optional[pd.DataFrame]:
    """Every `sport` game on `date` as columns home/away/home_pts/away_pts/final.

    `final` marks a game with a known result (gradeable). Scheduled-but-unplayed
    games have final=False and NaN scores -- they are part of the slate (lockable)
    but not yet gradeable. Returns None when the sport has no wired source yet.
    """
    if sport == "nhl":
        from sports.nhl.data import load_schedules
        s = load_schedules([_nhl_season_year(date)])
        s = s[s["game_date"].astype(str).str[:10] == date]
        hp = pd.to_numeric(s["home_goals"], errors="coerce")
        ap = pd.to_numeric(s["away_goals"], errors="coerce")
        return pd.DataFrame({
            "home": s["home"].to_numpy(), "away": s["away"].to_numpy(),
            "home_pts": hp.to_numpy(), "away_pts": ap.to_numpy(),
            "final": (s["status"].isin(["OFF", "FINAL"]).to_numpy() & hp.notna().to_numpy()),
        })
    if sport == "soccer":
        from sports.soccer.team_features import load_epl_raw
        m = load_epl_raw()
        m = m[m["date"].astype(str).str[:10] == date]
        hp = pd.to_numeric(m["fthg"], errors="coerce")
        ap = pd.to_numeric(m["ftag"], errors="coerce")
        return pd.DataFrame({
            "home": m["home"].to_numpy(), "away": m["away"].to_numpy(),
            "home_pts": hp.to_numpy(), "away_pts": ap.to_numpy(),
            "final": hp.notna().to_numpy(),
        })
    return None


def cmd_lock(sport: str, date: str, *, force: bool = False) -> int:
    """Predict + immutably lock the slate for (sport, date). Pre-game by design:
    only the matchup feeds the model, never the score."""
    g = _games_on(sport, date)
    if g is None:
        logger.warning("[%s] no wired slate source; skipped", sport)
        return 0
    if g.empty:
        logger.info("[%s] no games on %s", sport, date)
        return 0
    if lock_path(sport, date).exists() and not force:
        logger.info("[%s] %s already locked (immutable); use --force only to fix a same-day error",
                    sport, date)
        return 0
    sp = get_sport(sport)
    preds: List = []
    for _, row in g.iterrows():
        try:
            p = sp.predict_game(home=str(row["home"]), away=str(row["away"]), game_date=date)
        except Exception as e:
            logger.warning("[%s] predict failed %s@%s: %s", sport, row["away"], row["home"], e)
            p = None
        if p is not None:
            preds.append(p)
    if not preds:
        logger.warning("[%s] no predictions produced for %s (model not served?)", sport, date)
        return 0
    path = lock_predictions(sport, date, preds, model_version=f"{sport}_served", force=force)
    logger.info("[%s] locked %d games for %s -> %s", sport, len(preds), date, path)
    return len(preds)


def cmd_grade(sport: str, date: str) -> int:
    """Grade the locked slate for (sport, date) against finals; append to the ledger."""
    if not lock_path(sport, date).exists():
        logger.warning("[%s] no lock for %s; run `lock` first", sport, date)
        return 0
    g = _games_on(sport, date)
    if g is None or g.empty:
        logger.warning("[%s] no results source for %s", sport, date)
        return 0
    finals: Dict[str, Dict[str, float]] = {}
    for _, row in g.iterrows():
        if not bool(row["final"]) or pd.isna(row["home_pts"]) or pd.isna(row["away_pts"]):
            continue
        key = make_game_key(sport, date, str(row["away"]), str(row["home"]))
        finals[key] = {"home_pts": float(row["home_pts"]), "away_pts": float(row["away_pts"])}
    if not finals:
        logger.info("[%s] no finals yet for %s (games not completed)", sport, date)
        return 0
    df = grade_date(sport, date, finals)
    added = append_ledger(df)
    if not df.empty:
        h = headline(df)
        logger.info("[%s] graded %d games for %s: %s (%s SU) | +%d ledger rows",
                    sport, len(df), date, h["record"],
                    f"{h['win_pct']:.1%}" if h["win_pct"] is not None else "n/a", added)
    return len(df)


def cmd_report(sport: Optional[str], all_sources: bool) -> None:
    """Print the live record (headline + per-sport) from the results ledger."""
    if not RESULTS_LEDGER.exists():
        logger.info("no results ledger yet at %s (run lock+grade first)", RESULTS_LEDGER)
        return
    led = pd.read_parquet(RESULTS_LEDGER)
    if not all_sources and "source" in led.columns:
        led = led[led["source"] == "live"]  # the real live OOS record, excluding backtest seed
    if sport:
        led = led[led["sport"] == sport]
    if led.empty:
        logger.info("no %s rows in the ledger", "live" if not all_sources else "matching")
        return
    scope = "ALL (incl. backtest seed)" if all_sources else "LIVE"
    h = headline(led)
    logger.info("=== track record [%s] ===", scope)
    logger.info("RECORD %s | win%% %s | streak %+d | n=%d | score MAE %s",
                h["record"], f"{h['win_pct']:.1%}" if h["win_pct"] is not None else "n/a",
                h["streak"], h["n"], h["score_mae"])
    by = summarize(led, ["sport"])
    for _, r in by.sort_values("sport").iterrows():
        wp = f"{r['win_pct']:.1%}" if pd.notna(r["win_pct"]) else "n/a"
        logger.info("  %-7s %d-%d (%s)  score MAE %s", r["sport"],
                    int(r["wins"]), int(r["losses"]), wp, r["score_mae"])


def _default_date(cmd: str) -> str:
    """lock defaults to today's slate; grade defaults to yesterday's finals."""
    day = datetime.now() if cmd == "lock" else datetime.now() - timedelta(days=1)
    return day.strftime("%Y-%m-%d")


def main() -> int:
    ap = argparse.ArgumentParser(description="CHALK live track record (lock / grade / report)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    pl = sub.add_parser("lock", help="predict + immutably lock a date's slate (pre-game)")
    pl.add_argument("--sport", default="all", choices=["all", *WIRED_SPORTS])
    pl.add_argument("--date", default=None, help="YYYY-MM-DD (default: today)")
    pl.add_argument("--force", action="store_true", help="overwrite a same-day lock (corrections only)")

    pg = sub.add_parser("grade", help="grade a locked slate against finals (post-game)")
    pg.add_argument("--sport", default="all", choices=["all", *WIRED_SPORTS])
    pg.add_argument("--date", default=None, help="YYYY-MM-DD (default: yesterday)")

    pr = sub.add_parser("report", help="print the live record from the ledger")
    pr.add_argument("--sport", default=None, choices=WIRED_SPORTS)
    pr.add_argument("--all-sources", action="store_true", help="include the backtest seed rows")

    args = ap.parse_args()

    if args.cmd == "report":
        cmd_report(args.sport, args.all_sources)
        return 0

    sports = WIRED_SPORTS if args.sport == "all" else [args.sport]
    date = args.date or _default_date(args.cmd)
    for sp in sports:
        try:
            if args.cmd == "lock":
                cmd_lock(sp, date, force=args.force)
            else:
                cmd_grade(sp, date)
        except Exception as e:  # one sport's outage never aborts the rest
            logger.warning("[%s] %s failed for %s: %s", sp, args.cmd, date, e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
