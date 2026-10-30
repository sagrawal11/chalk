"""Canonical MLB team identity (StatsAPI abbreviations) + alias folding.

Handles the abbreviation variants across sources (ARI/AZ, CHW/CWS, WAS/WSH,
SDP/SD, SFG/SF, TBR/TB, KCR/KC, OAK/ATH after the A's move) and full team
names, so every source resolves to one code.
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, Set

CANONICAL_TEAMS: Set[str] = {
    "ATH", "ATL", "AZ", "BAL", "BOS", "CHC", "CIN", "CLE", "COL", "CWS",
    "DET", "HOU", "KC", "LAA", "LAD", "MIA", "MIL", "MIN", "NYM", "NYY",
    "PHI", "PIT", "SD", "SEA", "SF", "STL", "TB", "TEX", "TOR", "WSH",
}

# Full team names -> canonical code.
_FULL_NAMES: Dict[str, str] = {
    "Athletics": "ATH", "Oakland Athletics": "ATH", "Atlanta Braves": "ATL",
    "Arizona Diamondbacks": "AZ", "Baltimore Orioles": "BAL", "Boston Red Sox": "BOS",
    "Chicago Cubs": "CHC", "Cincinnati Reds": "CIN", "Cleveland Guardians": "CLE",
    "Colorado Rockies": "COL", "Chicago White Sox": "CWS", "Detroit Tigers": "DET",
    "Houston Astros": "HOU", "Kansas City Royals": "KC", "Los Angeles Angels": "LAA",
    "Los Angeles Dodgers": "LAD", "Miami Marlins": "MIA", "Milwaukee Brewers": "MIL",
    "Minnesota Twins": "MIN", "New York Mets": "NYM", "New York Yankees": "NYY",
    "Philadelphia Phillies": "PHI", "Pittsburgh Pirates": "PIT", "San Diego Padres": "SD",
    "Seattle Mariners": "SEA", "San Francisco Giants": "SF", "St. Louis Cardinals": "STL",
    "Tampa Bay Rays": "TB", "Texas Rangers": "TEX", "Toronto Blue Jays": "TOR",
    "Washington Nationals": "WSH",
}
_ABBR_ALIASES: Dict[str, str] = {
    "ARI": "AZ", "CHW": "CWS", "WAS": "WSH", "SDP": "SD", "SFG": "SF",
    "TBR": "TB", "KCR": "KC", "OAK": "ATH", "CHA": "CWS", "CHN": "CHC",
    "LAN": "LAD", "NYN": "NYM", "NYA": "NYY", "SLN": "STL", "SFN": "SF",
    "SDN": "SD", "TBA": "TB", "KCA": "KC", "ANA": "LAA", "FLA": "MIA",
}


def canonical_team(code: str, *, strict: bool = True) -> str:
    if code is None:
        if strict:
            raise ValueError("empty team code")
        return ""
    c = str(code).strip()
    if c in CANONICAL_TEAMS:
        return c
    up = c.upper()
    if up in CANONICAL_TEAMS:
        return up
    if up in _ABBR_ALIASES:
        return _ABBR_ALIASES[up]
    if c in _FULL_NAMES:
        return _FULL_NAMES[c]
    # last resort: case-insensitive full-name match
    for name, canon in _FULL_NAMES.items():
        if name.lower() == c.lower():
            return canon
    if strict:
        raise ValueError(f"unknown MLB team: {code!r}")
    return ""


def season_from_date(game_date: str) -> str:
    """MLB season is named by its calendar year (Mar/Apr -> Oct/Nov)."""
    return str(datetime.strptime(str(game_date)[:10], "%Y-%m-%d").year)
