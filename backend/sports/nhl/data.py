"""NHL data adapter over the free NHL API (api-web.nhle.com, no key).

Normalizes schedules/results into the generic shapes:
- ``load_schedules``  -> one row per game (canonical teams, goals, status).
- ``load_team_games`` -> one row per team-game (score-model substrate).

Built from the per-team season endpoint (``club-schedule-season/{TEAM}/{SEASON}``),
deduped by game id: every game has >=1 current-franchise opponent, so iterating
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


# Expected goals (MoneyPuck): the NHL analog of NFL EPA, the strongest team-quality
# signal beyond raw goals. We aggregate the ~120k shot-level rows/season down to one
# small row per team-game (total xG for + against) and cache THAT per season, so a
# backtest never re-downloads the 20MB shot file.
_XG_URL = "https://peter-tanner.com/moneypuck/downloads/shots_{year}.zip"
_XG_COLS = ["game_id", "team", "XGF_G", "XGA_G"]


def _fetch_team_xg(year: int) -> pd.DataFrame:
    """One row per team-game for one season: total expected goals FOR (shots the team
    took) and AGAINST (shots it faced), summed from MoneyPuck shot-level xGoal."""
    import io
    import zipfile

    import requests

    try:
        r = requests.get(_XG_URL.format(year=year), timeout=120)
        if not r.ok:
            return pd.DataFrame(columns=_XG_COLS)
        zf = zipfile.ZipFile(io.BytesIO(r.content))
        with zf.open(zf.namelist()[0]) as fh:
            s = pd.read_csv(fh, usecols=["season", "game_id", "teamCode", "xGoal"])
    except Exception:
        return pd.DataFrame(columns=_XG_COLS)
    # NHL 10-digit game id = season*1e6 + MoneyPuck within-season id (verified: the
    # reconstructed regular-season ids match the schedule 1:1; playoff ids (03xxx)
    # never match and drop out on the join downstream).
    s["gid"] = s["season"].astype(int) * 1_000_000 + s["game_id"].astype(int)
    per = s.groupby(["gid", "teamCode"], sort=False)["xGoal"].sum().reset_index(name="XGF_G")
    tot = s.groupby("gid")["xGoal"].sum()
    per["XGA_G"] = per["gid"].map(tot) - per["XGF_G"]       # against = game total - own
    per["team"] = per["teamCode"].map(lambda t: canonical_team(t, strict=False))
    per = per[per["team"] != ""]
    return per.rename(columns={"gid": "game_id"})[_XG_COLS]


def load_team_xg(years: Sequence[int]) -> pd.DataFrame:
    """Per team-game expected goals for/against for the given seasons, cached per
    completed season to data/nhl/xg_{year}.parquet (the aggregate, not the ~120k raw
    shots). Empty if the MoneyPuck feed is unavailable (engine stays offline-safe)."""
    cur = datetime.now().year
    frames: List[pd.DataFrame] = []
    for y in years:
        y = int(y)
        cache = _CACHE_DIR / f"xg_{y}.parquet"
        if y < cur and cache.exists():
            frames.append(pd.read_parquet(cache))
            continue
        df = _fetch_team_xg(y)
        if y < cur and not df.empty:
            _CACHE_DIR.mkdir(parents=True, exist_ok=True)
            df.to_parquet(cache, index=False)
        frames.append(df)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=_XG_COLS)
