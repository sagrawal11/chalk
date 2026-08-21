"""NBA sport plugin (flagship). A thin adapter that exposes the existing NBA
modules (feature_engine, predictor, and — once trained — team_predictor) behind
the shared ``Sport`` interface.

Heavy imports (feature_engine / predictor / team_predictor / requests) are done
lazily *inside* methods so importing this module stays cheap and the identity
methods are testable without pandas/lightgbm installed.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sports.base import Sport
from sports.nba import teams

logger = logging.getLogger(__name__)

ESPN_SCOREBOARD_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
)


class NBASport(Sport):
    key = "nba"
    display_name = "NBA"
    capabilities = frozenset({"predict_player", "predict_game", "schedule"})

    def __init__(self) -> None:
        self._predictor: Any = None        # cached NBAPredictor
        self._team_predictor: Any = None   # cached TeamPredictor (Phase 1)

    # --- identity / data ---
    def canonical_team(self, code: str, *, strict: bool = True) -> str:
        return teams.canonical_team(code, strict=strict)

    def current_season(self) -> str:
        now = datetime.now()
        start = now.year if now.month >= 10 else now.year - 1
        return teams.season_int_to_str(start)

    def season_from_date(self, game_date: str) -> str:
        d = datetime.strptime(str(game_date)[:10], "%Y-%m-%d")
        start = d.year if d.month >= 10 else d.year - 1
        return teams.season_int_to_str(start)

    def player_targets(self) -> List[str]:
        from feature_engine import TARGET_STATS  # lazy: pulls in pandas/numpy

        return list(TARGET_STATS)

    def team_targets(self) -> List[str]:
        # The team model predicts game margin & total (per-team points derived).
        return ["margin", "total", "home_pts", "away_pts"]

    def score_ranges(self) -> Dict[str, Any]:
        # Sanity bounds for content/caps (empirical NBA ranges).
        return {
            "team_pts": (70.0, 160.0),
            "total": (150.0, 300.0),
            "margin": (-60.0, 60.0),
        }

    # --- capabilities ---
    def predict_player(
        self,
        player_name: str,
        opponent_team: str,
        is_home: bool,
        game_date: str,
        season: Optional[str] = None,
        injury_status: str = "Healthy",
        teammates_out: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        from models.predictor import NBAPredictor  # lazy: pulls in lightgbm

        if self._predictor is None:
            self._predictor = NBAPredictor()
        return self._predictor.predict_player_stats(
            player_name=player_name,
            opponent_team=self.canonical_team(opponent_team, strict=False),
            is_home=is_home,
            game_date=game_date,
            season=season or self.season_from_date(game_date),
            injury_status=injury_status,
            teammates_out=teammates_out,
        )

    def predict_game(
        self,
        home: str,
        away: str,
        game_date: str,
        season: Optional[str] = None,
    ) -> Any:
        """Return a GamePrediction for a matchup. Returns ``None`` until the team
        model (Phase 1, Task #8) is built/trained — the daily loop treats a
        ``None`` as "no team-market content for this game yet"."""
        try:
            from models.team_predictor import default_team_predictor
        except ImportError:
            logger.debug("team_predictor not available yet (Phase 1 pending)")
            return None
        if self._team_predictor is None:
            self._team_predictor = default_team_predictor()
        return self._team_predictor.predict_game(
            home=self.canonical_team(home),
            away=self.canonical_team(away),
            game_date=game_date,
            season=season or self.season_from_date(game_date),
        )

    def schedule(self, game_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """Today's NBA slate from ESPN, with canonical team codes. (Single source
        of truth; app.py's inline fetch is folded in here during Phase 5.)"""
        import requests  # lazy

        resp = requests.get(ESPN_SCOREBOARD_URL, timeout=10)
        data = resp.json()
        games: List[Dict[str, Any]] = []
        for ev in data.get("events", []):
            try:
                comp = ev["competitions"][0]
                competitors = comp["competitors"]
                home = next(c for c in competitors if c["homeAway"] == "home")["team"]
                away = next(c for c in competitors if c["homeAway"] == "away")["team"]
                games.append(
                    {
                        "game_id": ev.get("id"),
                        "date": (game_date or datetime.now().strftime("%Y-%m-%d")),
                        "time": ev.get("date"),
                        "home": self.canonical_team(home["abbreviation"], strict=False),
                        "away": self.canonical_team(away["abbreviation"], strict=False),
                    }
                )
            except (KeyError, StopIteration, IndexError) as e:  # skip malformed events
                logger.warning("Skipping malformed ESPN event: %s", e)
        return games
