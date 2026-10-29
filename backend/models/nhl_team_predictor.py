"""Serve NHL team-market predictions (predicted goal score + win/total probs).
Team goal model + a live market anchor (The Odds API moneyline->win prob, market
total), the same pattern as MLB (fixed puck line, so the moneyline is the margin
signal). Auto-enabled when ODDS_API_KEY is set."""
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
from config.settings import market_blind
from predictions.schema import GamePrediction
from sports.nhl.teams import canonical_team

logger = logging.getLogger(__name__)
NHL_TEAM_MODEL_DIR = ARTIFACTS_DIR / "nhl_team"
_MARGIN_CAP = 2.5  # NHL margins are small even for heavy favorites


class NHLTeamPredictor:
    def __init__(self, model_dir: Path = NHL_TEAM_MODEL_DIR, years: Optional[list] = None):
        self.model_dir = Path(model_dir)
        self._m = {}
        for t in ("margin", "total"):
            p = self.model_dir / f"team_{t}.joblib"
            if p.exists():
                self._m[t] = joblib.load(p)
        self._latest = None
        self._years = years
        self.market_provider = None
        try:
            from sports.nba.live_odds import _get_key
            if _get_key():
                from sports.nhl.live_odds import market_provider
                self.market_provider = market_provider()
                logger.info("NHL live odds enabled (The Odds API)")
        except Exception as e:
            logger.warning("NHL live odds unavailable: %s", e)

    def available(self) -> bool:
        return "margin" in self._m and "total" in self._m

    def _ensure_latest(self, season: str):
        if self._latest is None:
            from sports.nhl.team_features import build_timeline, latest_team_features
            yrs = self._years or [int(season) - 1, int(season)]
            self._latest = latest_team_features(build_timeline(yrs))
        return self._latest

    def predict_game(self, home: str, away: str, game_date: str, season: Optional[str] = None) -> Optional[GamePrediction]:
        if not self.available():
            logger.warning("NHL team models not found in %s", self.model_dir)
            return None
        from statistics import NormalDist

        home_c, away_c = canonical_team(home, strict=False), canonical_team(away, strict=False)
        season = season or str(int(str(game_date)[:4]))
        mm, mt = self._m["margin"], self._m["total"]
        sig_m, sig_t = float(mm["sigma"]), float(mt["sigma"])

        # Market-blind (brand default): skip the line and use the pure team model.
        line = None if market_blind() else (
            self.market_provider(home_c, away_c, str(game_date)[:10]) if self.market_provider else None
        )
        if line is not None:
            p_home_win = min(max(float(line["p_home_win"]), 0.02), 0.98)
            mu_t = float(line["total"])
            mu_m = max(-_MARGIN_CAP, min(_MARGIN_CAP, NormalDist(0.0, 1.0).inv_cdf(p_home_win) * sig_m))
        else:
            from sports.nhl.team_features import matchup_features
            latest = self._ensure_latest(season)
            X = matchup_features(home_c, away_c, latest)
            mu_m = float(mm["model"].predict(X[mm["feature_cols"]])[0])
            mu_t = float(mt["model"].predict(X[mt["feature_cols"]])[0])
            p_home_win = 1.0 - NormalDist(mu_m, sig_m).cdf(0.0)

        return GamePrediction(
            sport="nhl", game_date=str(game_date)[:10], home=home_c, away=away_c,
            mu_total=mu_t, sigma_total=sig_t, mu_margin=mu_m, sigma_margin=sig_m,
            pred_home_pts=round(max(0.0, (mu_t + mu_m) / 2.0), 1),
            pred_away_pts=round(max(0.0, (mu_t - mu_m) / 2.0), 1),
            p_home_win=p_home_win,
        )


_default: Optional[NHLTeamPredictor] = None


def default_nhl_team_predictor() -> NHLTeamPredictor:
    global _default
    if _default is None:
        _default = NHLTeamPredictor()
    return _default
