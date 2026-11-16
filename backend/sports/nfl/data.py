"""NFL data adapter over nflverse (nfl_data_py).

Normalizes the free nflverse feeds into the shapes the generic core expects:
- ``load_schedules``  -> games with canonical teams, scores, and built-in
  weather / rest / division context.
- ``load_team_games`` -> one row per team-game (the score-model substrate,
  analogous to NBA's kaggle_team_games).
- ``load_weekly_player_stats`` -> weekly player box for prop models.

``nfl_data_py`` is imported lazily so the plugin stays importable without it.
"""
from __future__ import annotations

from typing import List, Optional, Sequence

import pandas as pd

from sports.nfl.teams import canonical_team


def _canon(s: pd.Series) -> pd.Series:
    return s.astype(str).map(lambda t: canonical_team(t, strict=False))


def load_schedules(years: Sequence[int]) -> pd.DataFrame:
    import nfl_data_py as nfl

    s = nfl.import_schedules(list(years)).copy()
    s["home"] = _canon(s["home_team"])
    s["away"] = _canon(s["away_team"])
    s = s.rename(columns={"gameday": "game_date"})
    cols = ["game_id", "season", "week", "game_date", "home", "away",
            "home_score", "away_score",
            # situational context (already in nflverse, previously dropped)
            "temp", "wind", "roof", "div_game",
            "home_rest", "away_rest", "home_qb_id", "away_qb_id"]
    return s[[c for c in cols if c in s.columns]]


def game_context(years: Sequence[int]) -> pd.DataFrame:
    """One row per game_id with weather + situational context, derived into
    leakage-safe pregame features (all known before kickoff)."""
    s = load_schedules(years).copy()
    roof = s.get("roof", pd.Series(index=s.index, dtype=object)).astype(str).str.lower()
    is_dome = roof.isin(["dome", "closed"])
    ctx = pd.DataFrame({"game_id": s["game_id"]})
    # weather: domes have no wind and controlled temp; fill neutral there / when missing
    ctx["IS_DOME"] = is_dome.astype(int)
    ctx["WIND"] = pd.to_numeric(s.get("wind"), errors="coerce").where(~is_dome, 0.0)
    ctx["TEMP"] = pd.to_numeric(s.get("temp"), errors="coerce").where(~is_dome, 70.0)
    ctx["DIV_GAME"] = pd.to_numeric(s.get("div_game"), errors="coerce").fillna(0).astype(int)
    return ctx


def load_team_games(years: Sequence[int]) -> pd.DataFrame:
    """Explode schedules into one row per team-game (home + away)."""
    s = load_schedules(years)
    rows: List[dict] = []
    for _, r in s.iterrows():
        rows.append({
            "game_id": r["game_id"], "season": r["season"], "game_date": r["game_date"],
            "team": r["home"], "opponent": r["away"], "is_home": 1,
            "pts": r.get("home_score"), "opp_pts": r.get("away_score"),
        })
        rows.append({
            "game_id": r["game_id"], "season": r["season"], "game_date": r["game_date"],
            "team": r["away"], "opponent": r["home"], "is_home": 0,
            "pts": r.get("away_score"), "opp_pts": r.get("home_score"),
        })
    df = pd.DataFrame(rows)
    df["game_date"] = pd.to_datetime(df["game_date"], errors="coerce")
    return df


def load_weekly_player_stats(years: Sequence[int]) -> pd.DataFrame:
    """Weekly player box scores (passing/rushing/receiving) for prop models."""
    import nfl_data_py as nfl

    w = nfl.import_weekly_data(list(years)).copy()
    for col in ("recent_team", "opponent_team"):
        if col in w.columns:
            w[col] = _canon(w[col])
    return w


# EPA/play: the single most predictive team-efficiency signal. We aggregate the
# heavy play-by-play down to one small row per team-game (offensive EPA/play and
# defensive EPA/play allowed) and cache THAT per season, so a backtest never
# re-downloads ~50k plays/season.
import datetime as _dt  # noqa: E402
from pathlib import Path  # noqa: E402

_EPA_CACHE = Path(__file__).resolve().parents[2] / "data" / "nfl"
_EPA_COLS = ["game_id", "team", "OFF_EPA_G", "DEF_EPA_G"]


def _fetch_team_epa(year: int) -> pd.DataFrame:
    """One row per team-game for one season: mean offensive EPA/play (posteam) and
    mean defensive EPA/play allowed (defteam)."""
    import nfl_data_py as nfl

    try:
        p = nfl.import_pbp_data([year], downcast=True)
    except Exception:
        return pd.DataFrame(columns=_EPA_COLS)
    p = p[p["epa"].notna()]
    off = (p[p["posteam"].notna()].groupby(["game_id", "posteam"])["epa"].mean()
           .reset_index().rename(columns={"posteam": "team", "epa": "OFF_EPA_G"}))
    deff = (p[p["defteam"].notna()].groupby(["game_id", "defteam"])["epa"].mean()
            .reset_index().rename(columns={"defteam": "team", "epa": "DEF_EPA_G"}))
    out = off.merge(deff, on=["game_id", "team"], how="outer")
    out["team"] = _canon(out["team"])
    return out[_EPA_COLS]


def load_team_epa(years: Sequence[int]) -> pd.DataFrame:
    """Per team-game offensive + defensive EPA/play for the given seasons, cached
    per completed season to data/nfl/epa_{year}.parquet (the aggregate, not the raw
    play-by-play). Returns empty if nfl_data_py / the PBP feed is unavailable."""
    cur = _dt.date.today().year
    frames: List[pd.DataFrame] = []
    for y in years:
        y = int(y)
        cache = _EPA_CACHE / f"epa_{y}.parquet"
        if y < cur and cache.exists():
            frames.append(pd.read_parquet(cache))
            continue
        df = _fetch_team_epa(y)
        if y < cur and not df.empty:
            _EPA_CACHE.mkdir(parents=True, exist_ok=True)
            df.to_parquet(cache, index=False)
        frames.append(df)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=_EPA_COLS)


# QB-ADJUSTED EPA (NFL-43): attribute passing EPA to the ACTUAL starting QB, not the
# team. The team OFF_EPA rolls whoever played; this rolls the specific starter's prior
# passing EPA and attaches it via the confirmed starter (schedule home_qb_id/away_qb_id)
# - the one signal the team aggregate gets wrong on a QB injury/benching. Same
# aggregate-and-cache pattern; cached per season to data/nfl/qb_epa_{year}.parquet.
_QB_EPA_COLS = ["game_id", "passer_id", "QB_PEPA_G", "n_db"]
_QB_MIN_DB = 10   # dropbacks to count a game as a meaningful start (skip mop-up/trick plays)


def _fetch_qb_epa(year: int) -> pd.DataFrame:
    """Per (game_id, passer) mean passing EPA + dropback count for one season."""
    import nfl_data_py as nfl

    try:
        p = nfl.import_pbp_data([year], downcast=True)
    except Exception:
        return pd.DataFrame(columns=_QB_EPA_COLS)
    p = p[p["epa"].notna() & (p.get("pass") == 1) & p.get("passer_player_id").notna()]
    if p.empty:
        return pd.DataFrame(columns=_QB_EPA_COLS)
    g = (p.groupby(["game_id", "passer_player_id"])
         .agg(QB_PEPA_G=("epa", "mean"), n_db=("epa", "size")).reset_index()
         .rename(columns={"passer_player_id": "passer_id"}))
    return g[g["n_db"] >= _QB_MIN_DB][_QB_EPA_COLS]


def load_qb_epa(years: Sequence[int]) -> pd.DataFrame:
    """Per (game_id, passer) passing EPA, cached per completed season to
    data/nfl/qb_epa_{year}.parquet. Empty if the PBP feed is absent."""
    cur = _dt.date.today().year
    frames: List[pd.DataFrame] = []
    for y in years:
        y = int(y)
        cache = _EPA_CACHE / f"qb_epa_{y}.parquet"
        if y < cur and cache.exists():
            frames.append(pd.read_parquet(cache))
            continue
        df = _fetch_qb_epa(y)
        if y < cur and not df.empty:
            _EPA_CACHE.mkdir(parents=True, exist_ok=True)
            df.to_parquet(cache, index=False)
        frames.append(df)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=_QB_EPA_COLS)


def load_team_qb_epa(years: Sequence[int]) -> pd.DataFrame:
    """Per (game_id, team) the STARTING QB's prior-only rolling passing EPA (last-10
    starts, leakage-safe), attached via the schedule's confirmed starter. Returns
    [game_id, team, QB_EPA]; empty if the PBP feed is absent. The rolling lives here
    (per-QB, across seasons) because a team's starter changes - a per-team roll would
    mix QBs."""
    qb = load_qb_epa(years)
    if qb.empty:
        return pd.DataFrame(columns=["game_id", "team", "QB_EPA"])
    sched = load_schedules(years)
    qb = qb.merge(sched[["game_id", "game_date"]], on="game_id", how="left")
    qb["game_date"] = pd.to_datetime(qb["game_date"], errors="coerce")
    qb = qb.sort_values(["passer_id", "game_date"])
    qb["QB_EPA"] = (qb.groupby("passer_id", sort=False)["QB_PEPA_G"]
                    .transform(lambda s: s.shift(1).rolling(10, min_periods=3).mean()))
    # map the confirmed starter to each team-game
    rows: List[dict] = []
    for _, r in sched.iterrows():
        rows.append({"game_id": r["game_id"], "team": r["home"], "passer_id": r.get("home_qb_id")})
        rows.append({"game_id": r["game_id"], "team": r["away"], "passer_id": r.get("away_qb_id")})
    starters = pd.DataFrame(rows)
    out = starters.merge(qb[["game_id", "passer_id", "QB_EPA"]], on=["game_id", "passer_id"], how="left")
    out["team"] = _canon(out["team"])
    return out[["game_id", "team", "QB_EPA"]]
