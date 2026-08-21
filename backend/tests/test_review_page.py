"""Static control-room review page (backend/content/review.py). Hermetic."""
from content.render import render_slate
from content.review import build_review_page
from predictions.schema import GamePrediction


def _gp():
    return GamePrediction(sport="nba", game_date="2025-01-15", home="LAL", away="BOS",
                          mu_total=224.0, sigma_total=20.0, mu_margin=6.0, sigma_margin=14.0,
                          pred_home_pts=115.0, pred_away_pts=109.0, p_home_win=0.66)


def test_render_slate_emits_review_page(tmp_path):
    render_slate("2025-01-15", [_gp()], None,
                 {"record": "3-1", "units": 2.0, "win_pct": 0.75, "streak": 2, "n_picks": 4},
                 out_root=tmp_path)
    idx = tmp_path / "2025-01-15" / "index.html"
    assert idx.exists()
    txt = idx.read_text()
    assert "score_BOS_at_LAL.png" in txt        # references the rendered card
    assert "3-1" in txt                          # shows the record
    assert "Copy caption" in txt                 # copy-ready captions


def test_build_review_page_standalone(tmp_path):
    # empty dir -> still a valid page with no cards
    p = build_review_page(tmp_path, "2025-01-15", None)
    assert p.exists() and "content review" in p.read_text()
