"""CFB sport plugin implementing the shared ``Sport`` interface. Team margin/total
model over CFBD FBS games; anchored player-prop models (pass/rush/rec yards +
receptions) over CFBD box scores."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sports.base import Sport
from sports.cfb import teams

logger = logging.getLogger(__name__)


class CFBSport(Sport):
    key = "cfb"
    display_name = "College Football"
    capabilities = frozenset({"predict_game", "predict_player"})

    def __init__(self) -> None:
        self._team_predictor: Any = None
        self._player_predictor: Any = None

    def canonical_team(self, code: str, *, strict: bool = True) -> str:
        return teams.canonical_team(code, strict=strict)

    def current_season(self) -> str:
        return teams.current_season()

    def season_from_date(self, game_date: str) -> str:
        return teams.season_from_date(game_date)

    def player_targets(self) -> List[str]:
        return ["passing_yards", "rushing_yards", "receiving_yards", "receptions"]

    def team_targets(self) -> List[str]:
        return ["margin", "total"]

    def score_ranges(self) -> Dict[str, Any]:
        return {"team_pts": (0.0, 80.0), "total": (0.0, 120.0), "margin": (-70.0, 70.0)}

    def predict_game(self, home: str, away: str, game_date: str, season: Optional[str] = None) -> Any:
        try:
            from models.cfb_team_predictor import default_cfb_team_predictor
        except ImportError:
            return None
        if self._team_predictor is None:
            self._team_predictor = default_cfb_team_predictor()
        return self._team_predictor.predict_game(
            home=self.canonical_team(home, strict=False), away=self.canonical_team(away, strict=False),
            game_date=game_date, season=season or self.season_from_date(game_date),
        )

    def predict_player(self, player_name: str, season: Optional[str] = None, **kw) -> Any:
        """Anchored player-prop projections (pass/rush/rec yards, receptions).
        Returns None until the CFB player models (artifacts/cfb_player/) exist."""
        try:
            from models.cfb_player_predictor import default_cfb_player_predictor
        except ImportError:
            return None
        if self._player_predictor is None:
            self._player_predictor = default_cfb_player_predictor()
        return self._player_predictor.predict_player(player_name, season=season or self.current_season())

    def schedule(self, game_date: Optional[str] = None) -> List[Dict[str, Any]]:
        return []  # no free forward-schedule feed wired yet
