"""Serve NBA team-market predictions: a predicted final score plus win / spread /
total probabilities, all derived from the trained margin & total normals.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

import joblib

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from config.paths import ARTIFACTS_DIR, KAGGLE_TEAM_GAMES_PARQUET
from predictions.schema import GamePrediction
from sports.nba.team_features import (_availability, _elo_timeline, _schedule_meta,
                                       _timeline, matchup_features)
from sports.nba.teams import canonical_team

logger = logging.getLogger(__name__)
TEAM_MODEL_DIR = ARTIFACTS_DIR / "team"


class TeamPredictor:
    def __init__(self, model_dir: Path = TEAM_MODEL_DIR, parquet_path: Path = KAGGLE_TEAM_GAMES_PARQUET):
        self.model_dir = Path(model_dir)
        self.parquet_path = Path(parquet_path)
        self._m = {}
        for t in ("margin", "total"):
            p = self.model_dir / f"team_{t}.joblib"
            if p.exists():
                self._m[t] = joblib.load(p)
        self._tl = None
        self._meta = None
        self._elo = None
        self._av = None

    def available(self) -> bool:
        return "margin" in self._m and "total" in self._m

    def _ctx(self):
        if self._tl is None:
            self._tl = _timeline(self.parquet_path)
        if self._meta is None:
            self._meta = _schedule_meta(self.parquet_path)
        if self._elo is None:
            self._elo = _elo_timeline(self.parquet_path)   # cached (a 20k-game sequential pass)
        if self._av is None:
            self._av = _availability()
        return self._tl, self._meta

    def predict_game(
        self, home: str, away: str, game_date: str, season: Optional[str] = None
    ) -> Optional[GamePrediction]:
        if not self.available():
            logger.warning("team models not found in %s", self.model_dir)
            return None
        home_c, away_c = canonical_team(home), canonical_team(away)

        tl, meta = self._ctx()
        X = matchup_features(home_c, away_c, game_date, timeline=tl, meta=meta,
                             availability=self._av, elo=self._elo)
        mm, mt = self._m["margin"], self._m["total"]
        mu_margin = float(mm["model"].predict(X[mm["feature_cols"]])[0])
        sig_margin = float(mm["sigma"])
        mu_total = float(mt["model"].predict(X[mt["feature_cols"]])[0])
        sig_total = float(mt["sigma"])

        home_pts = (mu_total + mu_margin) / 2.0
        away_pts = (mu_total - mu_margin) / 2.0

        # p_home_win = P(margin > 0); GamePrediction derives spread/total probs.
        from statistics import NormalDist

        p_home_win = 1.0 - NormalDist(mu_margin, sig_margin).cdf(0.0)

        return GamePrediction(
            sport="nba",
            game_date=str(game_date)[:10],
            home=home_c,
            away=away_c,
            mu_total=mu_total,
            sigma_total=sig_total,
            mu_margin=mu_margin,
            sigma_margin=sig_margin,
            pred_home_pts=round(home_pts, 1),
            pred_away_pts=round(away_pts, 1),
            p_home_win=p_home_win,
        )


_default: Optional[TeamPredictor] = None


def default_team_predictor() -> TeamPredictor:
    global _default
    if _default is None:
        _default = TeamPredictor()
    return _default
