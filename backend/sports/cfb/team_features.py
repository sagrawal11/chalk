"""CFB team-game features for the score/margin/total model.

Mirrors the NFL engine (same leakage discipline: every feature is prior-only) since
CFB is also a sparse weekly schedule. Built from CFBD FBS-vs-FBS games
(``sports.cfb.data.load_team_games``).

CFB specifics: ~12-15 games/season; many neutral-site games (kickoff/bowls) so a
neutral flag replaces NFL's dome/weather; conference games replace division games;
bowls create long rest gaps (clipped wider than NFL). Opponent-adjusted OFFENSE is
served from the start (it was a clean keep for NFL; measured here too).
"""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from sports.cfb.data import game_context, load_team_games

_ORDER = ["OFF", "DEF", "WINPCT", "FORM", "REST", "PRIOR_DIFF"]
CTX_COLS = ["IS_NEUTRAL", "CONF_GAME"]
_TEAM_COLS = [f"HOME_{k}" for k in _ORDER] + [f"AWAY_{k}" for k in _ORDER] + ["NET_DIFF", "REST_DIFF"]
_OPP_ADJ = ["OFF_ADJ", "DEF_ADJ"]
OPP_ADJ_COLS = [f"HOME_{k}" for k in _OPP_ADJ] + [f"AWAY_{k}" for k in _OPP_ADJ]
OFF_ADJ_COLS = ["HOME_OFF_ADJ", "AWAY_OFF_ADJ"]
# Base set (for measuring without opp-adj) and the served set (with opp-adj offense).
BASE_FEATURE_COLS: List[str] = _TEAM_COLS + CTX_COLS
TEAM_FEATURE_COLS: List[str] = _TEAM_COLS + OFF_ADJ_COLS + CTX_COLS
_FILL = {"OFF": 28.0, "DEF": 28.0, "WINPCT": 0.5, "FORM": 0.0, "REST": 7.0, "PRIOR_DIFF": 0.0}
_CTX_FILL = {"IS_NEUTRAL": 0, "CONF_GAME": 0}


def _team_timeline(tg: pd.DataFrame) -> pd.DataFrame:
    tg = tg.copy()
    tg["game_date"] = pd.to_datetime(tg["game_date"])
    tg["season"] = pd.to_numeric(tg["season"], errors="coerce").astype(int)
    tg = tg.sort_values(["team", "game_date"]).reset_index(drop=True)
    tg["win"] = (tg["pts"] > tg["opp_pts"]).astype(float)
    tg["diff"] = tg["pts"] - tg["opp_pts"]

    grp = tg.groupby(["team", "season"], sort=False)
    tg["OFF"] = grp["pts"].transform(lambda s: s.shift(1).expanding().mean())
    tg["DEF"] = grp["opp_pts"].transform(lambda s: s.shift(1).expanding().mean())
    tg["WINPCT"] = grp["win"].transform(lambda s: s.shift(1).expanding().mean())
    tg["FORM"] = grp["diff"].transform(lambda s: s.shift(1).rolling(3, min_periods=1).mean())
    tg["REST"] = tg.groupby("team", sort=False)["game_date"].diff().dt.days.clip(lower=0, upper=45)

    # Opponent adjustment (leakage-safe), identical to the NFL engine: attach each
    # opponent's prior-only OFF/DEF via a self-join on game_id, take the prior-only
    # mean over opponents faced this season, and subtract from raw OFF/DEF.
    pair = tg[["game_id", "team", "OFF", "DEF"]].rename(
        columns={"team": "team_opp", "OFF": "OPP_OFF", "DEF": "OPP_DEF"})
    tg = tg.merge(pair, on="game_id")
    tg = tg[tg["team"] != tg["team_opp"]].drop(columns=["team_opp"])
    tg = tg.sort_values(["team", "game_date"]).reset_index(drop=True)
    g2 = tg.groupby(["team", "season"], sort=False)
    tg["OFF_ADJ"] = tg["OFF"] - g2["OPP_DEF"].transform(lambda s: s.shift(1).expanding().mean())
    tg["DEF_ADJ"] = tg["DEF"] - g2["OPP_OFF"].transform(lambda s: s.shift(1).expanding().mean())
    tg[_OPP_ADJ] = tg[_OPP_ADJ].fillna(0.0)
    tg = tg.drop(columns=["OPP_OFF", "OPP_DEF"])

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
    row["HOME_OFF_ADJ"] = h.get("OFF_ADJ", 0.0)
    row["AWAY_OFF_ADJ"] = a.get("OFF_ADJ", 0.0)
    return row


def build_team_game_frame(years) -> pd.DataFrame:
    tg = load_team_games(list(years))
    if tg.empty:
        return pd.DataFrame()
    tg = tg.dropna(subset=["pts", "opp_pts"])          # played games only
    tl = _team_timeline(tg)

    home = tl[tl["is_home"] == 1].set_index("game_id")
    away = tl[tl["is_home"] == 0].set_index("game_id")
    g = home.join(away, lsuffix="_h", rsuffix="_a", how="inner")

    rows = []
    for gid, r in g.iterrows():
        h = {k: float(r[f"{k}_h"]) for k in _ORDER}
        a = {k: float(r[f"{k}_a"]) for k in _ORDER}
        feat = _assemble(h, a)
        for k in _OPP_ADJ:
            feat[f"HOME_{k}"] = float(r[f"{k}_h"])
            feat[f"AWAY_{k}"] = float(r[f"{k}_a"])
        feat.update({
            "game_id": gid, "season": int(r["season_h"]), "game_date": r["game_date_h"],
            "home": r["team_h"], "away": r["team_a"],
            "home_pts": float(r["pts_h"]), "away_pts": float(r["pts_a"]),
            "y_margin": float(r["pts_h"] - r["pts_a"]), "y_total": float(r["pts_h"] + r["pts_a"]),
        })
        rows.append(feat)
    df = pd.DataFrame(rows).sort_values("game_date").reset_index(drop=True)

    ctx = game_context(years)
    df = df.merge(ctx, on="game_id", how="left")
    for c, fill in _CTX_FILL.items():
        df[c] = pd.to_numeric(df.get(c), errors="coerce").fillna(fill).astype(int)
    return df


def latest_team_features(tl: pd.DataFrame) -> Dict[str, Dict[str, float]]:
    """Each team's most recent prior-only feature vector (for inference)."""
    out: Dict[str, Dict[str, float]] = {}
    for team, tdf in tl.sort_values("game_date").groupby("team"):
        r = tdf.iloc[-1]
        feats = {k: float(r[k]) for k in _ORDER}
        feats["OFF_ADJ"] = float(r["OFF_ADJ"]) if "OFF_ADJ" in r.index else 0.0
        out[team] = feats
    return out


def matchup_features(home: str, away: str, latest: Dict[str, Dict[str, float]],
                     context: Optional[Dict[str, float]] = None) -> pd.DataFrame:
    h = latest.get(home, dict(_FILL))
    a = latest.get(away, dict(_FILL))
    row = _assemble(h, a)
    ctx = {**_CTX_FILL, **(context or {})}
    row.update({k: ctx[k] for k in CTX_COLS})
    return pd.DataFrame([row])[TEAM_FEATURE_COLS]


def build_timeline(years) -> pd.DataFrame:
    tg = load_team_games(list(years)).dropna(subset=["pts", "opp_pts"])
    return _team_timeline(tg)
