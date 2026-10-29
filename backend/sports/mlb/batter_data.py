"""Batter game logs from the free MLB StatsAPI (no key) for the hitting props
(hits, total bases, home runs).

Enumerates position players from the season roster
(``/sports/1/players?season=YYYY`` -> people[], drop pitchers), fetches each
candidate's per-game hitting log, and keeps regulars only (>= MIN_GAMES games in
the season) to bound the fetch. One row per batter-game with hits, totalBases,
homeRuns and atBats. Cached per season to ``data/mlb/batter_games_{year}.parquet``.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List, Sequence

import pandas as pd

_STATS = "https://statsapi.mlb.com/api/v1/people/{pid}/stats"
_PLAYERS = "https://statsapi.mlb.com/api/v1/sports/1/players"
_CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "mlb"
# team (canonical) + name are captured at fetch time for slate filtering / card labels;
# they are constant per batter, NOT model features (see batter_features.FEATURE_COLS).
_COLS = ["batter_id", "season", "date", "hits", "totalBases", "homeRuns", "atBats",
         "is_home", "team", "name"]

MIN_GAMES = 40         # regulars only: drop bench/callup batters to bound the fetch
MAX_CANDIDATES = 400   # hard cap on hitters fetched per season (defensive; regulars fit well under this)


def _hitters(year: int) -> List[dict]:
    """Position players (primaryPosition != 'P') on the season roster, each tagged
    with its canonical team (from ``currentTeam``) and display name, captured here
    so the slate enumerator can filter batters to the day's teams and label cards.
    Deduped by id, capped for a bounded fetch."""
    import requests

    from sports.mlb.teams import canonical_team
    try:
        r = requests.get(_PLAYERS, params={"season": year}, timeout=60)
        people = r.json().get("people", []) or []
    except Exception:
        return []
    seen: dict = {}
    for p in people:
        pos = ((p.get("primaryPosition") or {}).get("abbreviation") or "").upper()
        if not pos or pos == "P":
            continue
        pid = p.get("id")
        if pid is None:
            continue
        team = canonical_team((p.get("currentTeam") or {}).get("name", ""), strict=False)
        seen[int(pid)] = {"id": int(pid), "team": team, "name": p.get("fullName") or str(pid)}
    return sorted(seen.values(), key=lambda h: h["id"])[:MAX_CANDIDATES]


def _fetch_batter(pid: int, season: int, team: str = "", name: str = "") -> List[dict]:
    """This batter's per-game hitting log for the season. Returns [] on any error
    OR if the batter is not a regular (< MIN_GAMES games) so we don't retain
    noisy small-sample bench players. ``team``/``name`` are stamped onto every row."""
    import requests
    try:
        r = requests.get(_STATS.format(pid=pid),
                         params={"stats": "gameLog", "group": "hitting", "season": season}, timeout=20)
        stats = r.json().get("stats", [])
        splits = stats[0]["splits"] if stats else []
    except Exception:
        return []
    if len(splits) < MIN_GAMES:      # usage gate at the fetch level: regulars only
        return []
    rows = []
    for sp in splits:
        st = sp.get("stat", {})
        rows.append({
            "batter_id": pid, "season": season, "date": sp.get("date"),
            "hits": float(st.get("hits", 0) or 0),
            "totalBases": float(st.get("totalBases", 0) or 0),
            "homeRuns": float(st.get("homeRuns", 0) or 0),
            "atBats": float(st.get("atBats", 0) or 0),
            "is_home": 1 if sp.get("isHome") else 0,
            "team": team, "name": name,
        })
    return rows


def build_batter_games(years: Sequence[int]) -> pd.DataFrame:
    cur = datetime.now().year
    frames = []
    for y in years:
        cache = _CACHE_DIR / f"batter_games_{y}.parquet"
        if y < cur and cache.exists():
            frames.append(pd.read_parquet(cache))
            continue
        rows: List[dict] = []
        for h in _hitters(int(y)):
            rows.extend(_fetch_batter(h["id"], int(y), h["team"], h["name"]))
        df = pd.DataFrame(rows, columns=_COLS)
        if y < cur and not df.empty:
            _CACHE_DIR.mkdir(parents=True, exist_ok=True)
            df.to_parquet(cache, index=False)
        frames.append(df)
    out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=_COLS)
    if not out.empty:
        out["date"] = pd.to_datetime(out["date"], errors="coerce")
    return out
