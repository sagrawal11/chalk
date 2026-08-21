"""Starting-pitcher game logs from the free MLB StatsAPI (no key) for the
strikeout-prop model.

Enumerates starting pitchers from the schedule (home_sp/away_sp ids we already
store), fetches each pitcher's per-game pitching log, and keeps their STARTS
(strikeouts, IP, batters faced, opponent). Cached per season to
``data/mlb/pitcher_starts_{year}.parquet``.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List, Sequence

import pandas as pd

_STATS = "https://statsapi.mlb.com/api/v1/people/{pid}/stats"
_CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "mlb"
# ER + IP kept per start so the team model can derive a rolling starter ERA
# (earned_runs*9/IP over prior starts) — a sharper pitcher signal than the
# coarse team-runs-allowed SP_RA proxy.
_COLS = ["pitcher_id", "season", "date", "K", "IP", "ER", "BF", "opp", "is_home"]


def _ip_to_float(ip) -> float:
    # "6.2" = 6 and 2/3 innings -> 6.667
    try:
        s = str(ip)
        whole, _, frac = s.partition(".")
        return float(whole) + (float(frac) / 3.0 if frac else 0.0)
    except Exception:
        return 0.0


def _sp_ids(year: int, min_starts: int = 5) -> List[int]:
    """Starting pitchers who appear >= min_starts times in the season's schedule
    (regulars — skips one-off spot starters/openers to bound the fetch)."""
    from sports.mlb.data import load_schedules
    s = load_schedules([year])
    if s.empty:
        return []
    ids = pd.concat([s.get("home_sp"), s.get("away_sp")]).dropna().astype(int)
    counts = ids.value_counts()
    return sorted(counts[counts >= min_starts].index.tolist())


def _fetch_pitcher(pid: int, season: int) -> List[dict]:
    import requests
    try:
        r = requests.get(_STATS.format(pid=pid),
                         params={"stats": "gameLog", "group": "pitching", "season": season}, timeout=20)
        stats = r.json().get("stats", [])
        splits = stats[0]["splits"] if stats else []
    except Exception:
        return []
    rows = []
    for sp in splits:
        st = sp.get("stat", {})
        if int(st.get("gamesStarted", 0) or 0) != 1:      # starts only
            continue
        rows.append({
            "pitcher_id": pid, "season": season, "date": sp.get("date"),
            "K": float(st.get("strikeOuts", 0) or 0), "IP": _ip_to_float(st.get("inningsPitched", 0)),
            "ER": float(st.get("earnedRuns", 0) or 0),
            "BF": float(st.get("battersFaced", 0) or 0),
            "opp": (sp.get("opponent", {}) or {}).get("abbreviation") or "",
            "is_home": 1 if sp.get("isHome") else 0,
        })
    return rows


def build_pitcher_starts(years: Sequence[int]) -> pd.DataFrame:
    cur = datetime.now().year
    frames = []
    for y in years:
        cache = _CACHE_DIR / f"pitcher_starts_{y}.parquet"
        if y < cur and cache.exists():
            frames.append(pd.read_parquet(cache))
            continue
        rows: List[dict] = []
        for pid in _sp_ids(int(y)):
            rows.extend(_fetch_pitcher(pid, int(y)))
        df = pd.DataFrame(rows, columns=_COLS)
        if y < cur and not df.empty:
            _CACHE_DIR.mkdir(parents=True, exist_ok=True)
            df.to_parquet(cache, index=False)
        frames.append(df)
    out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=_COLS)
    if not out.empty:
        out["date"] = pd.to_datetime(out["date"], errors="coerce")
    return out
