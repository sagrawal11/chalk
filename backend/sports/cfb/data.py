"""CFB data adapter over the CollegeFootballData API (CFBD).

Mirrors the NFL adapter shape so the generic core treats CFB like any other sport:
- ``load_games``       -> one row per game with canonical teams, scores, context.
- ``load_team_games``  -> one row per team-game (the score-model substrate).
- ``game_context``     -> neutral-site + conference-game context per game_id.

FBS-vs-FBS games only, so team ratings are built against comparable competition
(FBS-vs-FCS blowouts add noise and the FCS side has no rating). Needs a CFBD API
key in ``CFBD_API_KEY`` (free at collegefootballdata.com; read from env or
backend/.env). Requests are cached per completed season to
``data/cfb/games_{year}.parquet`` so reruns are offline and fast.
"""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import List, Sequence

import pandas as pd

from sports.cfb.teams import canonical_team

_API = "https://api.collegefootballdata.com/games"
_ROOT = Path(__file__).resolve().parents[2]
_CACHE_DIR = _ROOT / "data" / "cfb"
_ENV_PATH = _ROOT / ".env"
_COLS = ["game_id", "season", "week", "game_date", "home", "away",
         "home_score", "away_score", "neutral", "conference_game"]


def _api_key() -> str:
    k = os.environ.get("CFBD_API_KEY")
    if not k and _ENV_PATH.exists():
        for line in _ENV_PATH.read_text().splitlines():
            if line.strip().startswith("CFBD_API_KEY="):
                k = line.split("=", 1)[1].strip()
                break
    if not k:
        raise RuntimeError("CFBD_API_KEY not set (env var or backend/.env)")
    return k


def _fetch_year(year: int) -> pd.DataFrame:
    import requests

    hdr = {"Authorization": f"Bearer {_api_key()}"}
    raw: List[dict] = []
    for season_type in ("regular", "postseason"):
        try:
            r = requests.get(_API, params={"year": year, "seasonType": season_type},
                             headers=hdr, timeout=30)
            r.raise_for_status()
            raw.extend(r.json())
        except Exception:
            continue
    if not raw:
        return pd.DataFrame(columns=_COLS)
    df = pd.DataFrame(raw)
    # FBS-vs-FBS only (comparable competition; FCS opponents have no rating).
    df = df[(df.get("homeClassification") == "fbs") & (df.get("awayClassification") == "fbs")]
    if df.empty:
        return pd.DataFrame(columns=_COLS)
    out = pd.DataFrame({
        "game_id": df["id"],
        "season": pd.to_numeric(df["season"], errors="coerce"),
        "week": pd.to_numeric(df.get("week"), errors="coerce"),
        "game_date": pd.to_datetime(df["startDate"], errors="coerce", utc=True).dt.tz_localize(None),
        "home": df["homeTeam"].map(lambda x: canonical_team(str(x), strict=False)),
        "away": df["awayTeam"].map(lambda x: canonical_team(str(x), strict=False)),
        "home_score": pd.to_numeric(df["homePoints"], errors="coerce"),
        "away_score": pd.to_numeric(df["awayPoints"], errors="coerce"),
        "neutral": df.get("neutralSite", False).fillna(False).astype(bool),
        "conference_game": df.get("conferenceGame", False).fillna(False).astype(bool),
    }, columns=_COLS)
    return out.dropna(subset=["season"]).reset_index(drop=True)


def load_games(years: Sequence[int]) -> pd.DataFrame:
    """FBS-vs-FBS games for the given seasons, cached per completed season."""
    cur = datetime.now().year
    frames: List[pd.DataFrame] = []
    for y in years:
        y = int(y)
        cache = _CACHE_DIR / f"games_{y}.parquet"
        if y < cur and cache.exists():
            frames.append(pd.read_parquet(cache))
            continue
        df = _fetch_year(y)
        if y < cur and not df.empty:
            _CACHE_DIR.mkdir(parents=True, exist_ok=True)
            df.to_parquet(cache, index=False)
        frames.append(df)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=_COLS)


def game_context(years: Sequence[int]) -> pd.DataFrame:
    """One row per game_id: neutral-site + conference-game flags (pregame-known)."""
    g = load_games(years)
    return pd.DataFrame({
        "game_id": g["game_id"],
        "IS_NEUTRAL": g["neutral"].astype(int),
        "CONF_GAME": g["conference_game"].astype(int),
    })


def load_team_games(years: Sequence[int]) -> pd.DataFrame:
    """Explode games into one row per team-game (home + away)."""
    g = load_games(years)
    rows: List[dict] = []
    for _, r in g.iterrows():
        rows.append({"game_id": r["game_id"], "season": r["season"], "game_date": r["game_date"],
                     "team": r["home"], "opponent": r["away"], "is_home": 1,
                     "pts": r.get("home_score"), "opp_pts": r.get("away_score")})
        rows.append({"game_id": r["game_id"], "season": r["season"], "game_date": r["game_date"],
                     "team": r["away"], "opponent": r["home"], "is_home": 0,
                     "pts": r.get("away_score"), "opp_pts": r.get("home_score")})
    df = pd.DataFrame(rows)
    df["game_date"] = pd.to_datetime(df["game_date"], errors="coerce")
    df["season"] = pd.to_numeric(df["season"], errors="coerce").astype("Int64")
    return df
