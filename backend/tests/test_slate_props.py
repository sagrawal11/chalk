"""Props end-to-end: SlatePropModel, props card, and the daily star-card path.
Hermetic (stub predictor/context; real roster only for the display name)."""
import glob

from PIL import Image

import track_record.grade as grade
import track_record.lock as lock
from content.render import caption_for_props, render_props_card
from models.distribution import PoissonNBHead
from picks.slate_props import SlatePropModel
from pipeline.daily_content import run_day
from predictions.schema import GamePrediction


def _predict(slug, opp, is_home, date, season):
    if slug == "lebron_james":
        return {"PTS": PoissonNBHead(27.0, 8.0), "OREB": PoissonNBHead(1.2, None),
                "DREB": PoissonNBHead(6.8, None), "AST": PoissonNBHead(8.0, None)}
    return None


def _ctx(slug, games, date):
    if slug == "lebron_james":
        return {"team": "LAL", "opponent": "BOS", "is_home": True, "game_key": f"nba:{date}:BOS@LAL"}
    return None


def _model(date="2025-01-15"):
    return SlatePropModel(date, [{"home": "LAL", "away": "BOS"}], "2024-25",
                          predict_distribution=_predict, context_fn=_ctx)


def test_prop_model_head_projections_and_reb_composition():
    m = _model()
    assert m.head("lebron_james", "PTS").sf(20.5) > 0.5
    assert abs(m.head("lebron_james", "REB").mean() - 8.0) < 1e-6   # OREB+DREB
    proj = m.projections("lebron_james")
    assert proj["PTS"] == 27.0 and proj["REB"] == 8.0 and proj["AST"] == 8.0
    assert m.matchup("lebron_james") == "vs BOS"
    assert m.head("nobody", "PTS") is None and m.projections("nobody") is None
    assert m.dist_lookup()("lebron_james", "AST") is not None


def test_props_card_and_caption(tmp_path):
    p = render_props_card("LeBron James", {"PTS": 27.3, "REB": 8.1, "AST": 9.0, "FG3M": 2.1, "STL": 1.2},
                          tmp_path, "vs BOS")
    assert p.exists() and Image.open(p).size == (1080, 1350)
    c = caption_for_props("LeBron James", {"PTS": 27.3, "REB": 8.1, "AST": 9.0}, "vs BOS")
    assert "27 PTS" in c and "not betting advice" in c.lower()


class _StubTP:
    def predict_game(self, home, away, game_date, season=None):
        return GamePrediction(sport="nba", game_date=game_date, home=home, away=away,
                              mu_total=224.0, sigma_total=20.0, mu_margin=6.0, sigma_margin=14.0,
                              pred_home_pts=115.0, pred_away_pts=109.0, p_home_win=0.66)


def test_run_day_renders_star_prop_card(tmp_path, monkeypatch):
    monkeypatch.setattr(lock, "LOCKED_DIR", tmp_path / "locked")
    monkeypatch.setattr(grade, "RESULTS_LEDGER", tmp_path / "ledger.parquet")
    summary = run_day(
        "nba", "2025-01-15",
        games=[{"home": "LAL", "away": "BOS"}],
        team_predictor=_StubTP(),
        prop_model=_model(),
        star_players=["lebron_james"],
        out_root=tmp_path / "content",
    )
    assert summary["prop_cards"] >= 1
    assert glob.glob(str(tmp_path / "content" / "2025-01-15" / "props_*.png"))
