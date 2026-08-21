"""Canonical NFL team identity (nflverse convention) + aliases.

nflverse standardizes to 32 current abbreviations; historical / feed variants
(OAK, SD, STL, LA, JAC, WSH, ...) fold to the current franchise.
"""
from __future__ import annotations

from typing import Dict, FrozenSet

CANONICAL_TEAMS: FrozenSet[str] = frozenset({
    "ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE", "DAL", "DEN", "DET",
    "GB", "HOU", "IND", "JAX", "KC", "LAC", "LAR", "LV", "MIA", "MIN", "NE",
    "NO", "NYG", "NYJ", "PHI", "PIT", "SEA", "SF", "TB", "TEN", "WAS",
})

# Relocations + common feed spellings -> current canonical code.
_ALIASES: Dict[str, str] = {
    "OAK": "LV", "LVR": "LV",                 # Raiders: Oakland -> Las Vegas
    "SD": "LAC",                              # Chargers: San Diego -> LA
    "STL": "LAR", "LA": "LAR",                # Rams: St. Louis / "LA" -> LAR
    "JAC": "JAX",                             # Jaguars spelling
    "WSH": "WAS", "WFT": "WAS",               # Washington variants
    "GNB": "GB", "KAN": "KC", "SFO": "SF", "TAM": "TB", "NWE": "NE", "NOR": "NO",
    "CLV": "CLE", "ARZ": "ARI", "BLT": "BAL", "HST": "HOU",  # PFR-style variants
}


def canonical_team(code: str, *, strict: bool = True) -> str:
    if code is None:
        raise ValueError("team code is None")
    c = str(code).strip().upper()
    if c in CANONICAL_TEAMS:
        return c
    if c in _ALIASES:
        return _ALIASES[c]
    if strict:
        raise ValueError(f"Unknown NFL team code: {code!r}")
    return c


def is_canonical(code: str) -> bool:
    return str(code).strip().upper() in CANONICAL_TEAMS
