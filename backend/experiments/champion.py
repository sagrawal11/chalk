"""Champion descriptor: the per-sport model config the experiment harness reads.

A champion is ``{sport, model_version, rung, active_feature_builders, feature_cols,
cumulative_metrics}``. Feature-builders are toggled on progressively (the roadmap
rungs); a champion's ``feature_cols`` are resolved from its active builders via the
``FEATURE_BUILDERS`` registry, so "add one feature" is a config change, not new
code (ARCHITECTURE §1/§5d).

M1 seeds the NFL Rung-1 champion. M2 grows the registry (eventually
``experiments/roadmap.yaml``) and adds the champion/challenger runner + ledger.
The champion stays market-blind: no MARKET_* column is ever a builder output.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

BACKEND_ROOT = Path(__file__).resolve().parents[1]
# Tracked (NOT models/artifacts/, which is gitignored): the champion descriptor is
# config + public progression record, so it lives in the repo.
CHAMPION_DIR = BACKEND_ROOT / "artifacts"

# Roadmap feature-builder -> the frame columns it toggles on. Grows per rung in M2
# (and moves to experiments/roadmap.yaml); M1 seeds the NFL Rung-1 box-score set.
# NOTE: never map a builder to a MARKET_* column; the champion is market-blind.
FEATURE_BUILDERS: Dict[str, Dict[str, List[str]]] = {
    "nfl": {
        # Rung 1: basic box stats (the deliberately-simple day-1 baseline).
        "NFL-01": ["HOME_OFF", "AWAY_OFF"],                 # season-to-date points scored
        "NFL-02": ["HOME_DEF", "AWAY_DEF"],                 # season-to-date points allowed
        "NFL-03": ["NET_DIFF"],                             # net point differential
        "NFL-04": ["HOME_WINPCT", "AWAY_WINPCT"],           # season-to-date win pct
        "NFL-05": ["HOME_PRIOR_DIFF", "AWAY_PRIOR_DIFF"],   # prior-season carryover
        # Rung 2+ builders that are buildable from the cached schedule frame today.
        "NFL-06": ["HOME_FORM", "AWAY_FORM"],               # last-3 form (Rung 2)
        "NFL-10": ["HOME_OFF_ADJ", "AWAY_OFF_ADJ"],         # opponent-adjusted offense (Rung 3)
        "NFL-11": ["HOME_DEF_ADJ", "AWAY_DEF_ADJ"],         # opponent-adjusted defense (Rung 3)
        "NFL-14": ["HOME_REST", "AWAY_REST", "REST_DIFF"],  # rest / rest diff (Rung 4)
        "NFL-37": ["DIV_GAME"],                             # divisional game (Rung 7)
        "NFL-38": ["IS_DOME", "WIND", "TEMP"],              # weather (Rung 7)
    },
    "mlb": {
        # Rung 1: basic box stats (the deliberately-simple day-1 baseline). All
        # columns already exist in sports/mlb/team_features.build_team_game_frame,
        # so an MLB rung is a config change, not new feature code.
        "MLB-01": ["HOME_OFF", "AWAY_OFF"],                 # season-to-date runs scored
        "MLB-02": ["HOME_DEF", "AWAY_DEF"],                 # season-to-date runs allowed
        "MLB-03": ["NET_DIFF"],                             # net run differential
        "MLB-04": ["HOME_WINPCT", "AWAY_WINPCT"],           # season-to-date win pct
        "MLB-05": ["HOME_PRIOR_DIFF", "AWAY_PRIOR_DIFF"],   # prior-season carryover
        # Rung 2: recent form (last-10 run differential).
        "MLB-06": ["HOME_FORM", "AWAY_FORM"],               # last-10 form (Rung 2)
        "MLB-07": ["HOME_REST", "AWAY_REST", "REST_DIFF"],  # rest / rest diff (Rung 2)
        # Rung 3: the STARTING PITCHER (the dominant MLB signal; the MLB analog of
        # NFL's QB). SP_RA is schedule-only (cheap); SP_ERA needs the pitcher-log
        # backfill (see team_features.fetch_sp_era); both stay market-blind.
        "MLB-20": ["HOME_SP_RA", "AWAY_SP_RA", "SP_RA_DIFF"],     # starter rolling runs-allowed
        "MLB-21": ["HOME_SP_ERA", "AWAY_SP_ERA", "SP_ERA_DIFF"],  # starter rolling ERA
    },
    "nhl": {
        # Rung 1: basic box stats (goals for/against), the day-1 baseline. Every
        # column already exists in sports/nhl/team_features.build_team_game_frame.
        "NHL-01": ["HOME_OFF", "AWAY_OFF"],                 # season-to-date goals scored
        "NHL-02": ["HOME_DEF", "AWAY_DEF"],                 # season-to-date goals allowed
        "NHL-03": ["NET_DIFF"],                             # net goal differential
        "NHL-04": ["HOME_WINPCT", "AWAY_WINPCT"],           # season-to-date win pct
        "NHL-05": ["HOME_PRIOR_DIFF", "AWAY_PRIOR_DIFF"],   # prior-season carryover
        # Rung 2: recent form + rest (NHL plays dense back-to-backs, so rest may bite).
        "NHL-06": ["HOME_FORM", "AWAY_FORM"],               # last-10 form (Rung 2)
        "NHL-07": ["HOME_REST", "AWAY_REST", "REST_DIFF"],  # rest / rest diff (Rung 2)
        # The dominant NHL signal, the starting GOALIE, needs the boxscore endpoint
        # (the schedule only exposes the post-game winner), so it's a needs_builder
        # future rung, not wired here. Market-blind throughout: no MARKET_* column.
    },
}


# Param-based sports (soccer): the champion is a set of Poisson MODEL PARAMS, not
# feature columns, because the market-blind soccer champion is a parametric 3-way
# Poisson model (not a LightGBM margin regressor). A "builder" here toggles a model
# knob; builders fold over the baseline (backtest.soccer_backtest.BASELINE_PARAMS).
SOCCER_BUILDERS: Dict[str, Dict[str, Any]] = {
    "SOC-01": {},                          # baseline Poisson (the seed champion)
    "SOC-02": {"dixon_coles": True},       # Dixon-Coles low-score correction (draws)
    "SOC-03": {"cross_season": True},      # cross-season prior (early-season cold-start)
    "SOC-04": {"home_field": 1.30},        # a stronger home-field prior (tunable knob)
}
PARAM_BUILDERS: Dict[str, Dict[str, Dict[str, Any]]] = {"soccer": SOCCER_BUILDERS}


def resolve_model_params(sport: str, builders: List[str]) -> Dict[str, Any]:
    """Fold active param-builders over the sport's baseline model params (later
    builders win). Used by param-based sports (soccer) instead of resolve_feature_cols."""
    reg = PARAM_BUILDERS.get(sport, {})
    unknown = [b for b in builders if b not in reg]
    if unknown:
        raise ValueError(f"unknown {sport} model-param builder(s): {unknown}")
    from backtest.soccer_backtest import BASELINE_PARAMS
    params = dict(BASELINE_PARAMS)
    for b in builders:
        params.update(reg[b])
    return params


def bump_version(model_version: str) -> str:
    """'nfl-v1' -> 'nfl-v2'."""
    import re
    m = re.match(r"^(.*-v)(\d+)$", str(model_version))
    if not m:
        raise ValueError(f"unversioned model_version: {model_version!r}")
    return f"{m.group(1)}{int(m.group(2)) + 1}"


def resolve_feature_cols(sport: str, builders: List[str]) -> List[str]:
    """Flatten active builders -> ordered, de-duplicated feature columns."""
    reg = FEATURE_BUILDERS.get(sport, {})
    unknown = [b for b in builders if b not in reg]
    if unknown:
        raise ValueError(f"unknown {sport} feature-builder(s): {unknown}")
    cols: List[str] = []
    for b in builders:
        for c in reg[b]:
            if c not in cols:
                cols.append(c)
    return cols


@dataclass
class ChampionConfig:
    sport: str
    model_version: str
    rung: int
    active_feature_builders: List[str]
    feature_cols: List[str] = field(default_factory=list)
    model_params: Dict[str, Any] = field(default_factory=dict)   # param-based sports (soccer)
    cumulative_metrics: Dict[str, Any] = field(default_factory=dict)
    holdout_season: Optional[int] = None
    eval_window: Optional[str] = None
    created_at: Optional[str] = None
    notes: str = ""

    def validate(self) -> "ChampionConfig":
        if not self.sport or not isinstance(self.sport, str):
            raise ValueError("champion.sport must be a non-empty string")
        if not self.model_version or not isinstance(self.model_version, str):
            raise ValueError("champion.model_version must be a non-empty string")
        if not isinstance(self.rung, int) or isinstance(self.rung, bool) or self.rung < 1:
            raise ValueError("champion.rung must be an int >= 1")
        if not self.active_feature_builders:
            raise ValueError("champion.active_feature_builders must be non-empty")
        if self.sport in PARAM_BUILDERS:
            # Param-based sport (soccer): builders resolve to model params, not columns.
            self.model_params = resolve_model_params(self.sport, self.active_feature_builders)
            self.feature_cols = []
            return self
        resolved = resolve_feature_cols(self.sport, self.active_feature_builders)
        if self.feature_cols and self.feature_cols != resolved:
            raise ValueError(
                "champion.feature_cols out of sync with active_feature_builders; "
                f"expected {resolved}, got {self.feature_cols}"
            )
        self.feature_cols = resolved
        return self

    @classmethod
    def new(cls, sport: str, model_version: str, rung: int,
            active_feature_builders: List[str], **kw) -> "ChampionConfig":
        return cls(sport=sport, model_version=model_version, rung=rung,
                   active_feature_builders=list(active_feature_builders), **kw).validate()

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)


def champion_path(sport: str) -> Path:
    return CHAMPION_DIR / sport / "champion.json"


def save_champion(champ: ChampionConfig) -> Path:
    champ.validate()
    p = champion_path(champ.sport)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(champ.to_json() + "\n", encoding="utf-8")
    return p


def load_champion(sport: str) -> ChampionConfig:
    p = champion_path(sport)
    if not p.exists():
        raise FileNotFoundError(f"no champion for {sport}: {p}")
    data = json.loads(p.read_text(encoding="utf-8"))
    known = set(ChampionConfig.__dataclass_fields__)  # tolerate/ignore extra keys
    return ChampionConfig(**{k: v for k, v in data.items() if k in known}).validate()
