"""MLB data adapter over the free MLB StatsAPI (no key).

Normalizes schedules/results into the shapes the generic core expects:
- ``load_schedules``  -> one row per game (canonical teams, runs, probable
  starting pitchers, status).
- ``load_team_games`` -> one row per team-game (the score-model substrate,
  analogous to NFL's load_team_games).

Completed past seasons are cached to ``data/mlb/schedule_{year}.parquet``; the
current (in-progress) season is always refetched so lines/results stay live.
``requests`` is imported lazily so the module stays importable offline.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List, Sequence

import pandas as pd

from sports.mlb.teams import canonical_team

STATSAPI = "https://statsapi.mlb.com/api/v1/schedule"
_CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "mlb"
_COLS = ["game_id", "season", "game_date", "home", "away",
         "home_score", "away_score", "home_sp", "away_sp", "status"]


def _fetch_season(year: int) -> pd.DataFrame:
    import requests

    r = requests.get(STATSAPI, params={
        "sportId": 1, "startDate": f"{year}-03-01", "endDate": f"{year}-11-30",
        "gameType": "R", "hydrate": "probablePitcher"}, timeout=60)
    r.raise_for_status()
    rows: List[dict] = []
    for d in r.json().get("dates", []):
        for g in d.get("games", []):
            h, a = g["teams"]["home"], g["teams"]["away"]
            rows.append({
                "game_id": g.get("gamePk"), "season": year, "game_date": d["date"],
                "home": canonical_team(h["team"]["name"], strict=False),
                "away": canonical_team(a["team"]["name"], strict=False),
                "home_score": h.get("score"), "away_score": a.get("score"),
                "home_sp": (h.get("probablePitcher") or {}).get("id"),
                "away_sp": (a.get("probablePitcher") or {}).get("id"),
                "status": g.get("status", {}).get("abstractGameState"),
            })
    return pd.DataFrame(rows, columns=_COLS)


def load_schedules(years: Sequence[int]) -> pd.DataFrame:
    cur = datetime.now().year
    frames = []
    for y in years:
        cache = _CACHE_DIR / f"schedule_{y}.parquet"
        if y < cur and cache.exists():
            frames.append(pd.read_parquet(cache))
            continue
        df = _fetch_season(int(y))
        if y < cur and not df.empty:  # cache only completed seasons
            _CACHE_DIR.mkdir(parents=True, exist_ok=True)
            df.to_parquet(cache, index=False)
        frames.append(df)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=_COLS)


def load_team_games(years: Sequence[int]) -> pd.DataFrame:
    """One row per team-game (home + away) for completed games."""
    s = load_schedules(years)
    s = s[s["status"] == "Final"].dropna(subset=["home_score", "away_score"])
    rows: List[dict] = []
    for _, r in s.iterrows():
        base = {"game_id": r["game_id"], "season": r["season"], "game_date": r["game_date"]}
        rows.append({**base, "team": r["home"], "opponent": r["away"], "is_home": 1,
                     "runs": float(r["home_score"]), "opp_runs": float(r["away_score"]),
                     "sp": r["home_sp"], "opp_sp": r["away_sp"]})
        rows.append({**base, "team": r["away"], "opponent": r["home"], "is_home": 0,
                     "runs": float(r["away_score"]), "opp_runs": float(r["home_score"]),
                     "sp": r["away_sp"], "opp_sp": r["home_sp"]})
    df = pd.DataFrame(rows)
    if not df.empty:
        df["game_date"] = pd.to_datetime(df["game_date"], errors="coerce")
    return df
