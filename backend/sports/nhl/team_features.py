"""NHL team-game features for the goal score/margin/total model.

Same leakage discipline as the other sports: prior-only season-to-date expanding
means (shifted a game), last-10 form, rest, prior-season goal differential. The
dominant NHL swing, the starting GOALIE, is a planned enhancement (the schedule
endpoint only exposes the post-game winning goalie, so a pre-game goalie signal
needs the boxscore); the market anchor is NHL's real accuracy lever meanwhile.
"""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from sports.nhl.data import load_team_games, load_team_xg

_ORDER = ["OFF", "DEF", "WINPCT", "FORM", "REST", "PRIOR_DIFF"]
# Expected goals for/against (MoneyPuck), rolling prior-only: the NHL analog of NFL
# EPA, the strongest team-quality signal beyond raw goals.
_XG = ["OFF_XG", "DEF_XG"]
XG_COLS = [f"HOME_{k}" for k in _XG] + [f"AWAY_{k}" for k in _XG]
TEAM_FEATURE_COLS: List[str] = (
    [f"HOME_{k}" for k in _ORDER] + [f"AWAY_{k}" for k in _ORDER] + ["NET_DIFF", "REST_DIFF"] + XG_COLS
)
# League-typical fills (NHL ~3.1 goals/team/game; xG ~2.9/team/game).
_FILL = {"OFF": 3.1, "DEF": 3.1, "WINPCT": 0.5, "FORM": 0.0, "REST": 1.0, "PRIOR_DIFF": 0.0}
_XG_FILL = 2.9   # neutral cold-start / absent-feed fill for OFF_XG/DEF_XG


def _team_timeline(tg: pd.DataFrame, xg_df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
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

    # xG/game rolling (prior-only), merged from the aggregated MoneyPuck feed.
    # Absent feed -> neutral fill (keeps the engine usable offline + tests hermetic).
    if xg_df is not None and not xg_df.empty:
        tg = tg.merge(xg_df.drop_duplicates(["game_id", "team"]), on=["game_id", "team"], how="left")
        gx = tg.groupby(["team", "season"], sort=False)
        tg["OFF_XG"] = gx["XGF_G"].transform(lambda s: s.shift(1).expanding().mean())
        tg["DEF_XG"] = gx["XGA_G"].transform(lambda s: s.shift(1).expanding().mean())
        tg = tg.drop(columns=[c for c in ("XGF_G", "XGA_G") if c in tg.columns])
    else:
        tg["OFF_XG"] = np.nan
        tg["DEF_XG"] = np.nan
    tg["OFF_XG"] = tg["OFF_XG"].fillna(_XG_FILL)
    tg["DEF_XG"] = tg["DEF_XG"].fillna(_XG_FILL)

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
    for k in _XG:   # expected goals off+def; neutral fill for cold-start / missing
        row[f"HOME_{k}"] = h.get(k, _XG_FILL)
        row[f"AWAY_{k}"] = a.get(k, _XG_FILL)
    return row


def build_team_game_frame(years) -> pd.DataFrame:
    tg = load_team_games(list(years))
    if tg.empty:
        return pd.DataFrame()
    tl = _team_timeline(tg, load_team_xg(years))
    home = tl[tl["is_home"] == 1].set_index("game_id")
    away = tl[tl["is_home"] == 0].set_index("game_id")
    g = home.join(away, lsuffix="_h", rsuffix="_a", how="inner")

    rows = []
    for gid, r in g.iterrows():
        h = {k: float(r[f"{k}_h"]) for k in _ORDER}
        a = {k: float(r[f"{k}_a"]) for k in _ORDER}
        feat = _assemble(h, a)
        for k in _XG:   # expected goals off+def (prior-only, from the joined timeline)
            feat[f"HOME_{k}"] = float(r[f"{k}_h"])
            feat[f"AWAY_{k}"] = float(r[f"{k}_a"])
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
        feats = {k: float(r[k]) for k in _ORDER}
        for k in _XG:
            feats[k] = float(r[k]) if k in r.index else _XG_FILL
        out[team] = feats
    return out


def matchup_features(home: str, away: str, latest: Dict[str, Dict[str, float]]) -> pd.DataFrame:
    h = latest.get(home, dict(_FILL))
    a = latest.get(away, dict(_FILL))
    return pd.DataFrame([_assemble(h, a)])[TEAM_FEATURE_COLS]


def build_timeline(years) -> pd.DataFrame:
    tg = load_team_games(list(years))
    return _team_timeline(tg, load_team_xg(years)) if not tg.empty else pd.DataFrame()
