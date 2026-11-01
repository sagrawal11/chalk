"""CFB team canonicalization.

The model is single-source (CFBD), whose team names are already internally
consistent across the /games feed, so ``canonical_team`` only normalizes
whitespace. A full alias table is only needed once a second source (odds,
rankings, a different stats feed) has to be reconciled against CFBD; defer it
until then (there is no second source yet).
"""
from __future__ import annotations

from datetime import datetime


def canonical_team(code: str, *, strict: bool = True) -> str:
    name = " ".join(str(code).split()).strip()
    if not name and strict:
        raise ValueError(f"Unknown team code: {code!r}")
    return name


def current_season() -> str:
    """CFB season = the calendar year of the fall kickoff (Aug-Jan spans one season
    labeled by its start year)."""
    now = datetime.now()
    return str(now.year if now.month >= 2 else now.year - 1)


def season_from_date(game_date: str) -> str:
    d = datetime.fromisoformat(str(game_date)[:10])
    return str(d.year if d.month >= 2 else d.year - 1)
