"""Serve NHL skater points/shots projections (anchored: stat_L5 + model
adjustment). Keyed by NHL API player id; name resolution via the NHL API."""
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
from sports.nhl.skater_features import MIN_PRIOR_GAMES, PROP_TARGETS

logger = logging.getLogger(__name__)
NHL_SKATER_DIR = ARTIFACTS_DIR / "nhl_skater"


class NHLSkaterPredictor:
    def __init__(self, model_dir: Path = NHL_SKATER_DIR, years: Optional[list] = None):
        self.model_dir = Path(model_dir)
        self._blobs: Dict[str, dict] = {}
        for target in PROP_TARGETS:
            p = self.model_dir / f"skater_{target}.joblib"
            if p.exists():
                self._blobs[target] = joblib.load(p)
        self._latest = None
        self._years = years
        self._names: Dict[int, str] = {}

    def available(self) -> bool:
        return bool(self._blobs)

    def _ensure(self, season: str):
        if self._latest is None:
            from sports.nhl.skater_features import build_skater_frame, latest_skater_features
            yrs = self._years or [int(season) - 1, int(season)]
            self._latest = latest_skater_features(build_skater_frame(yrs))
        return self._latest

    def skater_name(self, player_id: int) -> str:
        pid = int(player_id)
        if pid not in self._names:
            try:
                import requests
                r = requests.get(f"https://api-web.nhle.com/v1/player/{pid}/landing", timeout=15)
                d = r.json()
                self._names[pid] = (d.get("firstName", {}).get("default", "")
                                    + " " + d.get("lastName", {}).get("default", "")).strip() or str(pid)
            except Exception:
                self._names[pid] = str(pid)
        return self._names[pid]

    def _predict_one(self, target: str, rec: dict) -> Optional[float]:
        blob = self._blobs.get(target)
        if blob is None or rec is None:
            return None
        anchor = float(rec["anchors"].get(target, 0.0))
        if rec.get("n_prior", 0) < MIN_PRIOR_GAMES:
            return round(max(0.0, anchor), 2)   # too little history -> recent-average fallback
        X = pd.DataFrame([rec["feats"]]).reindex(columns=blob["feature_cols"]).fillna(0.0)
        adj = float(blob["model"].predict(X)[0])
        return round(max(0.0, anchor + adj), 2)

    def predict(self, player_id: int, season: Optional[str] = None) -> Optional[Dict[str, float]]:
        """Project every served prop for a skater. Returns {target: value} or None."""
        if not self.available():
            return None
        rec = self._ensure(season or "2024").get(int(player_id))
        if rec is None:
            return None
        out = {t: self._predict_one(t, rec) for t in PROP_TARGETS if t in self._blobs}
        return {t: v for t, v in out.items() if v is not None} or None

    def slate_projections(self, games, season: Optional[str] = None, limit: int = 4) -> list:
        """Prop cards for the slate's marquee skaters: project every skater whose
        (roster) team is playing today, rank by projected points, return the top
        ``limit`` as render-ready dicts (player_name, projections, matchup, sport).
        Skaters carry their team from the roster fetch (skater_data._skaters)."""
        if not self.available() or not games:
            return []
        self._ensure(season or "2024")
        matchup: Dict[str, str] = {}
        for g in games:
            matchup[g["home"]] = f"vs {g['away']}"
            matchup[g["away"]] = f"@ {g['home']}"
        scored = []
        for pid, rec in (self._latest or {}).items():
            if rec.get("team") not in matchup:
                continue
            proj = self.predict(pid, season=season)
            if not proj:
                continue
            scored.append(({"player_name": rec.get("name") or self.skater_name(pid),
                            "projections": proj, "matchup": matchup[rec["team"]],
                            "sport": "nhl"}, proj.get("points", 0.0)))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [c for c, _ in scored[:limit]]


_default: Optional[NHLSkaterPredictor] = None


def default_nhl_skater_predictor() -> NHLSkaterPredictor:
    global _default
    if _default is None:
        _default = NHLSkaterPredictor()
    return _default
