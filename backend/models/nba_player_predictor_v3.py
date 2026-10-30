"""Serve NBA player-prop projections from the clean v3 models (anchored:
projection = stat_L10 + model-predicted adjustment).

Availability features (TM_OUT_*) default to 0 ("assume full roster") so the
projection gracefully degrades to a recent-form estimate when no live inactives
feed is present; pass ``teammates_out`` usage totals to activate the availability
bump. Non-rotation players (MIN_L10 < 8) fall back to their L10 anchors.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Dict, Optional

import json

import joblib
import pandas as pd

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from config.paths import ARTIFACTS_DIR
from sports.nba.player_features import ROTATION_MIN_L10, TARGET_STATS, player_key

logger = logging.getLogger(__name__)
NBA_PLAYER_V3_DIR = ARTIFACTS_DIR / "nba_player_v3"


class NBAPlayerPredictorV3:
    def __init__(self, model_dir: Path = NBA_PLAYER_V3_DIR):
        self.model_dir = Path(model_dir)
        self._m = {}
        for t in TARGET_STATS:
            p = self.model_dir / f"player_{t}.joblib"
            if p.exists():
                self._m[t] = joblib.load(p)
        # "Ship only improvers": a stat whose model doesn't beat the L10 baseline
        # out-of-sample falls back to the anchor (recent-form average).
        self._beats: Dict[str, bool] = {}
        mp = self.model_dir / "nba_player_v3_metrics.json"
        if mp.exists():
            met = json.load(open(mp))
            self._beats = {t: (met.get(t, {}).get("skill_pct", 0) or 0) > 0 for t in TARGET_STATS}
        self._latest = None

    def available(self) -> bool:
        return len(self._m) > 0

    def _ensure(self):
        if self._latest is None:
            from sports.nba.player_features import build_player_frame, latest_player_features
            self._latest = latest_player_features(build_player_frame())
        return self._latest

    def predict_player(self, player_name: str, avail: Optional[Dict[str, float]] = None,
                       **kw) -> Optional[Dict[str, float]]:
        if not self.available():
            return None
        rec = self._ensure().get(player_key(player_name))
        if rec is None:
            return None
        feats = dict(rec["feats"])
        # availability: default full-roster (0); override if caller supplies tonight's out-list totals
        for c in ("TM_OUT_MIN", "TM_OUT_PTS", "TM_OUT_COUNT", "TM_TOP_OUT"):
            feats[c] = float((avail or {}).get(c, 0.0))
        X = pd.DataFrame([feats])
        out: Dict[str, float] = {}
        for t, blob in self._m.items():
            anchor = float(rec["anchors"].get(t, 0.0))
            # fall back to the L10 anchor for non-rotation players OR stats whose
            # model doesn't beat recent form out-of-sample (FTM/BLK).
            if rec.get("min_l10", 0.0) < ROTATION_MIN_L10 or not self._beats.get(t, True):
                out[t] = round(max(0.0, anchor), 1)
                continue
            adj = float(blob["model"].predict(X.reindex(columns=blob["feature_cols"]).fillna(0.0))[0])
            out[t] = round(max(0.0, anchor + adj), 1)
        # convenience: REB from OREB+DREB for content
        if "OREB" in out and "DREB" in out:
            out["REB"] = round(out["OREB"] + out["DREB"], 1)
        return out


_default: Optional[NBAPlayerPredictorV3] = None


def default_nba_player_predictor_v3() -> NBAPlayerPredictorV3:
    global _default
    if _default is None:
        _default = NBAPlayerPredictorV3()
    return _default
