"""Serve MLB batter hitting-prop projections (anchored: <stat>_L5 + model
adjustment) for hits / total bases / home runs. Keyed by StatsAPI batter id;
name resolution via StatsAPI."""
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
from sports.mlb.batter_features import MIN_PRIOR_GAMES, PROP_TARGETS

logger = logging.getLogger(__name__)
MLB_BATTER_DIR = ARTIFACTS_DIR / "mlb_batter"


class MLBBatterPredictor:
    def __init__(self, model_dir: Path = MLB_BATTER_DIR, years: Optional[list] = None):
        self.model_dir = Path(model_dir)
        self._m: Dict[str, dict] = {}
        for t in PROP_TARGETS:
            p = self.model_dir / f"batter_{t}.joblib"
            if p.exists():
                self._m[t] = joblib.load(p)
        self._latest = None
        self._years = years
        self._names: Dict[int, str] = {}

    def available(self) -> bool:
        return len(self._m) > 0

    def _ensure(self, season: str):
        if self._latest is None:
            from sports.mlb.batter_features import build_batter_frame, latest_batter_features
            yrs = self._years or [int(season) - 1, int(season)]
            self._latest = latest_batter_features(build_batter_frame(yrs))
        return self._latest

    def batter_name(self, batter_id: int) -> str:
        bid = int(batter_id)
        if bid not in self._names:
            try:
                import requests
                r = requests.get(f"https://statsapi.mlb.com/api/v1/people/{bid}", timeout=15)
                self._names[bid] = r.json()["people"][0].get("fullName", str(bid))
            except Exception:
                self._names[bid] = str(bid)
        return self._names[bid]

    def predict(self, batter_id: int, season: Optional[str] = None) -> Optional[Dict[str, float]]:
        """Anchored per-prop projection dict {hits, totalBases, homeRuns}. With too
        little history, falls back to the batter's recent average per prop."""
        if not self.available():
            return None
        rec = self._ensure(season or "2024").get(int(batter_id))
        if rec is None:
            return None
        anchors = rec["anchors"]
        if rec.get("n_prior", 0) < MIN_PRIOR_GAMES:
            return {t: round(max(0.0, float(anchors.get(t, 0.0))), 2) for t in self._m}
        X = pd.DataFrame([rec["feats"]])
        out: Dict[str, float] = {}
        for t, blob in self._m.items():
            adj = float(blob["model"].predict(X.reindex(columns=blob["feature_cols"]).fillna(0.0))[0])
            out[t] = round(max(0.0, float(anchors.get(t, 0.0)) + adj), 2)
        return out

    def slate_projections(self, games, season: Optional[str] = None, limit: int = 4) -> list:
        """Prop cards for the slate's regular hitters: project every batter whose
        (roster) team is playing today, rank by projected total bases, return the
        top ``limit`` as render-ready dicts (player_name, projections, matchup, sport).
        Batters carry their team from the roster fetch (batter_data._hitters)."""
        if not self.available() or not games:
            return []
        self._ensure(season or "2024")
        matchup: Dict[str, str] = {}
        for g in games:
            matchup[g["home"]] = f"vs {g['away']}"
            matchup[g["away"]] = f"@ {g['home']}"
        scored = []
        for bid, rec in (self._latest or {}).items():
            if rec.get("team") not in matchup:
                continue
            proj = self.predict(bid, season=season)
            if not proj:
                continue
            rank = proj.get("totalBases", proj.get("hits", 0.0))
            scored.append(({"player_name": rec.get("name") or self.batter_name(bid),
                            "projections": proj, "matchup": matchup[rec["team"]],
                            "sport": "mlb"}, rank))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [c for c, _ in scored[:limit]]


_default: Optional[MLBBatterPredictor] = None


def default_mlb_batter_predictor() -> MLBBatterPredictor:
    global _default
    if _default is None:
        _default = MLBBatterPredictor()
    return _default
