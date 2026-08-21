"""Serve MLB starting-pitcher strikeout projections (anchored: K_L5 + model
adjustment). Keyed by StatsAPI pitcher id; name resolution via StatsAPI."""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Dict, Optional

import joblib
import pandas as pd

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from config.paths import ARTIFACTS_DIR
from sports.mlb.pitcher_features import MIN_PRIOR_STARTS

logger = logging.getLogger(__name__)
MLB_PITCHER_DIR = ARTIFACTS_DIR / "mlb_pitcher"


class MLBPitcherPredictor:
    def __init__(self, model_dir: Path = MLB_PITCHER_DIR, years: Optional[list] = None):
        self.model_dir = Path(model_dir)
        p = self.model_dir / "pitcher_K.joblib"
        self._blob = joblib.load(p) if p.exists() else None
        self._latest = None
        self._years = years
        self._names: Dict[int, str] = {}

    def available(self) -> bool:
        return self._blob is not None

    def _ensure(self, season: str):
        if self._latest is None:
            from sports.mlb.pitcher_features import build_pitcher_frame, latest_pitcher_features
            yrs = self._years or [int(season) - 1, int(season)]
            self._latest = latest_pitcher_features(build_pitcher_frame(yrs))
        return self._latest

    def pitcher_name(self, pitcher_id: int) -> str:
        pid = int(pitcher_id)
        if pid not in self._names:
            try:
                import requests
                r = requests.get(f"https://statsapi.mlb.com/api/v1/people/{pid}", timeout=15)
                self._names[pid] = r.json()["people"][0].get("fullName", str(pid))
            except Exception:
                self._names[pid] = str(pid)
        return self._names[pid]

    def predict(self, pitcher_id: int, season: Optional[str] = None) -> Optional[float]:
        if not self.available():
            return None
        rec = self._ensure(season or "2025").get(int(pitcher_id))
        if rec is None:
            return None
        anchor = float(rec["anchor"])
        if rec.get("n_prior", 0) < MIN_PRIOR_STARTS:
            return round(max(0.0, anchor), 1)   # too little history -> recent-average fallback
        X = pd.DataFrame([rec["feats"]]).reindex(columns=self._blob["feature_cols"]).fillna(0.0)
        adj = float(self._blob["model"].predict(X)[0])
        return round(max(0.0, anchor + adj), 1)

    def slate_projections(self, games, season: Optional[str] = None, limit: int = 6) -> list:
        """Strikeout prop cards for the day's probable starters — the natural MLB
        marquee prop. Reads the date's probable pitchers from the schedule
        (home_sp/away_sp), projects each, and returns the top ``limit`` by
        projected Ks as render-ready dicts (player_name, projections, matchup,
        sport). Empty if the model is untrained or no probables are posted yet."""
        if not self.available() or not games:
            return []
        from sports.mlb.data import load_schedules

        seas = season or "2025"
        dates = {str(g.get("date") or g.get("game_date"))[:10] for g in games}
        sched = load_schedules([int(seas)])
        if sched.empty:
            return []
        sched = sched[sched["game_date"].astype(str).str[:10].isin(dates)]
        cards = []
        for _, r in sched.iterrows():
            matchup = {"home_sp": f"vs {r['away']}", "away_sp": f"@ {r['home']}"}
            for col, mt in matchup.items():
                pid = r.get(col)
                if pid is None or pd.isna(pid):
                    continue
                k = self.predict(int(pid), season=seas)
                if k is None:
                    continue
                cards.append(({"player_name": self.pitcher_name(int(pid)),
                               "projections": {"strikeouts": k}, "matchup": mt,
                               "sport": "mlb"}, k))
        cards.sort(key=lambda x: x[1], reverse=True)
        return [c for c, _ in cards[:limit]]


_default: Optional[MLBPitcherPredictor] = None


def default_mlb_pitcher_predictor() -> MLBPitcherPredictor:
    global _default
    if _default is None:
        _default = MLBPitcherPredictor()
    return _default
