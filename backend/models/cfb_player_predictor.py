"""Serve CFB player-prop projections (anchored): pass/rush/rec yards + receptions.

Mirrors the NFL player predictor: one anchored LightGBM per prop, projection =
anchor (the player's last-3 average) + the model's learned adjustment, usage-gated
at inference so a stat the player does not produce is not projected.
"""
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
from sports.cfb.player_features import PROP_TARGETS, USAGE_GATE
from utils.names import player_slug

logger = logging.getLogger(__name__)
CFB_PLAYER_MODEL_DIR = ARTIFACTS_DIR / "cfb_player"


class CFBPlayerPredictor:
    def __init__(self, model_dir: Path = CFB_PLAYER_MODEL_DIR, years: Optional[list] = None):
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
            from sports.cfb.player_features import build_player_frame, latest_player_features
            yrs = self._years or [int(season) - 1, int(season)]
            self._latest = latest_player_features(build_player_frame(yrs))
        return self._latest

    def predict_player(self, player_name: str, season: Optional[str] = None, **kw) -> Optional[Dict[str, float]]:
        if not self.available():
            return None
        latest = self._ensure(season or "2025")
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


_default: Optional[CFBPlayerPredictor] = None


def default_cfb_player_predictor() -> CFBPlayerPredictor:
    global _default
    if _default is None:
        _default = CFBPlayerPredictor()
    return _default
