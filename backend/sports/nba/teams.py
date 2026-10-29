"""Canonical NBA team identity + season-format bridge.

A single choke point for team codes so every join (odds <-> predictions <->
team model <-> ESPN feeds) speaks one vocabulary. Folding franchise relocations
and feed-specific aliases here prevents the silent empty-join corruption that
mismatched codes cause.

Also bridges the two season encodings in the codebase (verified against
``kaggle_team_games.parquet``):
- the team parquet uses an int START year: 2024 == the 2024-25 season
  (season 2024 spans 2024-10-22 .. 2025-06-22).
- player CSVs / the predictor use the string "2024-25".

This module is NBA-specific and lives under the NBA plugin; other sports supply
their own equivalent behind the Sport interface.
"""
from __future__ import annotations

from typing import Dict, FrozenSet

# The 30 current franchises, in the abbreviations the pipeline standardizes on.
CANONICAL_TEAMS: FrozenSet[str] = frozenset({
    "ATL", "BKN", "BOS", "CHA", "CHI", "CLE", "DAL", "DEN", "DET", "GSW",
    "HOU", "IND", "LAC", "LAL", "MEM", "MIA", "MIL", "MIN", "NOP", "NYK",
    "OKC", "ORL", "PHI", "PHX", "POR", "SAC", "SAS", "TOR", "UTA", "WAS",
})

# ESPN abbreviation -> canonical (was duplicated in app.py:223 and
# collect_injuries.py:34; import from here to dedupe (PLANNING.md 10.6).
ESPN_TO_NBA_MAP: Dict[str, str] = {
    "GS": "GSW", "NO": "NOP", "NY": "NYK",
    "SA": "SAS", "UTAH": "UTA", "WSH": "WAS",
}

# Franchise relocations / feed-specific spellings -> canonical current code.
_ALIASES: Dict[str, str] = {
    # Nets: New Jersey -> Brooklyn; Basketball-Reference spells Brooklyn "BRK".
    "NJN": "BKN", "BRK": "BKN",
    # Pelicans lineage: New Orleans (OKC) Hornets -> Pelicans.
    "NOH": "NOP", "NOK": "NOP", "NOR": "NOP",
    # SuperSonics -> Thunder.
    "SEA": "OKC",
    # Common alternate spellings across feeds.
    "PHO": "PHX", "CHO": "CHA", "CHH": "CHA",
    **ESPN_TO_NBA_MAP,
}


def canonical_team(code: str, *, strict: bool = True) -> str:
    """Return the canonical current-franchise abbreviation for ``code``.

    Handles case/whitespace, franchise relocations, and feed-specific aliases.
    With ``strict=True`` (default) an unrecognized code raises ``ValueError``
    (fail loudly rather than corrupt a join); with ``strict=False`` the
    upper-cased input is returned unchanged.
    """
    if code is None:
        raise ValueError("team code is None")
    c = str(code).strip().upper()
    if c in CANONICAL_TEAMS:
        return c
    if c in _ALIASES:
        return _ALIASES[c]
    if strict:
        raise ValueError(f"Unknown team code: {code!r}")
    return c


def is_canonical(code: str) -> bool:
    return str(code).strip().upper() in CANONICAL_TEAMS


def season_int_to_str(year: int) -> str:
    """Int START year -> season string. 2024 -> '2024-25'."""
    y = int(year)
    return f"{y}-{str(y + 1)[-2:]}"


def season_str_to_int(season: str) -> int:
    """Season string -> int START year. '2024-25' -> 2024 (also '2024-2025')."""
    return int(str(season).strip().split("-")[0])
