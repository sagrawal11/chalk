"""Soccer identity across competitions. Unlike the US leagues there's no small
fixed team set (EPL + UCL + MLS = 100+ clubs), so a team's canonical id is its
normalized name; a light alias map folds common bookmaker/source variants.
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict

# Sport keys for the three competitions we cover.
COMPETITIONS: Dict[str, str] = {
    "epl": "soccer_epl",
    "ucl": "soccer_uefa_champs_league",
    "mls": "soccer_usa_mls",
}

_ALIASES: Dict[str, str] = {
    "Man City": "Manchester City", "Man Utd": "Manchester United",
    "Man United": "Manchester United", "Spurs": "Tottenham Hotspur",
    "Tottenham": "Tottenham Hotspur", "Wolves": "Wolverhampton Wanderers",
    "Newcastle": "Newcastle United", "Nott'm Forest": "Nottingham Forest",
    "Brighton": "Brighton and Hove Albion", "West Ham": "West Ham United",
    "Inter Miami": "Inter Miami CF", "LA Galaxy": "LA Galaxy", "LAFC": "Los Angeles FC",
    # football-data.co.uk EPL short names (2021-22..2024-25) -> canonical full names.
    "Leeds": "Leeds United", "Leicester": "Leicester City",
    "Sheffield United": "Sheffield United", "Wolverhampton": "Wolverhampton Wanderers",
    "Nottingham Forest": "Nottingham Forest", "Brighton & Hove Albion": "Brighton and Hove Albion",
}


def canonical_team(name: str, *, strict: bool = True) -> str:
    """Normalize a club name (collapse whitespace, fold known aliases). Soccer has
    no fixed roster of codes, so any non-empty name is valid identity."""
    if name is None or not str(name).strip():
        if strict:
            raise ValueError("empty team name")
        return ""
    n = " ".join(str(name).split()).strip()
    return _ALIASES.get(n, n)


def season_from_date(game_date: str) -> str:
    """European seasons span two years (named by START year, Aug->May); MLS is a
    calendar year. We use the start-year convention (good enough for labeling)."""
    d = datetime.strptime(str(game_date)[:10], "%Y-%m-%d")
    return str(d.year if d.month >= 7 else d.year - 1)
