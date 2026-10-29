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
