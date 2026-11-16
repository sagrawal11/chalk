"""Season expected-stats (xwOBA) from Baseball Savant via pybaseball, as a
leakage-safe PRIOR-season quality prior for the pitcher-K and batter hit/TB props.

The light leaderboard (one CSV per season, ~700 rows) gives each pitcher's
xwOBA-against (est_woba) and each batter's xwOBA. We attach the PRIOR season's
value to a player's current-season games: it is constant within a season and
strictly in the past, so it is leakage-safe, and it carries a true-talent quality
level the recent-form rolls (K_L5 etc.) cannot see. Aggregated small and cached to
``data/mlb/xwoba_{kind}_{year}.parquet`` (the NHL-xG / NFL-EPA aggregate-and-cache
pattern), so the ~700-row leaderboard, not the raw pitch feed, is what we keep.

pybaseball is NOT in config/requirements.txt - added only if a feature built on this
is kept (same rule as soccerdata). The engine stays offline-safe: an absent feed /
missing prior-season row falls back to the league-average neutral fill.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Sequence

import pandas as pd

_CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "mlb"
_COLS = ["player_id", "season", "xwOBA", "pa"]
_MIN_PA = 50   # drop tiny-sample leaderboard rows (their xwOBA is noise)

# League-average xwOBA neutral fill for a player with no prior-season leaderboard
# row (rookie, missed the prior year, or the first season in the window). ~0.315
# both for pitchers-against and batters; keeps the feature offline-safe and the
# engine lean. ponytail: fixed neutral, swap to a prior-season league mean only if
# cross-era drift ever shows up in the measurement.
NEUTRAL_XWOBA = 0.315


def _fetch_expected(kind: str, year: int) -> pd.DataFrame:
    """One season's expected-stats leaderboard, narrowed to [player_id, season,
    xwOBA, pa]. Returns an empty frame on any error (offline-safe)."""
    import pybaseball as pb
    fn = (pb.statcast_pitcher_expected_stats if kind == "pitcher"
          else pb.statcast_batter_expected_stats)
    try:
        df = fn(year, minPA=_MIN_PA)
    except Exception:
        return pd.DataFrame(columns=_COLS)
    if df is None or df.empty or "est_woba" not in df.columns:
        return pd.DataFrame(columns=_COLS)
    out = pd.DataFrame({
        "player_id": pd.to_numeric(df["player_id"], errors="coerce"),
        "season": int(year),
        "xwOBA": pd.to_numeric(df["est_woba"], errors="coerce"),
        "pa": pd.to_numeric(df["pa"], errors="coerce"),
    }).dropna(subset=["player_id", "xwOBA"])
    out["player_id"] = out["player_id"].astype(int)
    return out.drop_duplicates(subset=["player_id", "season"])[_COLS]


def load_xwoba(kind: str, years: Sequence[int]) -> pd.DataFrame:
    """Per-season xwOBA leaderboard for ``kind`` in {'pitcher','batter'}, cached
    small per season (past seasons only; the current season is refetched live)."""
    cur = datetime.now().year
    frames = []
    for y in years:
        cache = _CACHE_DIR / f"xwoba_{kind}_{int(y)}.parquet"
        if int(y) < cur and cache.exists():
            frames.append(pd.read_parquet(cache))
            continue
        df = _fetch_expected(kind, int(y))
        if int(y) < cur and not df.empty:
            _CACHE_DIR.mkdir(parents=True, exist_ok=True)
            df.to_parquet(cache, index=False)
        frames.append(df)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=_COLS)


def add_prior_xwoba(df: pd.DataFrame, kind: str, id_col: str) -> pd.DataFrame:
    """Attach each player's PRIOR-season xwOBA to their games as ``xwOBA_prior``.

    Leakage-safe: a game in season Y joins the leaderboard row for season Y-1,
    which is strictly in the past. Cold-start (no prior-season row) gets the
    neutral fill, so the feature is offline-safe and never NaN.
    """
    df = df.copy()
    if df.empty:
        df["xwOBA_prior"] = pd.Series(dtype=float)
        return df
    seasons = pd.to_numeric(df["season"], errors="coerce").dropna().astype(int).unique()
    prior_years = sorted({int(s) - 1 for s in seasons})
    lb = load_xwoba(kind, prior_years)
    df["_prior_season"] = pd.to_numeric(df["season"], errors="coerce").astype("Int64") - 1
    if lb.empty:
        df["xwOBA_prior"] = NEUTRAL_XWOBA
        return df.drop(columns=["_prior_season"])
    lk = lb.rename(columns={"player_id": id_col, "season": "_prior_season",
                            "xwOBA": "xwOBA_prior"})[[id_col, "_prior_season", "xwOBA_prior"]]
    merged = df.merge(lk, on=[id_col, "_prior_season"], how="left")
    merged["xwOBA_prior"] = pd.to_numeric(merged["xwOBA_prior"], errors="coerce").fillna(NEUTRAL_XWOBA)
    return merged.drop(columns=["_prior_season"])


def demo() -> None:
    """Self-check: the prior-season join is leakage-safe (uses only season Y-1) and
    the neutral fill leaves no NaN. Run from backend/: python -m sports.mlb.statcast_data"""
    import numpy as np
    frame = pd.DataFrame({
        "pitcher_id": [571945, 571945, 999999],   # Mikolas x2 (has 2023 xwOBA), a fake rookie
        "season": [2024, 2024, 2024],
        "date": pd.to_datetime(["2024-04-01", "2024-04-08", "2024-04-01"]),
    })
    out = add_prior_xwoba(frame, "pitcher", "pitcher_id")
    assert "xwOBA_prior" in out.columns and len(out) == 3
    assert out["xwOBA_prior"].notna().all(), "neutral fill must leave no NaN"
    rookie = out[out["pitcher_id"] == 999999]["xwOBA_prior"].iloc[0]
    assert abs(rookie - NEUTRAL_XWOBA) < 1e-9, "missing prior -> neutral fill"
    mik = out[out["pitcher_id"] == 571945]["xwOBA_prior"].unique()
    assert len(mik) == 1 and not np.isclose(mik[0], NEUTRAL_XWOBA), "real prior attached"
    print(f"OK: Mikolas 2024 prior xwOBA={mik[0]:.3f} (from 2023), rookie fill={rookie:.3f}")


if __name__ == "__main__":
    demo()
