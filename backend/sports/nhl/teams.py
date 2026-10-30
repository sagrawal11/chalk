"""Canonical NHL team identity (NHL API abbreviations) + alias/relocation folding.

Franchise continuity: Atlanta Thrashers (ATL) -> Winnipeg (WPG, 2011); Phoenix/
Arizona Coyotes (PHX/ARI) -> Utah (UTA, 2024). Full team names map in too, so
every source resolves to one code.
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, Set

CANONICAL_TEAMS: Set[str] = {
    "ANA", "BOS", "BUF", "CAR", "CBJ", "CGY", "CHI", "COL", "DAL", "DET",
    "EDM", "FLA", "LAK", "MIN", "MTL", "NJD", "NSH", "NYI", "NYR", "OTT",
    "PHI", "PIT", "SEA", "SJS", "STL", "TBL", "TOR", "UTA", "VAN", "VGK",
    "WPG", "WSH",
}

_FULL_NAMES: Dict[str, str] = {
    "Anaheim Ducks": "ANA", "Boston Bruins": "BOS", "Buffalo Sabres": "BUF",
    "Carolina Hurricanes": "CAR", "Columbus Blue Jackets": "CBJ", "Calgary Flames": "CGY",
    "Chicago Blackhawks": "CHI", "Colorado Avalanche": "COL", "Dallas Stars": "DAL",
    "Detroit Red Wings": "DET", "Edmonton Oilers": "EDM", "Florida Panthers": "FLA",
    "Los Angeles Kings": "LAK", "Minnesota Wild": "MIN", "Montréal Canadiens": "MTL",
    "Montreal Canadiens": "MTL", "New Jersey Devils": "NJD", "Nashville Predators": "NSH",
    "New York Islanders": "NYI", "New York Rangers": "NYR", "Ottawa Senators": "OTT",
    "Philadelphia Flyers": "PHI", "Pittsburgh Penguins": "PIT", "Seattle Kraken": "SEA",
    "San Jose Sharks": "SJS", "St. Louis Blues": "STL", "St Louis Blues": "STL",
    "Tampa Bay Lightning": "TBL", "Toronto Maple Leafs": "TOR", "Utah Mammoth": "UTA",
    "Utah Hockey Club": "UTA", "Vancouver Canucks": "VAN", "Vegas Golden Knights": "VGK",
    "Winnipeg Jets": "WPG", "Washington Capitals": "WSH",
    "Arizona Coyotes": "UTA", "Phoenix Coyotes": "UTA", "Atlanta Thrashers": "WPG",
}
_ABBR_ALIASES: Dict[str, str] = {
    "ARI": "UTA", "PHX": "UTA", "ATL": "WPG", "LA": "LAK", "L.A": "LAK",
    "NJ": "NJD", "N.J": "NJD", "TB": "TBL", "T.B": "TBL", "SJ": "SJS", "S.J": "SJS",
    "WAS": "WSH", "MON": "MTL", "WIN": "WPG", "VEG": "VGK", "NAS": "NSH", "CLS": "CBJ",
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
    for name, canon in _FULL_NAMES.items():
        if name.lower() == c.lower():
            return canon
    if strict:
        raise ValueError(f"unknown NHL team: {code!r}")
    return ""


def season_from_date(game_date: str) -> str:
    """NHL season is named by its START year (Oct -> Jun); Jan-Aug -> prior start year."""
    d = datetime.strptime(str(game_date)[:10], "%Y-%m-%d")
    return str(d.year if d.month >= 9 else d.year - 1)
