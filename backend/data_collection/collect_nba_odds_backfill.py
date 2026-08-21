#!/usr/bin/env python3
"""Build the historical NBA team-odds backfill (spreads + totals) that the team
model anchors on.

Source: Kaggle `christophertreasure/nba-odds-data` (2007 -> Jan-2023). Needs
KAGGLE_USERNAME / KAGGLE_KEY (already in .env for CI). Emits the csv_backfill
schema (game_date, home, away, spread_home, total) with canonical team codes to
`data/odds/nba_kaggle_backfill.csv`, where TeamPredrictor._line_for reads it.

NOTE ON CURRENCY: this dataset ends Jan-2023 — it's for TRAINING/backtesting the
anchor. UP-TO-DATE lines for the upcoming season come from the LIVE provider
(`sports/nba/live_odds.py`, The Odds API), which is what serves fresh games.
Re-run this if a newer Kaggle odds dataset becomes available.
"""
from __future__ import annotations

import argparse
import logging
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

OUT_CSV = BACKEND / "data" / "odds" / "nba_kaggle_backfill.csv"
DATASET = "christophertreasure/nba-odds-data"
# Full/relocation team names in the dataset -> our canonical codes.
CITY = {
    "Atlanta": "ATL", "Boston": "BOS", "Brooklyn": "BKN", "New Jersey": "BKN",
    "Charlotte": "CHA", "Chicago": "CHI", "Cleveland": "CLE", "Dallas": "DAL",
    "Denver": "DEN", "Detroit": "DET", "Golden State": "GSW", "Houston": "HOU",
    "Indiana": "IND", "LA Clippers": "LAC", "LA Lakers": "LAL", "Memphis": "MEM",
    "Miami": "MIA", "Milwaukee": "MIL", "Minnesota": "MIN", "New Orleans": "NOP",
    "New York": "NYK", "Oklahoma City": "OKC", "Seattle": "OKC", "Orlando": "ORL",
    "Philadelphia": "PHI", "Phoenix": "PHX", "Portland": "POR", "Sacramento": "SAC",
    "San Antonio": "SAS", "Toronto": "TOR", "Utah": "UTA", "Washington": "WAS",
}


def _download(dest: Path) -> Path:
    subprocess.run(["kaggle", "datasets", "download", "-d", DATASET, "-p", str(dest), "--unzip"],
                   check=True)
    csv = dest / "oddsData.csv"
    if not csv.exists():
        raise FileNotFoundError(f"expected oddsData.csv in {dest}")
    return csv


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", type=Path, default=None, help="pre-downloaded oddsData.csv (skip Kaggle)")
    ap.add_argument("--out", type=Path, default=OUT_CSV)
    args = ap.parse_args()

    src = args.csv
    if src is None:
        src = _download(Path(tempfile.mkdtemp()))
    df = pd.read_csv(src)

    h = df[df["home/visitor"] == "vs"].copy()   # one row per game (home perspective)
    h["home"] = h["team"].map(CITY)
    h["away"] = h["opponent"].map(CITY)
    h["spread_home"] = pd.to_numeric(h["spread"], errors="coerce")   # points-added-to-home
    h["total"] = pd.to_numeric(h["total"], errors="coerce")
    h["game_date"] = pd.to_datetime(h["date"]).dt.strftime("%Y-%m-%d")
    out = h[["game_date", "home", "away", "spread_home", "total"]].dropna()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.out, index=False)
    logger.info("wrote %d rows (%s -> %s) to %s",
                len(out), out["game_date"].min(), out["game_date"].max(), args.out)


if __name__ == "__main__":
    main()
