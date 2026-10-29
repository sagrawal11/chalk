"""Serve soccer (EPL/UCL/MLS) 3-way predictions from a standalone Poisson
(Dixon-Coles-lite) TEAM model built from football-data.co.uk EPL results
(attack/defense strength -> Poisson scoreline probs). League base rates remain the
final fallback when the Poisson model has no data for a team.
"""
from __future__ import annotations

import logging
from typing import Dict, Optional

from predictions.schema import GamePrediction
from sports.soccer.teams import canonical_team

logger = logging.getLogger(__name__)
# League base rates (home edge): the final fallback when the Poisson team model has
# no data for a matchup.
_BASE = {"p_home": 0.45, "p_draw": 0.27, "p_away": 0.28, "total": 2.7}


class SoccerPredictor:
    def __init__(self):
        # Poisson team-model ratings are built lazily on the first matchup so
        # instantiation stays cheap and network fetches happen only when needed.
        self._poisson_ratings: Optional[Dict[str, Dict[str, float]]] = None
        self._poisson_tried = False

    def available(self) -> bool:
        return True  # always predicts (base rates when the Poisson model has no data)

    def _poisson_line(self, home_c: str, away_c: str) -> Optional[Dict]:
        """3-way + total from the Poisson team model, or None if it has no data
        for either club. Ratings are fetched/cached once per predictor instance."""
        if not self._poisson_tried:
            self._poisson_tried = True
            try:
                from sports.soccer.team_features import build_epl_matches, latest_team_ratings
                self._poisson_ratings = latest_team_ratings(build_epl_matches())
                logger.info("Soccer Poisson team model ready (%d teams)",
                            len(self._poisson_ratings or {}))
            except Exception as e:
                logger.warning("Soccer Poisson team model unavailable: %s", e)
                self._poisson_ratings = None
        if not self._poisson_ratings:
            return None
        try:
            from sports.soccer.team_features import predict_3way
            la = self._poisson_ratings.get(home_c, {}).get("league_avg")
            probs = predict_3way(home_c, away_c, self._poisson_ratings,
                                 league_avg=la) if la else predict_3way(home_c, away_c, self._poisson_ratings)
        except Exception as e:
            logger.warning("Soccer Poisson predict failed for %s vs %s: %s", home_c, away_c, e)
            return None
        return probs

    def predict_game(self, home: str, away: str, game_date: str, season: Optional[str] = None) -> GamePrediction:
        home_c, away_c = canonical_team(home, strict=False), canonical_team(away, strict=False)
        line = self._poisson_line(home_c, away_c)  # Poisson team model; base rates fallback
        L = line or _BASE
        p_home, p_draw, p_away = float(L["p_home"]), float(L["p_draw"]), float(L["p_away"])
        total = float(L.get("total", 2.7))

        # nominal expected-goal split from the total + which side is favored
        # (soccer margins are small; scale the win-prob edge modestly).
        mu_margin = max(-2.5, min(2.5, (p_home - p_away) * 2.0))
        return GamePrediction(
            sport="soccer", game_date=str(game_date)[:10], home=home_c, away=away_c,
            mu_total=total, sigma_total=1.4, mu_margin=mu_margin, sigma_margin=1.3,
            pred_home_pts=round(max(0.0, (total + mu_margin) / 2.0), 1),
            pred_away_pts=round(max(0.0, (total - mu_margin) / 2.0), 1),
            p_home_win=p_home, p_draw=p_draw, p_away_win=p_away,
        )


_default: Optional[SoccerPredictor] = None


def default_soccer_predictor() -> SoccerPredictor:
    global _default
    if _default is None:
        _default = SoccerPredictor()
    return _default
