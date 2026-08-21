"""Auto-slate prop enumeration for MLB batters + NHL skaters, and the daily_content
dispatch that stitches them into a day's cards. Hermetic: predictors get synthetic
`_latest` records (team/name) and a stubbed `predict`, so no models or network."""
from pathlib import Path

from models.mlb_batter_predictor import MLBBatterPredictor
from models.nhl_skater_predictor import NHLSkaterPredictor

_NONE = Path("/nonexistent")   # no joblibs -> __init__ leaves models empty


def test_mlb_batter_slate_filters_to_slate_teams_and_ranks_by_tb(monkeypatch):
    bp = MLBBatterPredictor(model_dir=_NONE)
    bp._m = {"totalBases": object()}          # force available()
    bp._latest = {
        1: {"team": "NYY", "name": "Aaron Judge"},
        2: {"team": "BOS", "name": "Rafael Devers"},
        3: {"team": "LAD", "name": "Mookie Betts"},   # off-slate -> excluded
    }
    proj = {1: {"hits": 1.4, "totalBases": 2.8, "homeRuns": 0.5},
            2: {"hits": 1.1, "totalBases": 1.9, "homeRuns": 0.3},
            3: {"hits": 1.5, "totalBases": 3.0, "homeRuns": 0.6}}
    monkeypatch.setattr(bp, "predict", lambda bid, season=None: proj[bid])

    cards = bp.slate_projections([{"home": "NYY", "away": "BOS"}], season="2025")
    assert [c["player_name"] for c in cards] == ["Aaron Judge", "Rafael Devers"]  # TB desc, LAD gone
    assert cards[0]["matchup"] == "vs BOS" and cards[1]["matchup"] == "@ NYY"
    assert all(c["sport"] == "mlb" for c in cards)


def test_nhl_skater_slate_filters_to_slate_teams_and_ranks_by_points(monkeypatch):
    sp = NHLSkaterPredictor(model_dir=_NONE)
    sp._blobs = {"points": object()}          # force available()
    sp._latest = {
        10: {"team": "TOR", "name": "Auston Matthews"},
        20: {"team": "BOS", "name": "David Pastrnak"},
        30: {"team": "EDM", "name": "Connor McDavid"},   # off-slate -> excluded
    }
    proj = {10: {"points": 1.3, "shots": 4.2},
            20: {"points": 1.1, "shots": 3.8},
            30: {"points": 1.6, "shots": 5.0}}
    monkeypatch.setattr(sp, "predict", lambda pid, season=None: proj[pid])

    cards = sp.slate_projections([{"home": "TOR", "away": "BOS"}], season="2024")
    assert [c["player_name"] for c in cards] == ["Auston Matthews", "David Pastrnak"]
    assert cards[0]["matchup"] == "vs BOS"
    assert all(c["sport"] == "nhl" for c in cards)


def test_slate_respects_limit(monkeypatch):
    bp = MLBBatterPredictor(model_dir=_NONE)
    bp._m = {"totalBases": object()}
    bp._latest = {i: {"team": "NYY", "name": f"p{i}"} for i in range(6)}
    monkeypatch.setattr(bp, "predict", lambda bid, season=None: {"totalBases": float(bid)})
    cards = bp.slate_projections([{"home": "NYY", "away": "BOS"}], season="2025", limit=2)
    assert len(cards) == 2 and [c["player_name"] for c in cards] == ["p5", "p4"]  # top-2 by TB


def test_slate_empty_when_unavailable_or_no_games():
    bp = MLBBatterPredictor(model_dir=_NONE)               # no models loaded
    assert bp.slate_projections([{"home": "NYY", "away": "BOS"}]) == []
    bp._m = {"hits": object()}
    bp._latest = {}
    assert bp.slate_projections([]) == []                  # available but empty slate


def test_sport_slate_props_mlb_combines_pitcher_and_batter(monkeypatch):
    import models.mlb_batter_predictor as mbp
    import models.mlb_pitcher_predictor as mpp

    class _P:
        def slate_projections(self, games, season=None):
            return [{"player_name": "Gerrit Cole", "projections": {"K": 6.5},
                     "matchup": "vs BOS", "sport": "mlb"}]

    class _B:
        def slate_projections(self, games, season=None):
            return [{"player_name": "Aaron Judge", "projections": {"hits": 1.4},
                     "matchup": "vs BOS", "sport": "mlb"}]

    monkeypatch.setattr(mpp, "default_mlb_pitcher_predictor", lambda: _P())
    monkeypatch.setattr(mbp, "default_mlb_batter_predictor", lambda: _B())
    from pipeline.daily_content import _sport_slate_props
    cards = _sport_slate_props("mlb", [{"home": "NYY", "away": "BOS"}], "2025")
    assert [c["player_name"] for c in cards] == ["Gerrit Cole", "Aaron Judge"]  # pitcher then batter


def test_sport_slate_props_nhl_uses_skater(monkeypatch):
    import models.nhl_skater_predictor as nsp

    class _S:
        def slate_projections(self, games, season=None):
            return [{"player_name": "Auston Matthews", "projections": {"points": 1.3},
                     "matchup": "vs BOS", "sport": "nhl"}]

    monkeypatch.setattr(nsp, "default_nhl_skater_predictor", lambda: _S())
    from pipeline.daily_content import _sport_slate_props
    cards = _sport_slate_props("nhl", [{"home": "TOR", "away": "BOS"}], "2024")
    assert cards[0]["player_name"] == "Auston Matthews" and cards[0]["sport"] == "nhl"
