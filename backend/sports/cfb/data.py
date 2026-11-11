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


# --- Player box-score feed (CFBD /games/players), for player-prop models --------
_PLAYER_API = "https://api.collegefootballdata.com/games/players"
# Box-score columns we extract (CFBD has no targets, so receptions is the receiving
# usage signal). Mirrors the NFL weekly-stats columns the player features expect.
PLAYER_STAT_COLS = ["passing_yards", "passing_tds", "attempts", "completions",
                    "carries", "rushing_yards", "rushing_tds",
                    "receptions", "receiving_yards", "receiving_tds"]
_PLAYER_COLS = (["game_id", "season", "week", "game_date", "team", "opponent",
                 "is_home", "player_id", "player_name"] + PLAYER_STAT_COLS)


def _num(s) -> float:
    try:
        return float(str(s).replace(",", ""))
    except (ValueError, TypeError):
        return 0.0


def _parse_team_players(team: str, categories: list) -> List[dict]:
    """Pivot one team's nested passing/rushing/receiving categories into one row
    per athlete with the box-score columns we model."""
    rows: Dict[str, dict] = {}

    def _row(aid: str, aname: str) -> dict:
        r = rows.get(aid)
        if r is None:
            r = {c: 0.0 for c in PLAYER_STAT_COLS}
            r.update({"player_id": aid, "player_name": aname, "team": team})
            rows[aid] = r
        return r

    for cat in categories or []:
        cname = cat.get("name")
        if cname not in ("passing", "rushing", "receiving"):
            continue
        for ty in cat.get("types", []):
            tyname = ty.get("name")
            for ath in ty.get("athletes", []):
                aid = str(ath.get("id", ""))
                if not aid:
                    continue
                r = _row(aid, str(ath.get("name", "")))
                stat = str(ath.get("stat", "")).strip()
                if cname == "passing" and tyname == "C/ATT" and "/" in stat:
                    c, a = stat.split("/", 1)
                    r["completions"], r["attempts"] = _num(c), _num(a)
                elif cname == "passing" and tyname == "YDS":
                    r["passing_yards"] = _num(stat)
                elif cname == "passing" and tyname == "TD":
                    r["passing_tds"] = _num(stat)
                elif cname == "rushing" and tyname == "CAR":
                    r["carries"] = _num(stat)
                elif cname == "rushing" and tyname == "YDS":
                    r["rushing_yards"] = _num(stat)
                elif cname == "rushing" and tyname == "TD":
                    r["rushing_tds"] = _num(stat)
                elif cname == "receiving" and tyname == "REC":
                    r["receptions"] = _num(stat)
                elif cname == "receiving" and tyname == "YDS":
                    r["receiving_yards"] = _num(stat)
                elif cname == "receiving" and tyname == "TD":
                    r["receiving_tds"] = _num(stat)
    return list(rows.values())


def _fetch_player_year(year: int, fbs_ids: set) -> pd.DataFrame:
    import requests

    hdr = {"Authorization": f"Bearer {_api_key()}"}
    out: List[dict] = []
    # CFB weeks: regular 0-16 (week 0 since ~2016), postseason bowls under week 1-4.
    for season_type, weeks in (("regular", range(0, 17)), ("postseason", range(1, 5))):
        for wk in weeks:
            try:
                r = requests.get(_PLAYER_API, headers=hdr, timeout=60,
                                 params={"year": year, "week": wk, "seasonType": season_type})
                r.raise_for_status()
                games = r.json()
            except Exception:
                continue
            if not isinstance(games, list):
                continue
            for g in games:
                gid = g.get("id")
                if gid not in fbs_ids:  # FBS-vs-FBS only (join to the games cache)
                    continue
                for tm in g.get("teams", []):
                    team = canonical_team(str(tm.get("team", "")), strict=False)
                    for prow in _parse_team_players(team, tm.get("categories", [])):
                        prow["game_id"] = gid
                        out.append(prow)
    return pd.DataFrame(out)


def load_player_games(years: Sequence[int]) -> pd.DataFrame:
    """One row per (FBS game, player) with box-score stats, cached per completed
    season to ``data/cfb/player_games_{year}.parquet`` (the aggregate, not the raw
    per-week pulls). Game context (season/week/date/opponent/home) is joined from
    the FBS-vs-FBS games cache, which also filters out non-FBS games."""
    cur = datetime.now().year
    frames: List[pd.DataFrame] = []
    for y in years:
        y = int(y)
        cache = _CACHE_DIR / f"player_games_{y}.parquet"
        if y < cur and cache.exists():
            frames.append(pd.read_parquet(cache))
            continue
        games = load_games([y])
        if games.empty:
            frames.append(pd.DataFrame(columns=_PLAYER_COLS))
            continue
        meta = games[["game_id", "season", "week", "game_date", "home", "away"]]
        df = _fetch_player_year(y, set(games["game_id"]))
        if df.empty:
            frames.append(pd.DataFrame(columns=_PLAYER_COLS))
            continue
        df = df.merge(meta, on="game_id", how="inner")
        df["is_home"] = (df["team"] == df["home"]).astype(int)
        df["opponent"] = df["away"].where(df["is_home"] == 1, df["home"])
        df = df[_PLAYER_COLS]
        if y < cur and not df.empty:
            _CACHE_DIR.mkdir(parents=True, exist_ok=True)
            df.to_parquet(cache, index=False)
        frames.append(df)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=_PLAYER_COLS)
