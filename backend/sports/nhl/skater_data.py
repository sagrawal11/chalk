"""Skater game logs from the free NHL API (api-web.nhle.com, no key) for the
points/shots prop models.

Enumerates skaters (forwards + defensemen; goalies skipped) from every team's
roster, fetches each skater's per-game log, and keeps their regular-season games
(points = goals+assists, shots on goal, time-on-ice). Cached per season to
``data/nhl/skater_games_{year}.parquet`` (season named by its START year, e.g.
2023 -> the 20232024 season). ``requests`` is imported lazily so the module
stays importable offline.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List, Sequence

import pandas as pd

from sports.nhl.teams import CANONICAL_TEAMS

_ROSTER = "https://api-web.nhle.com/v1/roster/{team}/{season}"
_GAMELOG = "https://api-web.nhle.com/v1/player/{pid}/game-log/{season}/2"  # 2 = regular
_CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "nhl"
# team (the canonical roster code) + name are captured at fetch time for slate
# filtering / card labels; constant per skater, NOT model features.
_COLS = ["player_id", "season", "date", "points", "shots", "toi", "is_home", "opp",
         "team", "name"]


def _toi_to_min(toi) -> float:
    # "17:58" = 17 minutes 58 seconds -> 17.967 minutes
    try:
        s = str(toi)
        mm, _, ss = s.partition(":")
        return float(mm) + (float(ss) / 60.0 if ss else 0.0)
    except Exception:
        return 0.0


def _skaters(year: int) -> List[dict]:
    """Skaters (forward + defenseman; goalies excluded) across all 32 rosters for
    the season, each tagged with its (canonical) roster team + display name, so the
    slate enumerator can filter to the day's teams and label cards. Deduped by id (a
    traded player can appear on >1 roster; last roster seen wins, fine for the
    current season, where each id is on exactly one roster)."""
    import requests

    code = f"{year}{year + 1}"
    seen: dict = {}
    for team in sorted(CANONICAL_TEAMS):
        try:
            r = requests.get(_ROSTER.format(team=team, season=code), timeout=30)
            if not r.ok:
                continue
            d = r.json()
        except Exception:
            continue
        for grp in ("forwards", "defensemen"):   # skip goalies
            for p in d.get(grp, []) or []:
                pid = p.get("id")
                if pid is None:
                    continue
                name = (((p.get("firstName") or {}).get("default", "") + " "
                         + (p.get("lastName") or {}).get("default", "")).strip())
                seen[int(pid)] = {"id": int(pid), "team": team, "name": name or str(pid)}
    return sorted(seen.values(), key=lambda s: s["id"])


def _fetch_skater(pid: int, year: int, team: str = "", name: str = "") -> List[dict]:
    import requests

    code = f"{year}{year + 1}"
    try:
        r = requests.get(_GAMELOG.format(pid=pid, season=code), timeout=20)
        gl = r.json().get("gameLog", []) if r.ok else []
    except Exception:
        return []
    rows = []
    for g in gl:
        rows.append({
            "player_id": pid, "season": year, "date": g.get("gameDate"),
            "points": float(g.get("points", 0) or 0),
            "shots": float(g.get("shots", 0) or 0),
            "toi": _toi_to_min(g.get("toi", 0)),
            "is_home": 1 if g.get("homeRoadFlag") == "H" else 0,
            "opp": g.get("opponentAbbrev") or "",
            "team": team, "name": name,
        })
    return rows


def build_skater_games(years: Sequence[int]) -> pd.DataFrame:
    cur = datetime.now().year
    frames = []
    for y in years:
        cache = _CACHE_DIR / f"skater_games_{y}.parquet"
        if y < cur and cache.exists():
            frames.append(pd.read_parquet(cache))
            continue
        rows: List[dict] = []
        for s in _skaters(int(y)):
            rows.extend(_fetch_skater(s["id"], int(y), s["team"], s["name"]))
        df = pd.DataFrame(rows, columns=_COLS)
        if y < cur and not df.empty:      # cache only completed seasons
            _CACHE_DIR.mkdir(parents=True, exist_ok=True)
            df.to_parquet(cache, index=False)
        frames.append(df)
    out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=_COLS)
    if not out.empty:
        out["date"] = pd.to_datetime(out["date"], errors="coerce")
    return out
