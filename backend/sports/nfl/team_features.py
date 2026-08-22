"""NFL team-game features for the score/margin/total model.

Same leakage discipline as NBA: every feature is prior-only (season-to-date
expanding means shifted by one game, last-3 form, rest days from the previous
game, prior-season point differential). Built from nflverse team game logs
(``sports.nfl.data.load_team_games``).

NFL specifics: ~17 games/season (sparse) so we lean on season-to-date + a
prior-season carryover; rest is high-signal (short weeks / off a bye).
"""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from sports.nfl.data import game_context, load_team_games

_ORDER = ["OFF", "DEF", "WINPCT", "FORM", "REST", "PRIOR_DIFF"]
# Game-level context features (market line, weather, division) — all pregame-known.
MARKET_COLS = ["MARKET_SPREAD", "MARKET_TOTAL"]
WEATHER_COLS = ["IS_DOME", "WIND", "TEMP"]
CTX_COLS = ["DIV_GAME"]
GAME_COLS = MARKET_COLS + WEATHER_COLS + CTX_COLS
_TEAM_COLS = [f"HOME_{k}" for k in _ORDER] + [f"AWAY_{k}" for k in _ORDER] + ["NET_DIFF", "REST_DIFF"]
TEAM_FEATURE_COLS: List[str] = _TEAM_COLS + GAME_COLS
# The score model ANCHORS on the market line (efficient market = accuracy ceiling)
# and learns only the residual from team/weather/context signal. Anchor columns
# (MARKET_SPREAD -> margin, MARKET_TOTAL -> total) are NOT residual features.
RESIDUAL_FEATURE_COLS: List[str] = _TEAM_COLS + WEATHER_COLS + CTX_COLS
MARGIN_ANCHOR, TOTAL_ANCHOR = "MARKET_SPREAD", "MARKET_TOTAL"
_FILL = {"OFF": 22.0, "DEF": 22.0, "WINPCT": 0.5, "FORM": 0.0, "REST": 7.0, "PRIOR_DIFF": 0.0}
_GAME_FILL = {"MARKET_SPREAD": 0.0, "MARKET_TOTAL": 44.0, "IS_DOME": 0, "WIND": 5.0, "TEMP": 60.0, "DIV_GAME": 0}
# Opponent-adjusted OFF/DEF (Rung 3, NFL-10/11). Kept as SEPARATE columns so
# TEAM_FEATURE_COLS / RESIDUAL_FEATURE_COLS (the existing trainer's set) are
# unchanged — the experiment harness toggles these via explicit feature_cols.
_OPP_ADJ = ["OFF_ADJ", "DEF_ADJ"]
OPP_ADJ_COLS = [f"HOME_{k}" for k in _OPP_ADJ] + [f"AWAY_{k}" for k in _OPP_ADJ]


def _team_timeline(tg: pd.DataFrame) -> pd.DataFrame:
    tg = tg.copy()
    tg["game_date"] = pd.to_datetime(tg["game_date"])
    tg = tg.sort_values(["team", "game_date"]).reset_index(drop=True)
    tg["win"] = (tg["pts"] > tg["opp_pts"]).astype(float)
    tg["diff"] = tg["pts"] - tg["opp_pts"]

    grp = tg.groupby(["team", "season"], sort=False)
    tg["OFF"] = grp["pts"].transform(lambda s: s.shift(1).expanding().mean())
    tg["DEF"] = grp["opp_pts"].transform(lambda s: s.shift(1).expanding().mean())
    tg["WINPCT"] = grp["win"].transform(lambda s: s.shift(1).expanding().mean())
    tg["FORM"] = grp["diff"].transform(lambda s: s.shift(1).rolling(3, min_periods=1).mean())
    tg["REST"] = tg.groupby("team", sort=False)["game_date"].diff().dt.days.clip(lower=0, upper=21)

    # Opponent adjustment (leakage-safe): attach each opponent's prior-only OFF/DEF
    # for THIS game (self-join on game_id, other team), then take the prior-only
    # mean over opponents already faced this season (schedule strength) and subtract
    # it from raw OFF/DEF. Both terms are prior-only -> no leakage.
    pair = tg[["game_id", "team", "OFF", "DEF"]].rename(
        columns={"team": "team_opp", "OFF": "OPP_OFF", "DEF": "OPP_DEF"})
    tg = tg.merge(pair, on="game_id")
    tg = tg[tg["team"] != tg["team_opp"]].drop(columns=["team_opp"])
    tg = tg.sort_values(["team", "game_date"]).reset_index(drop=True)
    g2 = tg.groupby(["team", "season"], sort=False)
    tg["OFF_ADJ"] = tg["OFF"] - g2["OPP_DEF"].transform(lambda s: s.shift(1).expanding().mean())
    tg["DEF_ADJ"] = tg["DEF"] - g2["OPP_OFF"].transform(lambda s: s.shift(1).expanding().mean())
    tg[_OPP_ADJ] = tg[_OPP_ADJ].fillna(0.0)      # first-of-season: neutral
    tg = tg.drop(columns=["OPP_OFF", "OPP_DEF"])

    # prior-season point differential carried into the next season
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
        for k in _OPP_ADJ:   # opponent-adjusted OFF/DEF (Rung 3)
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

    # merge game-level context (market line / weather / division) by game_id
    ctx = game_context(years)
    df = df.merge(ctx, on="game_id", how="left")
    for c, fill in _GAME_FILL.items():
        df[c] = pd.to_numeric(df.get(c), errors="coerce").fillna(fill)
    return df


def latest_team_features(tl: pd.DataFrame) -> Dict[str, Dict[str, float]]:
    """Each team's most recent prior-only feature vector (for inference)."""
    out: Dict[str, Dict[str, float]] = {}
    for team, tdf in tl.sort_values("game_date").groupby("team"):
        r = tdf.iloc[-1]
        out[team] = {k: float(r[k]) for k in _ORDER}
    return out


def matchup_features(home: str, away: str, latest: Dict[str, Dict[str, float]],
                     context: Optional[Dict[str, float]] = None) -> pd.DataFrame:
    h = latest.get(home, dict(_FILL))
    a = latest.get(away, dict(_FILL))
    row = _assemble(h, a)
    ctx = {**_GAME_FILL, **(context or {})}  # neutral game context unless caller supplies odds/weather
    row.update({k: ctx[k] for k in GAME_COLS})
    return pd.DataFrame([row])[TEAM_FEATURE_COLS]


def build_timeline(years) -> pd.DataFrame:
    """Team timeline (per team-game features) — for computing latest_team_features."""
    tg = load_team_games(list(years)).dropna(subset=["pts", "opp_pts"])
    return _team_timeline(tg)
