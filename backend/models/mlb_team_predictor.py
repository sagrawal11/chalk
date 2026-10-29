"""Serve MLB team-market predictions (predicted run score + win/total probs)
from the trained margin & total normals, the MLB analog of nfl_team_predictor.

v1 is the team-strength model (~54% SU; MLB is low-signal without pitcher data).
The probable-pitcher signal is the planned accuracy enhancement."""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

import joblib

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from config.paths import ARTIFACTS_DIR
from predictions.schema import GamePrediction
from sports.mlb.teams import canonical_team

logger = logging.getLogger(__name__)
MLB_TEAM_MODEL_DIR = ARTIFACTS_DIR / "mlb_team"


class MLBTeamPredictor:
    def __init__(self, model_dir: Path = MLB_TEAM_MODEL_DIR, years: Optional[list] = None):
        self.model_dir = Path(model_dir)
        self._m = {}
        for t in ("margin", "total"):
            p = self.model_dir / f"team_{t}.joblib"
            if p.exists():
                self._m[t] = joblib.load(p)
        self._latest = None
        self._years = years

    def available(self) -> bool:
        return "margin" in self._m and "total" in self._m

    def _ensure_latest(self, season: str):
        if self._latest is None:
            from sports.mlb.team_features import build_timeline, latest_team_features
            yrs = self._years or [int(season) - 1, int(season)]
            self._latest = latest_team_features(build_timeline(yrs))
        return self._latest

    def predict_game(self, home: str, away: str, game_date: str, season: Optional[str] = None) -> Optional[GamePrediction]:
        if not self.available():
            logger.warning("MLB team models not found in %s", self.model_dir)
            return None
        from statistics import NormalDist

        home_c, away_c = canonical_team(home, strict=False), canonical_team(away, strict=False)
        season = season or str(int(str(game_date)[:4]))
        mm, mt = self._m["margin"], self._m["total"]
        sig_m, sig_t = float(mm["sigma"]), float(mt["sigma"])

        from sports.mlb.team_features import matchup_features
        latest = self._ensure_latest(season)
        X = matchup_features(home_c, away_c, latest)
        mu_m = float(mm["model"].predict(X[mm["feature_cols"]])[0])
        mu_t = float(mt["model"].predict(X[mt["feature_cols"]])[0])
        p_home_win = 1.0 - NormalDist(mu_m, sig_m).cdf(0.0)

        return GamePrediction(
            sport="mlb", game_date=str(game_date)[:10], home=home_c, away=away_c,
            mu_total=mu_t, sigma_total=sig_t, mu_margin=mu_m, sigma_margin=sig_m,
            pred_home_pts=round(max(0.0, (mu_t + mu_m) / 2.0), 1),
            pred_away_pts=round(max(0.0, (mu_t - mu_m) / 2.0), 1),
            p_home_win=p_home_win,
        )


_default: Optional[MLBTeamPredictor] = None


def default_mlb_team_predictor() -> MLBTeamPredictor:
    global _default
    if _default is None:
        _default = MLBTeamPredictor()
    return _default
