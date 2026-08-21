"""NFL sport plugin implementing the shared ``Sport`` interface.

Identity + schedule are wired to nflverse now; predict_game / predict_player
raise NotImplementedError until NFL models are trained (the generic pipeline —
team feature engine, honest validation, calibration, hybrid residuals — is
reused per sport, so training NFL is "build the feature engine + run the same
trainers", not new infrastructure).
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sports.base import Sport
from sports.nfl import teams

logger = logging.getLogger(__name__)


class NFLSport(Sport):
    key = "nfl"
    display_name = "NFL"
    capabilities = frozenset({"schedule", "predict_game", "predict_player"})

    def __init__(self) -> None:
        self._team_predictor: Any = None
        self._player_predictor: Any = None

    def canonical_team(self, code: str, *, strict: bool = True) -> str:
        return teams.canonical_team(code, strict=strict)

    def _season_start_year(self, year: int, month: int) -> int:
        # NFL season is named by its START year; Jan/Feb playoffs belong to the
        # prior year's season. Regular season starts in Sept (preseason Aug).
        return year if month >= 8 else year - 1

    def current_season(self) -> str:
        now = datetime.now()
        return str(self._season_start_year(now.year, now.month))

    def season_from_date(self, game_date: str) -> str:
        d = datetime.strptime(str(game_date)[:10], "%Y-%m-%d")
        return str(self._season_start_year(d.year, d.month))

    def player_targets(self) -> List[str]:
        return [
            "passing_yards", "passing_tds", "interceptions",
            "rushing_yards", "rushing_tds", "carries",
            "receptions", "receiving_yards", "receiving_tds", "targets",
        ]

    def team_targets(self) -> List[str]:
        return ["margin", "total", "home_pts", "away_pts"]

    def score_ranges(self) -> Dict[str, Any]:
        return {"team_pts": (0.0, 70.0), "total": (20.0, 100.0), "margin": (-50.0, 50.0)}

    def predict_game(self, home: str, away: str, game_date: str, season: Optional[str] = None) -> Any:
        """Predicted score + win/spread/total probs. Returns None until the NFL
        team model is trained (artifacts/nfl_team/)."""
        try:
            from models.nfl_team_predictor import default_nfl_team_predictor
        except ImportError:
            return None
        if self._team_predictor is None:
            self._team_predictor = default_nfl_team_predictor()
        return self._team_predictor.predict_game(
            home=self.canonical_team(home), away=self.canonical_team(away),
            game_date=game_date, season=season or self.season_from_date(game_date),
        )

    def predict_player(self, player_name: str, season: Optional[str] = None, **kw) -> Any:
        """Player-prop projections (pass/rush/rec yards, receptions). Returns None
        until the NFL player models (artifacts/nfl_player/) are trained."""
        try:
            from models.nfl_player_predictor import default_nfl_player_predictor
        except ImportError:
            return None
        if self._player_predictor is None:
            self._player_predictor = default_nfl_player_predictor()
        return self._player_predictor.predict_player(player_name, season=season or self.current_season())

    def schedule(self, game_date: Optional[str] = None) -> List[Dict[str, Any]]:
        from sports.nfl import data

        date = game_date or datetime.now().strftime("%Y-%m-%d")
        year = int(self.season_from_date(date))
        s = data.load_schedules([year])
        s = s[s["game_date"].astype(str).str[:10] == date]
        return [
            {"game_id": r["game_id"], "date": date, "home": r["home"], "away": r["away"]}
            for _, r in s.iterrows()
        ]
