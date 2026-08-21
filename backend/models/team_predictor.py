"""Serve team-market predictions: a predicted final score plus win / spread /
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
from config.settings import market_blind
from predictions.schema import GamePrediction
from sports.nba.team_features import (_availability, _elo_timeline, _schedule_meta,
                                       _timeline, matchup_features)
from sports.nba.teams import canonical_team

logger = logging.getLogger(__name__)
TEAM_MODEL_DIR = ARTIFACTS_DIR / "team"
# Historical market lines (Kaggle backfill, 2007->Jan-2023) + a hook for a live
# provider (upcoming season). When a game's closing line is known it's the most
# accurate predictor (68% SU vs 66% for our model), so we anchor on it and fall
# back to the team model only when no line is available.
NBA_ODDS_BACKFILL = BACKEND / "data" / "odds" / "nba_kaggle_backfill.csv"
NBA_SIG_MARGIN, NBA_SIG_TOTAL = 12.0, 17.0  # empirical NBA line residual sigmas (Hal Stern ~12 margin)


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
        self._lines = None
        # LIVE odds for the upcoming season: auto-enabled when ODDS_API_KEY is set
        # (get a free key at the-odds-api.com). callable(home,away,date)->(spread_home_fav,total)|None.
        self.market_provider = None
        try:
            from sports.nba.live_odds import _get_key, market_provider
            if _get_key():  # env or repo .env
                self.market_provider = market_provider()
                logger.info("NBA live odds enabled (The Odds API)")
        except Exception as e:
            logger.warning("live odds unavailable: %s", e)

    def available(self) -> bool:
        return "margin" in self._m and "total" in self._m

    def _line_for(self, home: str, away: str, game_date: str):
        """Closing line for this matchup as (home-favored spread, total), or None.
        Live provider (upcoming season) wins; else the historical backfill."""
        d = str(game_date)[:10]
        if self.market_provider is not None:
            try:
                live = self.market_provider(home, away, d)
                if live is not None:
                    return float(live[0]), float(live[1])
            except Exception as e:  # live odds are best-effort
                logger.debug("live market provider failed: %s", e)
        if self._lines is None:
            self._lines = {}
            if NBA_ODDS_BACKFILL.exists():
                import pandas as pd
                o = pd.read_csv(NBA_ODDS_BACKFILL)
                for r in o.itertuples():
                    # backfill 'spread_home' is points-added-to-home; flip to home-favored-positive
                    self._lines[(str(r.game_date)[:10], r.home, r.away)] = (-float(r.spread_home), float(r.total))
        return self._lines.get((d, home, away))

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

        # Market-blind (brand default): ignore the line and use our pure team model
        # (avail + Elo + ratings, ~66% SU). Only when MARKET_BLIND is off do we
        # anchor on the closing line (~68% SU ceiling), for ROI settlement.
        line = None if market_blind() else self._line_for(home_c, away_c, game_date)
        if line is not None:
            mu_margin, mu_total = line[0], line[1]
            sig_margin, sig_total = NBA_SIG_MARGIN, NBA_SIG_TOTAL
        else:
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
