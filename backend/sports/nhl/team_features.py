"""NHL team-game features for the goal score/margin/total model.

Same leakage discipline as the other sports: prior-only season-to-date expanding
means (shifted a game), last-10 form, rest, prior-season goal differential. The
dominant NHL swing, the starting GOALIE, is a planned enhancement (the schedule
endpoint only exposes the post-game winning goalie, so a pre-game goalie signal
needs the boxscore); the market anchor is NHL's real accuracy lever meanwhile.
"""
from __future__ import annotations

from typing import Dict, List

import numpy as np
import pandas as pd

from sports.nhl.data import load_team_games

_ORDER = ["OFF", "DEF", "WINPCT", "FORM", "REST", "PRIOR_DIFF"]
TEAM_FEATURE_COLS: List[str] = (
    [f"HOME_{k}" for k in _ORDER] + [f"AWAY_{k}" for k in _ORDER] + ["NET_DIFF", "REST_DIFF"]
)
# League-typical fills (NHL ~3.1 goals/team/game).
_FILL = {"OFF": 3.1, "DEF": 3.1, "WINPCT": 0.5, "FORM": 0.0, "REST": 1.0, "PRIOR_DIFF": 0.0}


def _team_timeline(tg: pd.DataFrame) -> pd.DataFrame:
    tg = tg.copy()
    tg["game_date"] = pd.to_datetime(tg["game_date"])
    tg = tg.sort_values(["team", "game_date"]).reset_index(drop=True)
    tg["win"] = (tg["goals"] > tg["opp_goals"]).astype(float)
    tg["diff"] = tg["goals"] - tg["opp_goals"]

    grp = tg.groupby(["team", "season"], sort=False)
    tg["OFF"] = grp["goals"].transform(lambda s: s.shift(1).expanding().mean())
    tg["DEF"] = grp["opp_goals"].transform(lambda s: s.shift(1).expanding().mean())
    tg["WINPCT"] = grp["win"].transform(lambda s: s.shift(1).expanding().mean())
    tg["FORM"] = grp["diff"].transform(lambda s: s.shift(1).rolling(10, min_periods=1).mean())
    tg["REST"] = tg.groupby("team", sort=False)["game_date"].diff().dt.days.clip(lower=0, upper=7)

    sd = tg.groupby(["team", "season"])["diff"].mean().reset_index().rename(columns={"diff": "PRIOR_DIFF"})
    sd["season"] = sd["season"] + 1
    tg = tg.merge(sd, on=["team", "season"], how="left")

    for k in _ORDER:
        tg[k] = tg[k].fillna(_FILL[k])
    return tg


def _assemble(h: Dict[str, float], a: Dict[str, float]) -> Dict[str, float]:
    row = {f"HOME_{k}": h[k] for k in _ORDER}
    row.update({f"AWAY_{k}": a[k] for k in _ORDER})
    row["NET_DIFF"] = (h["OFF"] - h["DEF"]) - (a["OFF"] - a["DEF"])
    row["REST_DIFF"] = h["REST"] - a["REST"]
    return row


def build_team_game_frame(years) -> pd.DataFrame:
    tg = load_team_games(list(years))
    if tg.empty:
        return pd.DataFrame()
    tl = _team_timeline(tg)
    home = tl[tl["is_home"] == 1].set_index("game_id")
    away = tl[tl["is_home"] == 0].set_index("game_id")
    g = home.join(away, lsuffix="_h", rsuffix="_a", how="inner")

    rows = []
    for gid, r in g.iterrows():
        h = {k: float(r[f"{k}_h"]) for k in _ORDER}
        a = {k: float(r[f"{k}_a"]) for k in _ORDER}
        feat = _assemble(h, a)
        feat.update({
            "game_id": gid, "season": int(r["season_h"]), "game_date": r["game_date_h"],
            "home": r["team_h"], "away": r["team_a"],
            "home_goals": float(r["goals_h"]), "away_goals": float(r["goals_a"]),
            "y_margin": float(r["goals_h"] - r["goals_a"]), "y_total": float(r["goals_h"] + r["goals_a"]),
        })
        rows.append(feat)
    return pd.DataFrame(rows).sort_values("game_date").reset_index(drop=True)


def latest_team_features(tl: pd.DataFrame) -> Dict[str, Dict[str, float]]:
    out: Dict[str, Dict[str, float]] = {}
    for team, tdf in tl.sort_values("game_date").groupby("team"):
        r = tdf.iloc[-1]
        out[team] = {k: float(r[k]) for k in _ORDER}
    return out


def matchup_features(home: str, away: str, latest: Dict[str, Dict[str, float]]) -> pd.DataFrame:
    h = latest.get(home, dict(_FILL))
    a = latest.get(away, dict(_FILL))
    return pd.DataFrame([_assemble(h, a)])[TEAM_FEATURE_COLS]


def build_timeline(years) -> pd.DataFrame:
    tg = load_team_games(list(years))
    return _team_timeline(tg) if not tg.empty else pd.DataFrame()
