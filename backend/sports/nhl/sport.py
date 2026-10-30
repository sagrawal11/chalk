"""NHL sport plugin implementing the shared ``Sport`` interface (NHL API data).
Team goal-score model + skater points/shots props."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sports.base import Sport
from sports.nhl import teams

logger = logging.getLogger(__name__)
_SCORE_API = "https://api-web.nhle.com/v1/score/{date}"


class NHLSport(Sport):
    key = "nhl"
    display_name = "NHL"
    capabilities = frozenset({"schedule", "predict_game", "predict_player"})

    def __init__(self) -> None:
        self._team_predictor: Any = None
        self._skater_predictor: Any = None

    def canonical_team(self, code: str, *, strict: bool = True) -> str:
        return teams.canonical_team(code, strict=strict)

    def current_season(self) -> str:
        now = datetime.now()
        return str(now.year if now.month >= 9 else now.year - 1)

    def season_from_date(self, game_date: str) -> str:
        return teams.season_from_date(game_date)

    def player_targets(self) -> List[str]:
        return ["points", "shots"]  # skater props (points = goals+assists, shots on goal)

    def team_targets(self) -> List[str]:
        return ["margin", "total", "home_goals", "away_goals"]

    def score_ranges(self) -> Dict[str, Any]:
        return {"team_pts": (0.0, 12.0), "total": (2.0, 16.0), "margin": (-10.0, 10.0)}

    def predict_game(self, home: str, away: str, game_date: str, season: Optional[str] = None) -> Any:
        """Predicted goal score + win/total probs. Returns None until the NHL team
        model (artifacts/nhl_team/) is trained."""
        try:
            from models.nhl_team_predictor import default_nhl_team_predictor
        except ImportError:
            return None
        if self._team_predictor is None:
            self._team_predictor = default_nhl_team_predictor()
        return self._team_predictor.predict_game(
            home=self.canonical_team(home, strict=False), away=self.canonical_team(away, strict=False),
            game_date=game_date, season=season or self.season_from_date(game_date),
        )

    def predict_player(self, player_id: int, season: Optional[str] = None, **kw) -> Any:
        """Projected skater props {"points": .., "shots": ..} keyed by NHL API
        player id. Returns None until the skater model (artifacts/nhl_skater/)
        is trained."""
        try:
            from models.nhl_skater_predictor import default_nhl_skater_predictor
        except ImportError:
            return None
        if self._skater_predictor is None:
            self._skater_predictor = default_nhl_skater_predictor()
        return self._skater_predictor.predict(int(player_id), season=season or self.current_season())

    def schedule(self, game_date: Optional[str] = None) -> List[Dict[str, Any]]:
        import requests

        date = game_date or datetime.now().strftime("%Y-%m-%d")
        try:
            r = requests.get(_SCORE_API.format(date=date), timeout=20)
            games = r.json().get("games", [])
        except Exception:
            return []
        out: List[Dict[str, Any]] = []
        for g in games:
            if g.get("gameType") not in (None, 2):
                continue
            ht, at = g.get("homeTeam", {}), g.get("awayTeam", {})
            out.append({
                "game_id": g.get("id"), "date": date,
                "home": self.canonical_team(ht.get("abbrev", ""), strict=False),
                "away": self.canonical_team(at.get("abbrev", ""), strict=False),
            })
        return out
