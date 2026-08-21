"""Serve NFL team-market predictions (predicted score + win/spread/total probs)
from the trained margin & total normals — the NFL analog of models.team_predictor."""
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
from sports.nfl.teams import canonical_team

logger = logging.getLogger(__name__)
NFL_TEAM_MODEL_DIR = ARTIFACTS_DIR / "nfl_team"
NFL_TEAM_BLIND_DIR = ARTIFACTS_DIR / "nfl_team_blind"  # market-blind (absolute-target) model


class NFLTeamPredictor:
    def __init__(self, model_dir: Path = NFL_TEAM_MODEL_DIR, years: Optional[list] = None,
                 blind_dir: Path = NFL_TEAM_BLIND_DIR):
        self.model_dir = Path(model_dir)
        self._m = {}
        for t in ("margin", "total"):
            p = self.model_dir / f"team_{t}.joblib"
            if p.exists():
                self._m[t] = joblib.load(p)
        self.blind_dir = Path(blind_dir)
        self._m_blind = {}
        for t in ("margin", "total"):
            p = self.blind_dir / f"team_{t}.joblib"
            if p.exists():
                self._m_blind[t] = joblib.load(p)
        self._latest = None
        self._years = years

    def _residual_available(self) -> bool:
        return "margin" in self._m and "total" in self._m

    def _blind_available(self) -> bool:
        return "margin" in self._m_blind and "total" in self._m_blind

    def available(self) -> bool:
        return self._residual_available() or self._blind_available()

    def _ensure_latest(self, season: str):
        if self._latest is None:
            from sports.nfl.team_features import build_timeline, latest_team_features
            yrs = self._years or [int(season) - 1, int(season)]
            self._latest = latest_team_features(build_timeline(yrs))
        return self._latest

    def _game_context(self, home: str, away: str, season: str) -> dict:
        """Real market line + weather for this matchup from the nflverse schedule
        (the anchor); {} (neutral fills) if the game/line isn't posted yet."""
        from sports.nfl.data import game_context, load_schedules
        try:
            s = load_schedules([int(season)])
        except Exception:
            return {}
        row = s[(s["home"] == home) & (s["away"] == away)]
        if row.empty:
            return {}
        c = game_context([int(season)])
        c = c[c["game_id"] == row.iloc[0]["game_id"]]
        if c.empty:
            return {}
        r = c.iloc[0]
        return {k: float(r[k]) for k in ("MARKET_SPREAD", "MARKET_TOTAL", "IS_DOME", "WIND", "TEMP", "DIV_GAME")}

    def predict_game(self, home: str, away: str, game_date: str, season: Optional[str] = None) -> Optional[GamePrediction]:
        from statistics import NormalDist

        from sports.nfl.team_features import MARGIN_ANCHOR, TOTAL_ANCHOR, matchup_features

        blind = market_blind()
        use_blind = blind and self._blind_available()
        if use_blind:
            models = self._m_blind
        elif self._residual_available():
            models = self._m
            if blind:
                logger.warning(
                    "MARKET_BLIND is set but models/artifacts/nfl_team_blind/ is missing — "
                    "falling back to the MARKET-ANCHORED NFL model (this leaks the line). "
                    "Train it: python model_training/train_nfl_team_model.py --blind")
        else:
            logger.warning("NFL team models not found in %s", self.model_dir)
            return None

        home_c, away_c = canonical_team(home), canonical_team(away)
        season = season or str(int(str(game_date)[:4]))
        latest = self._ensure_latest(season)
        # Blind mode never fetches the market line (no anchor needed).
        ctx = {} if use_blind else self._game_context(home_c, away_c, season)
        X = matchup_features(home_c, away_c, latest, context=ctx)

        mm, mt = models["margin"], models["total"]
        sig_m, sig_t = float(mm["sigma"]), float(mt["sigma"])
        if use_blind:
            # Absolute margin/total straight from team features — no market anchor.
            mu_m = float(mm["model"].predict(X[mm["feature_cols"]])[0])
            mu_t = float(mt["model"].predict(X[mt["feature_cols"]])[0])
        else:
            # Market line (accuracy ceiling) + learned residual.
            mu_m = ctx.get(MARGIN_ANCHOR, 0.0) + float(mm["model"].predict(X[mm["feature_cols"]])[0])
            mu_t = ctx.get(TOTAL_ANCHOR, 44.0) + float(mt["model"].predict(X[mt["feature_cols"]])[0])
        p_home_win = 1.0 - NormalDist(mu_m, sig_m).cdf(0.0)

        return GamePrediction(
            sport="nfl", game_date=str(game_date)[:10], home=home_c, away=away_c,
            mu_total=mu_t, sigma_total=sig_t, mu_margin=mu_m, sigma_margin=sig_m,
            pred_home_pts=round((mu_t + mu_m) / 2.0, 1), pred_away_pts=round((mu_t - mu_m) / 2.0, 1),
            p_home_win=p_home_win,
        )


_default: Optional[NFLTeamPredictor] = None


def default_nfl_team_predictor() -> NFLTeamPredictor:
    global _default
    if _default is None:
        _default = NFLTeamPredictor()
    return _default
