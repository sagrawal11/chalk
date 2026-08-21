"""Normalized, sport-agnostic prediction containers.

These are the contract the whole downstream pipeline speaks. They are
deliberately dependency-light (stdlib ``statistics.NormalDist`` for the normal
CDF — no numpy/scipy) and JSON-serializable so the daily track-record LOCK can
snapshot them immutably.

Team markets are derived from a normal model of game **margin** (home - away)
and **total** (home + away): win probability, spread-cover probability, and
total over/under all fall out of those two normals. Player props carry a mean
plus a distribution descriptor filled in by ``models.distribution`` (Phase 1).

Sign conventions:
- ``mu_margin`` is home minus away (positive => home favored).
- A **home spread** of ``-4.5`` means the home team is laid 4.5; the home side
  covers iff ``margin > 4.5`` (i.e. ``margin > -home_spread``).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from statistics import NormalDist
from typing import Any, Dict, Optional


def make_game_key(sport: str, game_date: str, away: str, home: str) -> str:
    """Stable join key across predictions, odds, and results.

    Callers must pass already-canonical team codes (schemas stay sport-agnostic
    and never import a sport's team map).
    """
    return f"{sport}:{game_date}:{away}@{home}"


@dataclass
class GamePrediction:
    """A single game's team-market prediction (the headline content unit)."""

    sport: str
    game_date: str          # "YYYY-MM-DD"
    home: str               # canonical code
    away: str               # canonical code
    mu_total: float
    sigma_total: float
    mu_margin: float        # home - away
    sigma_margin: float
    pred_home_pts: float
    pred_away_pts: float
    p_home_win: float
    # 3-way sports (soccer): draw + away-win probs. None for 2-way sports, where
    # away-win is implicitly 1 - p_home_win.
    p_draw: Optional[float] = None
    p_away_win: Optional[float] = None
    confidence: Optional[float] = None      # [0,1]; defaults from win prob
    model_version: str = ""
    locked_at: Optional[str] = None         # ISO ts, set at lock time
    game_key: str = ""

    def __post_init__(self) -> None:
        if self.sigma_total <= 0 or self.sigma_margin <= 0:
            raise ValueError("sigma_total and sigma_margin must be > 0")
        if not self.game_key:
            self.game_key = make_game_key(self.sport, self.game_date, self.away, self.home)
        if self.confidence is None:
            self.confidence = self.default_confidence()

    def default_confidence(self) -> float:
        """Honest confidence: distance of the win prob from a coin flip, in [0,1]."""
        return abs(float(self.p_home_win) - 0.5) * 2.0

    # --- derived market probabilities (all from the two normals) ---
    def p_total_over(self, total_line: float) -> float:
        return 1.0 - NormalDist(self.mu_total, self.sigma_total).cdf(total_line)

    def p_total_under(self, total_line: float) -> float:
        return 1.0 - self.p_total_over(total_line)

    def p_home_cover(self, home_spread: float) -> float:
        """P(home covers) for a home spread like -4.5 => P(margin > 4.5)."""
        return 1.0 - NormalDist(self.mu_margin, self.sigma_margin).cdf(-home_spread)

    def p_away_cover(self, home_spread: float) -> float:
        return 1.0 - self.p_home_cover(home_spread)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "GamePrediction":
        return cls(**d)


@dataclass
class PlayerPropPrediction:
    """A single player-stat projection (e.g. LeBron PTS)."""

    sport: str
    game_date: str
    player_slug: str
    stat: str
    mu: float
    home: str = ""
    away: str = ""
    player_name: str = ""
    team: str = ""
    opponent: str = ""
    # Distribution descriptor, filled by models.distribution (Phase 1):
    #   "point" (mu only), "normal" ({"sigma": s}), "nb" ({"dispersion": r}),
    #   "empirical" ({"quantiles": [...]})
    dist_kind: str = "point"
    dist_params: Dict[str, Any] = field(default_factory=dict)
    line: Optional[float] = None       # set when a pick is made against a line
    prob_over: Optional[float] = None  # cached P(stat > line) at pick time
    model_version: str = ""
    game_key: str = ""

    def __post_init__(self) -> None:
        if not self.game_key and self.home and self.away:
            self.game_key = make_game_key(self.sport, self.game_date, self.away, self.home)

    def p_over(self, line: float) -> float:
        """P(stat > line). ``normal`` is handled here; richer distributions
        (``nb``/``empirical``) are computed by ``models.distribution`` (Phase 1),
        which populates ``prob_over``.
        """
        if self.dist_kind == "normal":
            sigma = float(self.dist_params.get("sigma", 0.0))
            if sigma <= 0:
                raise ValueError("normal dist requires a positive 'sigma'")
            return 1.0 - NormalDist(self.mu, sigma).cdf(line)
        raise NotImplementedError(
            f"p_over for dist_kind={self.dist_kind!r} is provided by "
            "models.distribution (Phase 1)"
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PlayerPropPrediction":
        return cls(**d)
