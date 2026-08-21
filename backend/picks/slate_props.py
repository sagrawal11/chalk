"""Slate prop model: given today's games, resolve each player's game context and
serve their predictive distributions + projected stat line.

Decoupled from the concrete predictor/roster (both injected) so it's testable
without models or player-data on disk. Composes REB = OREB + DREB (the model
predicts the two boards separately; PrizePicks lists total Rebounds).
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from models.distribution import PoissonNBHead

HEADLINE_STATS = ["PTS", "REB", "AST"]


class SlatePropModel:
    def __init__(
        self,
        game_date: str,
        games: List[Dict[str, str]],
        season: str,
        *,
        predict_distribution: Callable[..., Optional[Dict[str, Any]]],
        context_fn: Callable[..., Optional[Dict[str, Any]]],
    ):
        self.game_date = game_date
        self.games = games
        self.season = season
        self._predict = predict_distribution   # (slug, opponent, is_home, date, season) -> {stat: head}
        self._ctx = context_fn                  # (slug, games, date) -> ctx | None
        self._cache: Dict[str, Optional[Dict[str, Any]]] = {}

    def _load(self, slug: str) -> Optional[Dict[str, Any]]:
        if slug in self._cache:
            return self._cache[slug]
        ctx = self._ctx(slug, self.games, self.game_date)
        if not ctx:
            self._cache[slug] = None
            return None
        dists = self._predict(slug, ctx["opponent"], ctx["is_home"], self.game_date, self.season) or {}
        self._cache[slug] = {"dists": dists, "ctx": ctx}
        return self._cache[slug]

    def head(self, slug: str, stat: str):
        e = self._load(slug)
        if not e:
            return None
        d = e["dists"]
        if stat in d:
            return d[stat]
        if stat == "REB" and "OREB" in d and "DREB" in d:  # compose total boards
            return PoissonNBHead(mu=float(d["OREB"].mean() + d["DREB"].mean()), dispersion=None)
        return None

    def projections(self, slug: str) -> Optional[Dict[str, float]]:
        e = self._load(slug)
        if not e:
            return None
        d = e["dists"]
        out = {s: round(float(h.mean()), 1) for s, h in d.items()}
        if "REB" not in out and "OREB" in d and "DREB" in d:
            out["REB"] = round(float(d["OREB"].mean() + d["DREB"].mean()), 1)
        return out

    def matchup(self, slug: str) -> str:
        e = self._load(slug)
        if not e:
            return ""
        c = e["ctx"]
        return f"{'vs' if c['is_home'] else '@'} {c['opponent']}"

    def dist_lookup(self) -> Callable[[str, str], Any]:
        return lambda subj, stat: self.head(subj, stat)
