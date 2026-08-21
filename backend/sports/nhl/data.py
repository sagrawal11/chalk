"""NHL data adapter over the free NHL API (api-web.nhle.com, no key).

Normalizes schedules/results into the generic shapes:
- ``load_schedules``  -> one row per game (canonical teams, goals, status).
- ``load_team_games`` -> one row per team-game (score-model substrate).

Built from the per-team season endpoint (``club-schedule-season/{TEAM}/{SEASON}``),
deduped by game id — every game has >=1 current-franchise opponent, so iterating
the 32 current codes captures the whole league (relocated ARI/ATL games are
captured via their opponents and fold to UTA/WPG). Completed past seasons cache
to ``data/nhl/schedule_{year}.parquet``; the current season is always refetched.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List, Sequence

import pandas as pd

from sports.nhl.teams import CANONICAL_TEAMS, canonical_team

_API = "https://api-web.nhle.com/v1/club-schedule-season/{team}/{season}"
_CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "nhl"
_COLS = ["game_id", "season", "game_date", "home", "away", "home_goals", "away_goals", "status"]


def _fetch_season(year: int) -> pd.DataFrame:
    import requests

    code = f"{year}{year + 1}"
    seen = {}
    for team in sorted(CANONICAL_TEAMS):
        try:
            r = requests.get(_API.format(team=team, season=code), timeout=30)
            if not r.ok:
                continue
            games = r.json().get("games", [])
        except Exception:
            continue
        for g in games:
            if g.get("gameType") != 2:          # 2 = regular season
                continue
            gid = g.get("id")
            if gid in seen:
                continue
            ht, at = g.get("homeTeam", {}), g.get("awayTeam", {})
            seen[gid] = {
                "game_id": gid, "season": year, "game_date": str(g.get("gameDate"))[:10],
                "home": canonical_team(ht.get("abbrev", ""), strict=False),
                "away": canonical_team(at.get("abbrev", ""), strict=False),
                "home_goals": ht.get("score"), "away_goals": at.get("score"),
                "status": g.get("gameState"),
            }
    return pd.DataFrame(list(seen.values()), columns=_COLS)


def load_schedules(years: Sequence[int]) -> pd.DataFrame:
    cur = datetime.now().year
    frames = []
    for y in years:
        cache = _CACHE_DIR / f"schedule_{y}.parquet"
        if y < cur and cache.exists():
            frames.append(pd.read_parquet(cache))
            continue
        df = _fetch_season(int(y))
        if y < cur and not df.empty:
            _CACHE_DIR.mkdir(parents=True, exist_ok=True)
            df.to_parquet(cache, index=False)
        frames.append(df)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=_COLS)


def load_team_games(years: Sequence[int]) -> pd.DataFrame:
    """One row per team-game (home + away) for completed games."""
    s = load_schedules(years)
    s = s[s["status"].isin(["OFF", "FINAL"])].dropna(subset=["home_goals", "away_goals"])
    rows: List[dict] = []
    for _, r in s.iterrows():
        base = {"game_id": r["game_id"], "season": r["season"], "game_date": r["game_date"]}
        rows.append({**base, "team": r["home"], "opponent": r["away"], "is_home": 1,
                     "goals": float(r["home_goals"]), "opp_goals": float(r["away_goals"])})
        rows.append({**base, "team": r["away"], "opponent": r["home"], "is_home": 0,
                     "goals": float(r["away_goals"]), "opp_goals": float(r["home_goals"])})
    df = pd.DataFrame(rows)
    if not df.empty:
        df["game_date"] = pd.to_datetime(df["game_date"], errors="coerce")
    return df
