#!/usr/bin/env python3
"""Collect a slate's odds from the configured free providers, write the live
snapshot, and append to the forward-collection history.

Mirrors the shape of collect_dvp.py / collect_injuries.py so it slots into the
nightly pipeline as ``step_collect_odds``.
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import List

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from odds.provider import MultiProvider, OddsProvider
from odds.store import append_history, write_live_snapshot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def build_provider(csv: Path = None, manual: Path = None, prizepicks: bool = True) -> MultiProvider:
    providers: List[OddsProvider] = []
    if csv:
        from odds.providers.csv_backfill import CSVBackfillProvider
        providers.append(CSVBackfillProvider(csv))
    if manual:
        from odds.providers.manual import ManualProvider
        providers.append(ManualProvider(manual))
    if prizepicks:
        from odds.providers.prizepicks import PrizePicksProvider
        providers.append(PrizePicksProvider())
    return MultiProvider(providers)


def collect(sport: str, game_date: str, provider: OddsProvider) -> int:
    lines = provider.fetch_game_markets(sport, game_date) + provider.fetch_player_props(sport, game_date)
    write_live_snapshot(sport, game_date, lines)
    added = append_history(lines)
    logger.info("collected %d odds lines for %s %s (+%d to history)", len(lines), sport, game_date, added)
    return len(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sport", default="nba")
    ap.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    ap.add_argument("--csv", type=Path, default=None, help="historical team-market CSV (csv_backfill)")
    ap.add_argument("--manual", type=Path, default=None, help="manual normalized odds CSV")
    ap.add_argument("--no-prizepicks", action="store_true")
    args = ap.parse_args()

    provider = build_provider(csv=args.csv, manual=args.manual, prizepicks=not args.no_prizepicks)
    collect(args.sport, args.date, provider)


if __name__ == "__main__":
    main()
