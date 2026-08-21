"""MLB sport plugin implementing the shared ``Sport`` interface (StatsAPI data;
lines via The Odds API). Team run-score model wired; player props TBD."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sports.base import Sport
from sports.mlb import teams

logger = logging.getLogger(__name__)
STATSAPI = "https://statsapi.mlb.com/api/v1/schedule"


class MLBSport(Sport):
    key = "mlb"
    display_name = "MLB"
    capabilities = frozenset({"schedule", "predict_game", "predict_player"})

    def __init__(self) -> None:
        self._team_predictor: Any = None
        self._batter_predictor: Any = None

    def canonical_team(self, code: str, *, strict: bool = True) -> str:
        return teams.canonical_team(code, strict=strict)

    def current_season(self) -> str:
        return str(datetime.now().year)

    def season_from_date(self, game_date: str) -> str:
        return teams.season_from_date(game_date)

    def player_targets(self) -> List[str]:
        # Batter hitting props (this track). Pitcher Ks are a separate track/model.
        from sports.mlb.batter_features import PROP_TARGETS
        return list(PROP_TARGETS)

    def team_targets(self) -> List[str]:
        return ["margin", "total", "home_runs", "away_runs"]

    def score_ranges(self) -> Dict[str, Any]:
        return {"team_pts": (0.0, 20.0), "total": (4.0, 25.0), "margin": (-15.0, 15.0)}

    def predict_game(self, home: str, away: str, game_date: str, season: Optional[str] = None) -> Any:
        """Predicted run score + win/total probs. Returns None until the MLB team
        model (artifacts/mlb_team/) is trained."""
        try:
            from models.mlb_team_predictor import default_mlb_team_predictor
        except ImportError:
            return None
        if self._team_predictor is None:
            self._team_predictor = default_mlb_team_predictor()
        return self._team_predictor.predict_game(
            home=self.canonical_team(home, strict=False), away=self.canonical_team(away, strict=False),
            game_date=game_date, season=season or self.season_from_date(game_date),
        )

    def predict_player(self, batter_id: int, season: Optional[str] = None, **kw) -> Any:
        """Batter hitting-prop projections (hits, total bases, home runs), keyed by
        StatsAPI batter id. Returns None until the MLB batter models
        (artifacts/mlb_batter/) are trained."""
        try:
            from models.mlb_batter_predictor import default_mlb_batter_predictor
        except ImportError:
            return None
        if self._batter_predictor is None:
            self._batter_predictor = default_mlb_batter_predictor()
        return self._batter_predictor.predict(int(batter_id), season=season or self.current_season())

    def schedule(self, game_date: Optional[str] = None) -> List[Dict[str, Any]]:
        import requests

        date = game_date or datetime.now().strftime("%Y-%m-%d")
        r = requests.get(STATSAPI, params={"sportId": 1, "date": date, "gameType": "R"}, timeout=20)
        out: List[Dict[str, Any]] = []
        for d in r.json().get("dates", []):
            for g in d.get("games", []):
                out.append({
                    "game_id": g.get("gamePk"), "date": date,
                    "home": self.canonical_team(g["teams"]["home"]["team"]["name"], strict=False),
                    "away": self.canonical_team(g["teams"]["away"]["team"]["name"], strict=False),
                })
        return out
