"""On-disk odds stores.

- **live snapshot**: ``data/odds/live/{sport}/{date}.parquet`` — latest capture
  for a slate; what the API / best-bet selection read today.
- **append-only history**: ``data/odds/history/odds_history.parquet`` — every
  capture appended (idempotent on ``odds_id`` + ``captured_at``), building the
  forward-collection corpus for grading and (eventually) prop backtests.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import pandas as pd

from config.paths import ODDS_HISTORY_PARQUET, ODDS_LIVE_DIR
from odds.schema import OddsLine

logger = logging.getLogger(__name__)


def _stamp(lines: List[OddsLine]) -> List[OddsLine]:
    ts = datetime.now(timezone.utc).isoformat()
    for ln in lines:
        if not ln.captured_at:
            ln.captured_at = ts
    return lines


def _to_frame(lines: List[OddsLine]) -> pd.DataFrame:
    return pd.DataFrame([ln.to_dict() for ln in lines]) if lines else pd.DataFrame()


def write_live_snapshot(sport: str, game_date: str, lines: List[OddsLine]) -> Path:
    lines = _stamp(lines)
    d = ODDS_LIVE_DIR / sport
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{game_date}.parquet"
    _to_frame(lines).to_parquet(p, index=False)
    logger.info("wrote %d live odds lines -> %s", len(lines), p)
    return p


def load_live(sport: str, game_date: str) -> pd.DataFrame:
    p = ODDS_LIVE_DIR / sport / f"{game_date}.parquet"
    return pd.read_parquet(p) if p.exists() else pd.DataFrame()


def append_history(lines: List[OddsLine]) -> int:
    """Append captures to the history store; returns the number of NEW rows.
    Idempotent: re-appending the same capture (same odds_id + captured_at) is a
    no-op."""
    lines = _stamp(lines)
    new = _to_frame(lines)
    if new.empty:
        return 0
    if ODDS_HISTORY_PARQUET.exists():
        old = pd.read_parquet(ODDS_HISTORY_PARQUET)
        n_old = len(old)
        combined = pd.concat([old, new], ignore_index=True)
    else:
        n_old = 0
        combined = new
    combined = combined.drop_duplicates(subset=["odds_id", "captured_at"], keep="last")
    ODDS_HISTORY_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    combined.to_parquet(ODDS_HISTORY_PARQUET, index=False)
    added = len(combined) - n_old
    logger.info("history append: +%d rows (total %d)", added, len(combined))
    return added


def load_history(
    sport: Optional[str] = None, market_family: Optional[str] = None
) -> pd.DataFrame:
    if not ODDS_HISTORY_PARQUET.exists():
        return pd.DataFrame()
    df = pd.read_parquet(ODDS_HISTORY_PARQUET)
    if sport:
        df = df[df["sport"] == sport]
    if market_family:
        df = df[df["market_family"] == market_family]
    return df.reset_index(drop=True)
