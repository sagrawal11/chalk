"""Team-level (game) features for the score/margin/total model.

Same leakage discipline as the player FeatureEngine: every rating is prior-only
(cumulative-through-previous-game via ``_load_team_ratings_timeline`` +
``merge_asof(direction="backward", allow_exact_matches=False)``), rest/B2B come
from ``_build_kaggle_team_schedule_meta``, and all team codes route through
``canonical_team``.

Train/inference parity: ``build_team_game_frame`` (training) and
``matchup_features`` (inference) both derive each side's pre-game rating as "the
latest timeline entry strictly before the game date", then feed the SAME
``_assemble`` step — so the model sees identical features at train and serve.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from config.paths import KAGGLE_TEAM_GAMES_PARQUET, TEAM_AVAILABILITY_PARQUET
from feature_engine import _build_kaggle_team_schedule_meta, _load_team_ratings_timeline
from sports.nba.teams import canonical_team

# Injury/availability signal (TM_OUT_* = baseline minutes/points of rotation
# players OUT) — the biggest driver the ratings-only model was blind to.
AVAIL_KEYS = ["OUT_MIN", "OUT_PTS", "OUT_COUNT", "TOP_OUT"]
_BASE_FEATURE_COLS: List[str] = [
    "HOME_OFF", "HOME_DEF", "HOME_NET", "HOME_PACE", "HOME_REST", "HOME_B2B",
    "AWAY_OFF", "AWAY_DEF", "AWAY_NET", "AWAY_PACE", "AWAY_REST", "AWAY_B2B",
    "NET_DIFF", "PACE_SUM", "REST_DIFF",
]
_AVAIL_FEATURE_COLS: List[str] = (
    [f"HOME_{k}" for k in AVAIL_KEYS] + [f"AWAY_{k}" for k in AVAIL_KEYS]
    + ["OUT_PTS_DIFF", "OUT_MIN_DIFF"]
)
_ELO_FEATURE_COLS: List[str] = ["HOME_ELO", "AWAY_ELO", "ELO_DIFF"]
# The model's feature contract (order matters — persisted with the artifact).
TEAM_FEATURE_COLS: List[str] = _BASE_FEATURE_COLS + _AVAIL_FEATURE_COLS + _ELO_FEATURE_COLS

_ELO_BASE, _ELO_K, _ELO_HOME = 1500.0, 20.0, 100.0
# League-typical fills for a team's very first game (no prior history); availability
# defaults to 0 (full roster) so it degrades gracefully when no report exists.
_FILL = {"OFF": 110.0, "DEF": 110.0, "NET": 0.0, "PACE": 99.0, "REST": 2.0, "B2B": 0.0,
         "OUT_MIN": 0.0, "OUT_PTS": 0.0, "OUT_COUNT": 0.0, "TOP_OUT": 0.0, "ELO": _ELO_BASE}


def _canon(s: pd.Series) -> pd.Series:
    return s.astype(str).map(lambda c: canonical_team(c, strict=False))


def _assemble(
    h: Dict[str, float], a: Dict[str, float]
) -> Dict[str, float]:
    """Combine one side's (OFF/DEF/NET/PACE/REST/B2B) dicts into the feature row."""
    row = {
        "HOME_OFF": h["OFF"], "HOME_DEF": h["DEF"], "HOME_NET": h["NET"],
        "HOME_PACE": h["PACE"], "HOME_REST": h["REST"], "HOME_B2B": h["B2B"],
        "AWAY_OFF": a["OFF"], "AWAY_DEF": a["DEF"], "AWAY_NET": a["NET"],
        "AWAY_PACE": a["PACE"], "AWAY_REST": a["REST"], "AWAY_B2B": a["B2B"],
    }
    row["NET_DIFF"] = h["NET"] - a["NET"]
    row["PACE_SUM"] = h["PACE"] + a["PACE"]
    row["REST_DIFF"] = h["REST"] - a["REST"]
    # availability: each side's vacated-rotation signal + the relative edge
    # (away has more out => positive => tilts toward home).
    for k in AVAIL_KEYS:
        row[f"HOME_{k}"] = h.get(k, 0.0)
        row[f"AWAY_{k}"] = a.get(k, 0.0)
    row["OUT_PTS_DIFF"] = a.get("OUT_PTS", 0.0) - h.get("OUT_PTS", 0.0)
    row["OUT_MIN_DIFF"] = a.get("OUT_MIN", 0.0) - h.get("OUT_MIN", 0.0)
    # Elo rating (MOV-adjusted) — a strong margin prior; diff carries home edge separately.
    row["HOME_ELO"] = h.get("ELO", _ELO_BASE)
    row["AWAY_ELO"] = a.get("ELO", _ELO_BASE)
    row["ELO_DIFF"] = h.get("ELO", _ELO_BASE) - a.get("ELO", _ELO_BASE)
    return row


def _elo_timeline(parquet_path: Path = KAGGLE_TEAM_GAMES_PARQUET) -> pd.DataFrame:
    """Per-(team, game_date) POST-game Elo (MOV multiplier, home advantage in the
    win-expectancy, 25% season regression). Merged backward-EXCLUSIVE like the
    ratings timeline => pre-game Elo at train time, current Elo at inference."""
    cols = ["game_id", "season", "game_date", "is_home_team", "team", "pts"]
    df = pd.read_parquet(parquet_path, columns=cols)
    df["team"] = _canon(df["team"])
    df["game_date"] = pd.to_datetime(df["game_date"])
    df = df.sort_values(["game_id", "game_date"]).drop_duplicates(["game_id", "is_home_team"], keep="first")
    grp = df.groupby("game_id")["is_home_team"]
    df = df[grp.transform("nunique").eq(2) & grp.transform("size").eq(2)]
    home = df[df["is_home_team"] == 1].set_index("game_id")
    away = df[df["is_home_team"] == 0].set_index("game_id")
    g = home.join(away, lsuffix="_h", rsuffix="_a", how="inner").sort_values("game_date_h")

    elo: Dict[str, float] = {}
    season_of: Dict[str, int] = {}
    rows: List[Dict[str, Any]] = []
    for _, r in g.iterrows():
        h, a, s, gd = r["team_h"], r["team_a"], int(r["season_h"]), r["game_date_h"]
        for t in (h, a):
            e = elo.get(t, _ELO_BASE)
            if season_of.get(t) is not None and season_of[t] != s:
                e = 0.75 * e + 0.25 * _ELO_BASE  # regress toward the mean each new season
            elo[t] = e
            season_of[t] = s
        eh, ea = elo[h], elo[a]
        exp_h = 1.0 / (1.0 + 10 ** (-((eh + _ELO_HOME) - ea) / 400.0))
        margin = float(r["pts_h"] - r["pts_a"])
        res_h = 1.0 if margin > 0 else 0.0
        mov = ((abs(margin) + 3.0) ** 0.8) / (7.5 + 0.006 * abs((eh + _ELO_HOME) - ea))
        delta = _ELO_K * mov * (res_h - exp_h)
        elo[h] = eh + delta
        elo[a] = ea - delta
        rows.append({"team": h, "game_date": gd, "ELO": elo[h]})
        rows.append({"team": a, "game_date": gd, "ELO": elo[a]})
    return pd.DataFrame(rows).sort_values("game_date").reset_index(drop=True)


def _availability(parquet_path: Path = TEAM_AVAILABILITY_PARQUET) -> Optional[pd.DataFrame]:
    if not Path(parquet_path).exists():
        return None
    av = pd.read_parquet(parquet_path)
    av["team"] = _canon(av["team"])
    av["game_date"] = pd.to_datetime(av["game_date"])
    return av.drop_duplicates(["team", "game_date"])


def _timeline(parquet_path: Path) -> pd.DataFrame:
    tl = _load_team_ratings_timeline(parquet_path)
    if tl is None or tl.empty:
        raise RuntimeError("team ratings timeline unavailable")
    tl = tl.copy()
    tl["team"] = _canon(tl["team"])
    tl["game_date"] = pd.to_datetime(tl["game_date"])
    return tl.sort_values("game_date")


def _schedule_meta(parquet_path: Path) -> pd.DataFrame:
    meta = _build_kaggle_team_schedule_meta(parquet_path)
    if meta is None or meta.empty:
        raise RuntimeError("schedule meta unavailable")
    meta = meta.copy()
    meta["team"] = _canon(meta["team"])
    meta["game_date"] = pd.to_datetime(meta["game_date"])
    return meta.drop_duplicates(["team", "game_date"])


def build_team_game_frame(parquet_path: Path = KAGGLE_TEAM_GAMES_PARQUET) -> pd.DataFrame:
    """One row per game (home perspective) with prior-only features + targets."""
    cols = ["game_id", "season", "game_date", "is_home_team", "team", "pts", "plus_minus"]
    df = pd.read_parquet(parquet_path, columns=cols)
    df["team"] = _canon(df["team"])
    df["game_date"] = pd.to_datetime(df["game_date"])

    # Dedupe to exactly one home + one away row per game_id.
    df = df.sort_values(["game_id", "game_date"]).drop_duplicates(
        ["game_id", "is_home_team"], keep="first"
    )
    grp = df.groupby("game_id")["is_home_team"]
    keep = grp.transform("nunique").eq(2) & grp.transform("size").eq(2)
    df = df[keep]

    # Prior-only pre-game ratings via backward-exclusive as-of merge.
    tl = _timeline(parquet_path)
    left = df.sort_values("game_date")
    df = pd.merge_asof(
        left,
        tl[["team", "game_date", "OFF_RATING", "DEF_RATING", "NET_RATING", "PACE"]],
        on="game_date", by="team", direction="backward", allow_exact_matches=False,
    ).rename(columns={
        "OFF_RATING": "PRE_OFF", "DEF_RATING": "PRE_DEF",
        "NET_RATING": "PRE_NET", "PACE": "PRE_PACE",
    })

    # Rolling Elo (prior-only via the same backward-exclusive as-of merge).
    el = _elo_timeline(parquet_path)
    df = pd.merge_asof(
        df.sort_values("game_date"), el,
        on="game_date", by="team", direction="backward", allow_exact_matches=False,
    ).rename(columns={"ELO": "PRE_ELO"})
    df["PRE_ELO"] = df["PRE_ELO"].fillna(_ELO_BASE)

    # Rest / B2B.
    meta = _schedule_meta(parquet_path)
    df = df.merge(
        meta[["team", "game_date", "team_days_rest", "team_is_b2b"]],
        on=["team", "game_date"], how="left",
    )

    # Fills for first-of-history rows.
    df["PRE_OFF"] = df["PRE_OFF"].fillna(_FILL["OFF"])
    df["PRE_DEF"] = df["PRE_DEF"].fillna(_FILL["DEF"])
    df["PRE_NET"] = df["PRE_NET"].fillna(_FILL["NET"])
    df["PRE_PACE"] = df["PRE_PACE"].fillna(_FILL["PACE"])
    df["team_days_rest"] = df["team_days_rest"].fillna(_FILL["REST"]).clip(0, 10)
    df["team_is_b2b"] = df["team_is_b2b"].fillna(0).astype(float)

    # Injury/availability (leakage-safe: rotation players OUT is same-day roster
    # info known pre-tip). Missing rows (older seasons w/o player logs) -> 0.
    av = _availability()  # reads TEAM_AVAILABILITY_PARQUET (distinct from the kaggle path)
    _AVC = ["TM_OUT_MIN", "TM_OUT_PTS", "TM_OUT_COUNT", "TM_TOP_OUT"]
    if av is not None:
        df = df.merge(av[["team", "game_date"] + _AVC], on=["team", "game_date"], how="left")
    for c in _AVC:
        # When availability data is absent entirely (fresh clone / CI without the
        # parquet), the whole column is missing -> default to 0.0. (df.get(c) then
        # returns None, and pd.to_numeric(None) is a scalar, not a Series.)
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
        else:
            df[c] = 0.0

    home = df[df["is_home_team"] == 1].set_index("game_id")
    away = df[df["is_home_team"] == 0].set_index("game_id")
    g = home.join(away, lsuffix="_h", rsuffix="_a", how="inner")

    rows: List[Dict[str, Any]] = []
    for gid, r in g.iterrows():
        h = {"OFF": r["PRE_OFF_h"], "DEF": r["PRE_DEF_h"], "NET": r["PRE_NET_h"],
             "PACE": r["PRE_PACE_h"], "REST": r["team_days_rest_h"], "B2B": r["team_is_b2b_h"],
             "OUT_MIN": r["TM_OUT_MIN_h"], "OUT_PTS": r["TM_OUT_PTS_h"],
             "OUT_COUNT": r["TM_OUT_COUNT_h"], "TOP_OUT": r["TM_TOP_OUT_h"],
             "ELO": r["PRE_ELO_h"]}
        a = {"OFF": r["PRE_OFF_a"], "DEF": r["PRE_DEF_a"], "NET": r["PRE_NET_a"],
             "PACE": r["PRE_PACE_a"], "REST": r["team_days_rest_a"], "B2B": r["team_is_b2b_a"],
             "OUT_MIN": r["TM_OUT_MIN_a"], "OUT_PTS": r["TM_OUT_PTS_a"],
             "OUT_COUNT": r["TM_OUT_COUNT_a"], "TOP_OUT": r["TM_TOP_OUT_a"],
             "ELO": r["PRE_ELO_a"]}
        feat = _assemble(h, a)
        feat.update({
            "game_id": gid,
            "season": int(r["season_h"]),
            "game_date": r["game_date_h"],
            "home": r["team_h"],
            "away": r["team_a"],
            "home_pts": float(r["pts_h"]),
            "away_pts": float(r["pts_a"]),
            "y_margin": float(r["pts_h"] - r["pts_a"]),
            "y_total": float(r["pts_h"] + r["pts_a"]),
        })
        rows.append(feat)
    out = pd.DataFrame(rows).sort_values("game_date").reset_index(drop=True)
    return out


def _side_asof(team: str, game_date: pd.Timestamp, tl: pd.DataFrame, meta: pd.DataFrame,
               avail: Optional[pd.DataFrame] = None, elo_tl: Optional[pd.DataFrame] = None) -> Dict[str, float]:
    """Pre-game rating + rest + availability + Elo for one team as-of a date (inference parity)."""
    tsub = tl[(tl["team"] == team) & (tl["game_date"] < game_date)]
    if len(tsub):
        last = tsub.iloc[-1]
        off, dfn, net, pace = float(last["OFF_RATING"]), float(last["DEF_RATING"]), float(last["NET_RATING"]), float(last["PACE"])
    else:
        off, dfn, net, pace = _FILL["OFF"], _FILL["DEF"], _FILL["NET"], _FILL["PACE"]
    msub = meta[(meta["team"] == team) & (meta["game_date"] < game_date)]
    if len(msub):
        gap = (game_date - msub.iloc[-1]["game_date"]).days
        rest = float(min(max(gap, 0), 10))
        b2b = 1.0 if gap <= 1 else 0.0
    else:
        rest, b2b = _FILL["REST"], _FILL["B2B"]
    out = {k: _FILL[k] for k in AVAIL_KEYS}
    if avail is not None:
        asub = avail[(avail["team"] == team) & (avail["game_date"] == game_date)]
        if len(asub):
            r = asub.iloc[-1]
            out = {"OUT_MIN": float(r["TM_OUT_MIN"]), "OUT_PTS": float(r["TM_OUT_PTS"]),
                   "OUT_COUNT": float(r["TM_OUT_COUNT"]), "TOP_OUT": float(r["TM_TOP_OUT"])}
    elo = _ELO_BASE
    if elo_tl is not None:
        esub = elo_tl[(elo_tl["team"] == team) & (elo_tl["game_date"] < game_date)]
        if len(esub):
            elo = float(esub.iloc[-1]["ELO"])
    return {"OFF": off, "DEF": dfn, "NET": net, "PACE": pace, "REST": rest, "B2B": b2b, "ELO": elo, **out}


def matchup_features(
    home: str,
    away: str,
    game_date: str,
    *,
    parquet_path: Path = KAGGLE_TEAM_GAMES_PARQUET,
    timeline: Optional[pd.DataFrame] = None,
    meta: Optional[pd.DataFrame] = None,
    availability: Optional[pd.DataFrame] = None,
    elo: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """A single-row feature frame for an (unplayed) matchup, in TEAM_FEATURE_COLS
    order — built with the exact same primitives as training."""
    tl = timeline if timeline is not None else _timeline(parquet_path)
    md = meta if meta is not None else _schedule_meta(parquet_path)
    av = availability if availability is not None else _availability()
    el = elo if elo is not None else _elo_timeline(parquet_path)
    gd = pd.to_datetime(game_date)
    h = _side_asof(canonical_team(home), gd, tl, md, av, el)
    a = _side_asof(canonical_team(away), gd, tl, md, av, el)
    return pd.DataFrame([_assemble(h, a)])[TEAM_FEATURE_COLS]
