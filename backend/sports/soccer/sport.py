"""Soccer sport plugin (EPL / UCL / MLS) implementing the shared ``Sport``
interface. 3-way outcome (home/draw/away) from a Poisson team model."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sports.base import Sport
from sports.soccer import teams

logger = logging.getLogger(__name__)


class SoccerSport(Sport):
    key = "soccer"
    display_name = "Soccer"
    capabilities = frozenset({"schedule", "predict_game"})

    def __init__(self) -> None:
        self._predictor: Any = None

    def canonical_team(self, code: str, *, strict: bool = True) -> str:
        return teams.canonical_team(code, strict=strict)

    def current_season(self) -> str:
        now = datetime.now()
        return str(now.year if now.month >= 7 else now.year - 1)

    def season_from_date(self, game_date: str) -> str:
        return teams.season_from_date(game_date)

    def player_targets(self) -> List[str]:
        return []  # player props (goals/assists/shots) not built yet

    def team_targets(self) -> List[str]:
        return ["home_win", "draw", "away_win", "total"]

    def score_ranges(self) -> Dict[str, Any]:
        return {"team_pts": (0.0, 8.0), "total": (0.0, 10.0), "margin": (-8.0, 8.0)}

    def predict_game(self, home: str, away: str, game_date: str, season: Optional[str] = None) -> Any:
        try:
            from models.soccer_predictor import default_soccer_predictor
        except ImportError:
            return None
        if self._predictor is None:
            self._predictor = default_soccer_predictor()
        return self._predictor.predict_game(
            home=self.canonical_team(home, strict=False), away=self.canonical_team(away, strict=False),
            game_date=game_date, season=season or self.season_from_date(game_date),
        )

    def schedule(self, game_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """No free soccer fixtures source is wired yet (the prior source was the betting
        odds API, now removed). Returns an empty slate until a free schedule feed is added."""
        return []
