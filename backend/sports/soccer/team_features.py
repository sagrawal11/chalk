"""Soccer TEAM strength features for a Poisson (Dixon-Coles-lite) 3-way model.

Mirrors the other sports' leakage-safe philosophy: every team's attack/defense
rating on a given matchday is computed from that team's PRIOR games only
(shifted), so a match's own goals never leak into the ratings used to predict it.

A team's rolling ATTACK is (goals scored / league-average goals), DEFENSE is
(goals conceded / league-average goals), split by venue (home ratings from home
games, away ratings from away games). With those, the Poisson scoring rates are::

    lambda_home = home_attack * away_defense * home_field * league_avg_goals
    lambda_away = away_attack * home_defense              * league_avg_goals

and 1X2 probabilities come from summing independent Poisson scoreline
probabilities over goals 0..MAX_GOALS. Data source is football-data.co.uk EPL
season CSVs (free, no key): FTHG/FTAG per match.

Pure functions (``add_team_features``, ``predict_3way``) take a matches frame so
they are unit-testable with synthetic data and no network. ``build_epl_matches``
does the (cached-per-season) fetch.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from sports.soccer.teams import canonical_team

# --- config -----------------------------------------------------------------
_FD_URL = "https://www.football-data.co.uk/mmz4281/{ss}/E0.csv"
_CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "soccer"
# Season start-year -> football-data 4-digit season code (2021-22 = "2122").
_SEASON_CODES: Dict[int, str] = {2021: "2122", 2022: "2223", 2023: "2324", 2024: "2425"}

ROLL = 6            # rolling window (matches) for a team's attack/defense form
MIN_PRIOR = 3       # usage gate: need >= this many prior games for a data-backed rating
MAX_GOALS = 10      # scoreline grid cap for the Poisson sum
PRIOR_K = 5.0       # cross-season shrinkage pseudo-count: early-season ratings pull
                    # toward the team's prior-season level instead of neutral 1.0
HOME_FIELD = 1.19   # home multiplier on home attack; empirical EPL home/away goal
                    # ratio over 2021-22..2024-25 (mean home goals / mean away goals)
_LEAGUE_AVG_GOALS = 1.35  # a-priori per-team goals/game fallback when a season is thin

_MATCH_COLS = ["season", "date", "home", "away", "fthg", "ftag"]


# --- rating helpers ---------------------------------------------------------
def _prior_mean(s: pd.Series, window: int) -> pd.Series:
    """Rolling mean over the team's PRIOR games only (shifted; leakage-safe)."""
    return s.shift(1).rolling(window, min_periods=1).mean()


def _prior_count(s: pd.Series) -> pd.Series:
    return s.shift(1).rolling(len(s), min_periods=1).count().fillna(0.0)


def _blend_prior_season(long: pd.DataFrame, la: Dict) -> None:
    """In-place: shrink each (team, venue) attack/defense toward its PRIOR-SEASON
    average with a PRIOR_K pseudo-count, weighted by how few prior games exist this
    season. Leakage-safe — only the strictly-earlier season feeds the blend, and a
    team with no prior season keeps the neutral 1.0 cold-start."""
    seas = long.groupby(["season", "team", "venue"], sort=False).agg(
        s_gf=("gf", "mean"), s_ga=("ga", "mean")).reset_index()
    la_by = seas["season"].map(la).fillna(_LEAGUE_AVG_GOALS)
    seas["s_attack"] = seas["s_gf"] / la_by
    seas["s_defense"] = seas["s_ga"] / la_by
    # carry each season's average forward one season, preserving the key dtype so the
    # merge aligns whether seasons are ints or year-strings ("2021").
    nxt = seas["season"].astype(int) + 1
    seas["season"] = nxt.astype(str) if long["season"].dtype == object else nxt
    merged = long.merge(seas[["season", "team", "venue", "s_attack", "s_defense"]],
                        on=["season", "team", "venue"], how="left")
    w_prior = PRIOR_K / (long["n_prior"].to_numpy(dtype=float) + PRIOR_K)
    for col, scol in (("attack", "s_attack"), ("defense", "s_defense")):
        prior_val = merged[scol].fillna(1.0).to_numpy()   # no prior season -> neutral
        long[col] = (1.0 - w_prior) * long[col].to_numpy() + w_prior * prior_val


def add_team_features(matches: pd.DataFrame, *, roll: int = ROLL,
                      cross_season: bool = False) -> pd.DataFrame:
    """Attach leakage-safe rolling attack/defense ratings (per venue) to a match
    frame with columns season/date/home/away/fthg/ftag.

    For each season we compute the league-average per-team goals, then for each
    team a rolling (prior-only) mean of goals-for and goals-against, split into
    HOME rows (from that team's home games) and AWAY rows (from away games). The
    result carries, per match, the four ratings the Poisson model needs plus the
    prior-game counts for the usage gate.

    ``roll`` sizes the rolling form window. ``cross_season`` (default off) blends
    each team's PRIOR-SEASON average rating into the current season with a
    ``PRIOR_K`` pseudo-count, so early-season matches lean on last year's strength
    instead of the neutral 1.0 cold-start (still leakage-safe — the prior season is
    strictly earlier). Both are pre-registered experiment knobs; the defaults
    reproduce the shipped predictor exactly.
    """
    if matches.empty:
        return matches.assign(
            home_attack=[], home_defense=[], away_attack=[], away_defense=[],
            league_avg=[], home_n_prior=[], away_n_prior=[],
        )
    df = matches.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.sort_values(["season", "date"]).reset_index(drop=True)
    df["fthg"] = pd.to_numeric(df["fthg"], errors="coerce")
    df["ftag"] = pd.to_numeric(df["ftag"], errors="coerce")

    # League average per-team goals for each season (all goals / all team-games).
    la = {}
    for season, sdf in df.groupby("season"):
        tot = float(sdf["fthg"].sum() + sdf["ftag"].sum())
        n = 2.0 * float(len(sdf))
        la[season] = (tot / n) if n else _LEAGUE_AVG_GOALS
    df["league_avg"] = df["season"].map(la).fillna(_LEAGUE_AVG_GOALS)

    # Build a long per-(team, venue) view so rolling is naturally prior-only.
    home_view = df[["season", "date", "home", "fthg", "ftag"]].rename(
        columns={"home": "team", "fthg": "gf", "ftag": "ga"})
    home_view["venue"] = "home"
    away_view = df[["season", "date", "away", "ftag", "fthg"]].rename(
        columns={"away": "team", "ftag": "gf", "fthg": "ga"})
    away_view["venue"] = "away"
    long = pd.concat([home_view, away_view], ignore_index=True)
    long = long.sort_values(["season", "team", "venue", "date"]).reset_index(drop=True)

    g = long.groupby(["season", "team", "venue"], sort=False)
    long["gf_roll"] = g["gf"].transform(lambda s: _prior_mean(s, roll))
    long["ga_roll"] = g["ga"].transform(lambda s: _prior_mean(s, roll))
    long["n_prior"] = g["gf"].transform(_prior_count)

    la_series = long["season"].map(la).fillna(_LEAGUE_AVG_GOALS)
    # Ratings relative to the league; default to 1.0 (neutral) with no prior games.
    long["attack"] = (long["gf_roll"] / la_series).fillna(1.0)
    long["defense"] = (long["ga_roll"] / la_series).fillna(1.0)

    if cross_season:
        _blend_prior_season(long, la)

    hk = long[long["venue"] == "home"].set_index(["season", "team", "date"])
    ak = long[long["venue"] == "away"].set_index(["season", "team", "date"])

    def _lookup(col: str, side: str) -> pd.Series:
        src = hk if side == "home" else ak
        keys = list(zip(df["season"], df[side], df["date"]))
        return pd.Series(src[col].reindex(keys).to_numpy(), index=df.index)

    df["home_attack"] = _lookup("attack", "home").fillna(1.0)
    df["home_defense"] = _lookup("defense", "home").fillna(1.0)
    df["home_n_prior"] = _lookup("n_prior", "home").fillna(0.0)
    df["away_attack"] = _lookup("attack", "away").fillna(1.0)
    df["away_defense"] = _lookup("defense", "away").fillna(1.0)
    df["away_n_prior"] = _lookup("n_prior", "away").fillna(0.0)
    return df


# --- Poisson 3-way ----------------------------------------------------------
def _poisson_pmf_vec(lam: float, kmax: int) -> np.ndarray:
    """P(X=k) for k in 0..kmax for a Poisson(lam). scipy if present, else a
    numerically-stable recurrence so the module has no hard scipy dependency."""
    lam = max(1e-6, float(lam))
    ks = np.arange(0, kmax + 1)
    try:
        from scipy.stats import poisson
        return poisson.pmf(ks, lam)
    except Exception:
        # p_0 = e^-lam ; p_k = p_{k-1} * lam / k
        p = np.empty(kmax + 1)
        p[0] = np.exp(-lam)
        for k in range(1, kmax + 1):
            p[k] = p[k - 1] * lam / k
        return p


def three_way_from_lambdas(lambda_home: float, lambda_away: float,
                           max_goals: int = MAX_GOALS, *,
                           dixon_coles_rho: float = 0.0) -> Dict[str, float]:
    """P(home win)/P(draw)/P(away win) by summing independent Poisson scoreline
    probabilities over the 0..max_goals grid. Renormalized so the three sum to 1
    (mass beyond the grid cap is negligible but we normalize to be exact).

    ``dixon_coles_rho`` (0 = off, default) applies the Dixon-Coles (1997) low-score
    dependence correction to the four cells {0-0, 0-1, 1-0, 1-1} before summing —
    a negative rho inflates 0-0/1-1 (draws) and is the standard fix for the
    independent-Poisson model under-predicting draws. rho is pre-registered per
    experiment (not fit on the test set)."""
    ph = _poisson_pmf_vec(lambda_home, max_goals)
    pa = _poisson_pmf_vec(lambda_away, max_goals)
    grid = np.outer(ph, pa)  # grid[i, j] = P(home=i, away=j)
    if dixon_coles_rho:
        lh, la = max(1e-6, float(lambda_home)), max(1e-6, float(lambda_away))
        rho = float(dixon_coles_rho)
        grid[0, 0] *= 1.0 - lh * la * rho
        grid[0, 1] *= 1.0 + lh * rho
        grid[1, 0] *= 1.0 + la * rho
        grid[1, 1] *= 1.0 - rho
        np.clip(grid, 0.0, None, out=grid)   # a large rho can push a tiny cell negative
    p_home = float(np.tril(grid, -1).sum())   # i > j
    p_away = float(np.triu(grid, 1).sum())    # j > i
    p_draw = float(np.trace(grid))            # i == j
    s = p_home + p_draw + p_away
    if s <= 0:
        return {"p_home": 0.45, "p_draw": 0.27, "p_away": 0.28}
    return {"p_home": p_home / s, "p_draw": p_draw / s, "p_away": p_away / s}


def predict_3way(home: str, away: str, ratings: Dict[str, Dict[str, float]], *,
                 league_avg: float = _LEAGUE_AVG_GOALS, home_field: float = HOME_FIELD,
                 max_goals: int = MAX_GOALS, min_prior: int = MIN_PRIOR
                 ) -> Optional[Dict[str, float]]:
    """3-way probabilities + expected total for a fixture, from precomputed team
    ratings (see ``latest_team_ratings``). Returns ``None`` when either team lacks
    data-backed home/away ratings (so the caller can fall back), else::

        {p_home, p_draw, p_away, total, lambda_home, lambda_away}

    lambda_home = home_attack * away_defense * home_field * league_avg
    lambda_away = away_attack * home_defense              * league_avg
    """
    hc, ac = canonical_team(home, strict=False), canonical_team(away, strict=False)
    rh, ra = ratings.get(hc), ratings.get(ac)
    if not rh or not ra:
        return None
    if rh.get("home_n_prior", 0) < min_prior or ra.get("away_n_prior", 0) < min_prior:
        return None
    la = float(league_avg) if league_avg and league_avg > 0 else _LEAGUE_AVG_GOALS
    lambda_home = float(rh["home_attack"]) * float(ra["away_defense"]) * float(home_field) * la
    lambda_away = float(ra["away_attack"]) * float(rh["home_defense"]) * la
    # Guard against pathological blow-ups; soccer team totals live in ~[0.2, 4].
    lambda_home = float(np.clip(lambda_home, 0.05, 6.0))
    lambda_away = float(np.clip(lambda_away, 0.05, 6.0))
    probs = three_way_from_lambdas(lambda_home, lambda_away, max_goals)
    probs["total"] = round(lambda_home + lambda_away, 3)
    probs["lambda_home"] = round(lambda_home, 3)
    probs["lambda_away"] = round(lambda_away, 3)
    return probs


def latest_team_ratings(matches: pd.DataFrame, *, window: int = ROLL) -> Dict[str, Dict[str, float]]:
    """Each team's ratings for their NEXT match — rolling over their most recent
    ACTUAL games (NOT the shifted training column, which is stale by one game).

    Uses the LATEST season present so ratings reflect the current squad, and the
    that season's league average. Keyed by canonical team name for inference.
    """
    if matches.empty:
        return {}
    df = matches.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    latest_season = df["season"].dropna().max()
    df = df[df["season"] == latest_season].copy()
    if df.empty:
        return {}
    df["fthg"] = pd.to_numeric(df["fthg"], errors="coerce")
    df["ftag"] = pd.to_numeric(df["ftag"], errors="coerce")
    tot = float(df["fthg"].sum() + df["ftag"].sum())
    n = 2.0 * float(len(df))
    la = (tot / n) if n else _LEAGUE_AVG_GOALS

    home_view = df[["date", "home", "fthg", "ftag"]].rename(
        columns={"home": "team", "fthg": "gf", "ftag": "ga"})
    home_view["venue"] = "home"
    away_view = df[["date", "away", "ftag", "fthg"]].rename(
        columns={"away": "team", "ftag": "gf", "fthg": "ga"})
    away_view["venue"] = "away"
    long = pd.concat([home_view, away_view], ignore_index=True)

    out: Dict[str, Dict[str, float]] = {}
    for team, tdf in long.groupby("team"):
        team = canonical_team(str(team), strict=False)
        rec = out.setdefault(team, {"league_avg": round(la, 4)})
        for venue in ("home", "away"):
            vdf = tdf[tdf["venue"] == venue].sort_values("date")
            n_prior = int(len(vdf))
            if n_prior:
                gf = float(vdf["gf"].tail(window).mean())
                ga = float(vdf["ga"].tail(window).mean())
                rec[f"{venue}_attack"] = gf / la if la else 1.0
                rec[f"{venue}_defense"] = ga / la if la else 1.0
            else:
                rec[f"{venue}_attack"] = 1.0
                rec[f"{venue}_defense"] = 1.0
            rec[f"{venue}_n_prior"] = n_prior
    return out


# --- data fetch (cached per season) -----------------------------------------
def _fetch_season(start_year: int) -> pd.DataFrame:
    ss = _SEASON_CODES.get(int(start_year))
    if ss is None:
        return pd.DataFrame(columns=_MATCH_COLS)
    import requests
    import io
    try:
        r = requests.get(_FD_URL.format(ss=ss), timeout=30)
        r.raise_for_status()
        raw = pd.read_csv(io.BytesIO(r.content), encoding="latin-1")
    except Exception:
        return pd.DataFrame(columns=_MATCH_COLS)
    need = {"HomeTeam", "AwayTeam", "FTHG", "FTAG"}
    if not need.issubset(raw.columns):
        return pd.DataFrame(columns=_MATCH_COLS)
    out = pd.DataFrame({
        "season": str(start_year),
        "date": pd.to_datetime(raw.get("Date"), dayfirst=True, errors="coerce"),
        "home": raw["HomeTeam"].map(lambda x: canonical_team(str(x), strict=False)),
        "away": raw["AwayTeam"].map(lambda x: canonical_team(str(x), strict=False)),
        "fthg": pd.to_numeric(raw["FTHG"], errors="coerce"),
        "ftag": pd.to_numeric(raw["FTAG"], errors="coerce"),
    }, columns=_MATCH_COLS)
    return out.dropna(subset=["home", "away", "fthg", "ftag"]).reset_index(drop=True)


def load_epl_raw(seasons: Sequence[int] = (2021, 2022, 2023, 2024)) -> pd.DataFrame:
    """Raw EPL match results (season/date/home/away/fthg/ftag) for the given season
    START years, cached per season. No features attached — the experiment harness
    applies ``add_team_features`` with each challenger's params."""
    from datetime import datetime
    cur = datetime.now().year
    frames: List[pd.DataFrame] = []
    for y in seasons:
        y = int(y)
        cache = _CACHE_DIR / f"epl_matches_{y}.parquet"
        if y < cur and cache.exists():
            frames.append(pd.read_parquet(cache))
            continue
        df = _fetch_season(y)
        if y < cur and not df.empty:
            _CACHE_DIR.mkdir(parents=True, exist_ok=True)
            df.to_parquet(cache, index=False)
        frames.append(df)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=_MATCH_COLS)


def build_epl_matches(seasons: Sequence[int] = (2021, 2022, 2023, 2024)) -> pd.DataFrame:
    """Fetch (and per-season cache) the football-data.co.uk EPL match results,
    returned with the shipped-default attack/defense features attached (reruns are
    fast: completed seasons read from parquet)."""
    return add_team_features(load_epl_raw(seasons))
