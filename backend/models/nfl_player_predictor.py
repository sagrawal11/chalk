"""Serve NFL player-prop projections (anchored): pass/rush/rec yards + receptions."""
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
from sports.nfl.player_features import PROP_TARGETS, USAGE_GATE
from utils.names import player_slug

logger = logging.getLogger(__name__)
NFL_PLAYER_MODEL_DIR = ARTIFACTS_DIR / "nfl_player"


class NFLPlayerPredictor:
    def __init__(self, model_dir: Path = NFL_PLAYER_MODEL_DIR, years: Optional[list] = None):
        self.model_dir = Path(model_dir)
        self._m = {}
        for t in PROP_TARGETS:
            p = self.model_dir / f"player_{t}.joblib"
            if p.exists():
                self._m[t] = joblib.load(p)
        self._latest = None
        self._years = years

    def available(self) -> bool:
        return len(self._m) > 0

    def _ensure(self, season: str):
        if self._latest is None:
            from sports.nfl.player_features import build_player_frame, latest_player_features
            yrs = self._years or [int(season) - 1, int(season)]
            self._latest = latest_player_features(build_player_frame(yrs))
        return self._latest

    def predict_player(self, player_name: str, season: Optional[str] = None, **kw) -> Optional[Dict[str, float]]:
        if not self.available():
            return None
        latest = self._ensure(season or "2024")
        rec = latest.get(player_slug(player_name))
        if rec is None:
            return None
        X = pd.DataFrame([rec["feats"]])
        out: Dict[str, float] = {}
        for t, blob in self._m.items():
            # Usage gate at inference too: don't project a stat the player doesn't
            # produce (else a WR's zero-attempts vector extrapolates phantom pass yds).
            gate_col, gate_val = USAGE_GATE[t]
            if float(rec["feats"].get(gate_col, 0.0)) < gate_val:
                continue
            adj = float(blob["model"].predict(X.reindex(columns=blob["feature_cols"]).fillna(0.0))[0])
            out[t] = round(max(0.0, rec["anchors"].get(t, 0.0) + adj), 1)  # anchor + adjustment
        return out


    def slate_projections(self, games, season: Optional[str] = None, limit: int = 6) -> list:
        """Prop cards for the slate's marquee skill players: project every player
        on a slate team, rank by primary yardage, return the top ``limit`` as
        render-ready dicts (player_name, projections, matchup, sport)."""
        if not self.available() or not games:
            return []
        self._ensure(season or "2024")
        matchup = {}
        for g in games:
            matchup[g["home"]] = f"vs {g['away']}"
            matchup[g["away"]] = f"@ {g['home']}"
        # primary stat to rank by, per position
        prim = {"QB": lambda p: p.get("passing_yards", 0.0),
                "RB": lambda p: p.get("rushing_yards", 0.0) + p.get("receiving_yards", 0.0),
                "WR": lambda p: p.get("receiving_yards", 0.0),
                "TE": lambda p: p.get("receiving_yards", 0.0)}
        buckets: dict = {}
        for rec in (self._latest or {}).values():
            if rec.get("team") not in matchup:
                continue
            pos = rec.get("position", "")
            if pos not in prim:
                continue
            proj = self.predict_player(rec["name"], season=season)
            if not proj:
                continue
            buckets.setdefault(pos, []).append(
                ({"player_name": rec["name"], "projections": proj,
                  "matchup": matchup[rec["team"]], "sport": "nfl"}, prim[pos](proj)))
        # diversify: top-2 QB/RB/WR + top TE, ranked within position, then capped
        out = []
        for pos, n in (("QB", 2), ("RB", 2), ("WR", 2), ("TE", 1)):
            top = sorted(buckets.get(pos, []), key=lambda x: x[1], reverse=True)[:n]
            out += [c for c, _ in top]
        return out[:limit]


_default: Optional[NFLPlayerPredictor] = None


def default_nfl_player_predictor() -> NFLPlayerPredictor:
    global _default
    if _default is None:
        _default = NFLPlayerPredictor()
    return _default
