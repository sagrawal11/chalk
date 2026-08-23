"""Hermetic tests for the M3 content generators (HTML build only — no rasterization).

Guards that every template fills cleanly (no leftover %%TOKENS%%) and that the key
copy / honesty elements are present.
"""
from content.carousel import _SAMPLE as CAROUSEL_SAMPLE, build_carousel_cover_html
from content.feature_post import build_experiment_log_html, pick_display_metric
from content.game_cards import (_SAMPLE_RESULTS, _SAMPLE_SCORE,
                                build_results_html, build_score_html)
from content.triptych import build_triptych_html

_RESULT = {  # a ledger-row-shaped ExperimentResult (NFL-10 keep)
    "id": "NFL-10", "sport": "nfl", "rung": 3, "name": "Opponent-adjusted offense",
    "eval_window": "2002–2024", "decision": "keep", "hypothesis": "Adjust for schedule.",
    "champion_metrics": {"su_acc": 0.6249, "winner_logloss": 0.6451, "margin_mae": 10.73, "total_mae": 10.953},
    "challenger_metrics": {"su_acc": 0.6247, "winner_logloss": 0.6442, "margin_mae": 10.704, "total_mae": 10.933},
}


def _no_unfilled(html: str) -> None:
    assert "%%" not in html, "template has an unfilled %%TOKEN%%"


def test_pick_display_metric_prefers_the_metric_that_moved():
    # SU is flat (0.02pp) but margin moved (0.026) -> feature margin MAE (Option C).
    assert pick_display_metric(_RESULT) == "margin_mae"


def test_experiment_log_keep_builds():
    html = build_experiment_log_html(
        _RESULT, metric="auto", next_exp={"id": "NFL-19", "name": "EPA/play", "hypothesis": "EPA."})
    _no_unfilled(html)
    assert "Opponent-adjusted offense" in html
    assert "KEPT" in html and "MARGIN MAE" in html
    assert "A research project." in html


def test_experiment_log_drop_is_styled_muted():
    html = build_experiment_log_html({**_RESULT, "decision": "drop"}, metric="su_acc")
    _no_unfilled(html)
    assert "DROPPED" in html and 'class="dropped"' in html


def test_score_card_builds():
    html = build_score_html(_SAMPLE_SCORE)
    _no_unfilled(html)
    assert "Buffalo Bills" in html and "Not betting advice" in html


def test_results_card_builds():
    html = build_results_html(_SAMPLE_RESULTS)
    _no_unfilled(html)
    assert "How the calls landed" in html and "HIT" in html and "MISS" in html


def test_carousel_cover_builds():
    html = build_carousel_cover_html(CAROUSEL_SAMPLE)
    _no_unfilled(html)
    assert "Today's calls" in html and "SWIPE FOR EACH" in html


def test_triptych_builds():
    html = build_triptych_html()
    _no_unfilled(html)
    assert "market-blind model" in html and "No market data ever enters" in html
