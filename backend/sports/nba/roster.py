"""Roster → game context: map a player slug to their current team and, given a
slate, to their opponent + home/away. Powers prop content (player -> which game
they're in). Reads the player-log CSVs (PLAYER_TEAM of the latest game).
"""
from __future__ import annotations

import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from config.paths import PLAYER_DATA_DIR
from sports.nba.teams import canonical_team
from utils.names import player_slug


def _ascii(s: str) -> str:
    """Transliterate accents away (Jokić -> Jokic) so accented dir names and
    ASCII inputs resolve to the same key."""
    return unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode("ascii")


@lru_cache(maxsize=1)
def _slug_to_dir() -> Dict[str, str]:
    m: Dict[str, str] = {}
    base = Path(PLAYER_DATA_DIR)
    if base.exists():
        for d in base.iterdir():
            if d.is_dir():
                disp = d.name.replace("_", " ")
                # Index under both the raw slug (accent-stripped) and the
                # ascii-transliterated slug so "Jokić" and "Jokic" both resolve.
                m[player_slug(disp)] = d.name
                m.setdefault(player_slug(_ascii(disp)), d.name)
    return m


def clear_cache() -> None:
    _slug_to_dir.cache_clear()
    player_team.cache_clear()


def player_display_name(slug: str) -> str:
    d = _slug_to_dir().get(slug)
    return d.replace("_", " ") if d else slug.replace("_", " ").title()


@lru_cache(maxsize=8192)
def player_team(slug: str) -> Optional[str]:
    """Canonical current team from the player's most recent logged game."""
    m = _slug_to_dir()
    d = m.get(slug) or m.get(player_slug(_ascii(slug)))
    if not d:
        return None
    p = Path(PLAYER_DATA_DIR) / d / f"{d}_data.csv"
    if not p.exists():
        return None
    try:
        df = pd.read_csv(p, usecols=lambda c: c in ("GAME_DATE", "PLAYER_TEAM"))
    except Exception:
        return None
    if "PLAYER_TEAM" not in df.columns or df.empty:
        return None
    if "GAME_DATE" in df.columns:
        df = df.sort_values("GAME_DATE")
    vals = df["PLAYER_TEAM"].dropna()
    return canonical_team(vals.iloc[-1], strict=False) if len(vals) else None


def player_game_context(
    slug: str, games: List[Dict[str, str]], game_date: Optional[str] = None
) -> Optional[Dict]:
    """Which slate game the player is in: {team, opponent, is_home, game_key}."""
    team = player_team(slug)
    if not team:
        return None
    for g in games:
        h = canonical_team(g["home"], strict=False)
        a = canonical_team(g["away"], strict=False)
        gk = f"nba:{game_date}:{a}@{h}" if game_date else ""
        if team == h:
            return {"team": h, "opponent": a, "is_home": True, "game_key": gk}
        if team == a:
            return {"team": a, "opponent": h, "is_home": False, "game_key": gk}
    return None
