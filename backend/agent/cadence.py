"""Experiment cadence (CHALK_MASTER_PLAN §7 / ARCHITECTURE §7): which sports run a
feature experiment on which day, a content-rhythm choice, not a technical limit.
NFL/CFB ~twice-weekly, NBA/NHL daily, MLB/soccer few-per-week. Predictions/results are
game-day-driven (decided by the slate, not here).
"""
from __future__ import annotations

import datetime as dt

# weekday() -> Mon=0 … Sun=6. Config-like; refine per sport as they launch.
_CADENCE = {
    "nfl": {1, 4},              # Tue, Fri
    "cfb": {2, 5},             # Wed, Sat
    "nba": set(range(7)),      # daily
    "nhl": set(range(7)),      # daily
    "mlb": {0, 2, 4},          # Mon, Wed, Fri
    "soccer": {2, 6},          # Wed, Sun
}


def experiment_due(sport: str, date: dt.date) -> bool:
    return date.weekday() in _CADENCE.get(str(sport).lower(), set())
