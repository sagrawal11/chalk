"""MLB team-game features for the run score/margin/total model.

Same leakage discipline as NBA/NFL: every feature is prior-only (season-to-date
expanding means shifted one game, last-10 form, rest days, prior-season run
differential). Built from MLB StatsAPI team game logs (``sports.mlb.data``).

v1 is a team-strength model (runs for/against). The dominant MLB signal — the
probable STARTING PITCHER — and a market-total anchor are the planned next
enhancements (the MLB analogs of NFL's QB + line).
"""
from __future__ import annotations

from typing import Dict, List

import numpy as np
import pandas as pd

from sports.mlb.data import load_team_games

# SP_RA = the STARTING pitcher's rolling runs-allowed over his prior starts (the
# dominant MLB signal — who's on the mound tonight). Leakage-safe (prior starts).
# SP_ERA = the same pitcher's rolling EARNED-run average (ER*9/IP over prior
# starts). SP_RA is a coarse team-runs-allowed proxy (SP+bullpen); SP_ERA isolates
# the starter's own earned-run rate for a sharper pitcher signal. Both are kept.
_ORDER = ["OFF", "DEF", "WINPCT", "FORM", "REST", "PRIOR_DIFF", "SP_RA", "SP_ERA"]
TEAM_FEATURE_COLS: List[str] = (
    [f"HOME_{k}" for k in _ORDER] + [f"AWAY_{k}" for k in _ORDER]
    + ["NET_DIFF", "REST_DIFF", "SP_RA_DIFF", "SP_ERA_DIFF"]
)
# League-typical fills (MLB ~4.5 runs/team/game; starter ERA ~4.2).
_LEAGUE_ERA = 4.2
_FILL = {"OFF": 4.5, "DEF": 4.5, "WINPCT": 0.5, "FORM": 0.0, "REST": 1.0,
         "PRIOR_DIFF": 0.0, "SP_RA": 4.5, "SP_ERA": _LEAGUE_ERA}
_MIN_ERA_STARTS = 2   # need some prior starts before an ERA is meaningful


def _sp_era_by_game(years) -> pd.DataFrame:
    """Rolling starter ERA keyed by (pitcher_id, start date), leakage-safe.

    ERA over a window is aggregated as a RATIO OF SUMS — ``sum(ER)*9/sum(IP)``
    over the pitcher's PRIOR starts (shifted) — not a mean of per-start ratios,
    so short/blow-up outings are weighted by innings the way real ERA is. The
    value on a given start row reflects only starts strictly before it, so
    merging it onto that game's team-row (by home_sp/away_sp + game_date) never
    leaks the current game. Returns empty if the ER-bearing cache is absent.
    """
    from sports.mlb.pitcher_data import build_pitcher_starts

    starts = build_pitcher_starts(years)
    if starts.empty or "ER" not in starts.columns:
        return pd.DataFrame(columns=["pitcher_id", "date", "SP_ERA"])
    s = starts.copy()
    s["date"] = pd.to_datetime(s["date"], errors="coerce")
    s = s.dropna(subset=["date"]).sort_values(["pitcher_id", "date"]).reset_index(drop=True)
    g = s.groupby("pitcher_id", sort=False)
    er_c = g["ER"].transform(lambda x: x.shift(1).rolling(10, min_periods=_MIN_ERA_STARTS).sum())
    ip_c = g["IP"].transform(lambda x: x.shift(1).rolling(10, min_periods=_MIN_ERA_STARTS).sum())
    s["SP_ERA"] = (er_c * 9.0 / ip_c).replace([np.inf, -np.inf], np.nan)
    return s[["pitcher_id", "date", "SP_ERA"]]


def _team_timeline(tg: pd.DataFrame) -> pd.DataFrame:
    tg = tg.copy()
    tg["game_date"] = pd.to_datetime(tg["game_date"])
    tg = tg.sort_values(["team", "game_date"]).reset_index(drop=True)
    tg["win"] = (tg["runs"] > tg["opp_runs"]).astype(float)
    tg["diff"] = tg["runs"] - tg["opp_runs"]

    grp = tg.groupby(["team", "season"], sort=False)
    tg["OFF"] = grp["runs"].transform(lambda s: s.shift(1).expanding().mean())
    tg["DEF"] = grp["opp_runs"].transform(lambda s: s.shift(1).expanding().mean())
    tg["WINPCT"] = grp["win"].transform(lambda s: s.shift(1).expanding().mean())
    tg["FORM"] = grp["diff"].transform(lambda s: s.shift(1).rolling(10, min_periods=1).mean())
    tg["REST"] = tg.groupby("team", sort=False)["game_date"].diff().dt.days.clip(lower=0, upper=10)

    # Starting-pitcher rolling runs-allowed (prior starts only, per pitcher id).
    # opp_runs = runs the SP's team allowed that game (SP+bullpen proxy).
    if "sp" in tg.columns:
        sp_ra = (tg.sort_values(["sp", "game_date"]).groupby("sp", sort=False)["opp_runs"]
                 .transform(lambda s: s.shift(1).rolling(10, min_periods=2).mean()))
        tg["SP_RA"] = sp_ra
    else:
        tg["SP_RA"] = np.nan

    # Starting-pitcher rolling EARNED-run average, keyed by the game's SP id +
    # date (prior starts only, from the ER-bearing pitcher_starts cache). Sharper
    # than SP_RA because it isolates the starter's own earned runs from the
    # bullpen. Missing SP / no ER cache / too-few-prior-starts -> league-avg fill.
    tg["SP_ERA"] = np.nan
    if "sp" in tg.columns:
        era = _sp_era_by_game(sorted(tg["season"].dropna().astype(int).unique().tolist()))
        if not era.empty:
            key = tg["sp"].astype("Float64").astype("Int64")   # NaN-safe int key
            merged = pd.DataFrame({"pitcher_id": key, "date": tg["game_date"]}).merge(
                era, on=["pitcher_id", "date"], how="left")
            tg["SP_ERA"] = merged["SP_ERA"].to_numpy()

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
    # away starter allows more runs => tilts toward the home team
    row["SP_RA_DIFF"] = a["SP_RA"] - h["SP_RA"]
    row["SP_ERA_DIFF"] = a["SP_ERA"] - h["SP_ERA"]
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
            "home_runs": float(r["runs_h"]), "away_runs": float(r["runs_a"]),
            "y_margin": float(r["runs_h"] - r["runs_a"]), "y_total": float(r["runs_h"] + r["runs_a"]),
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
