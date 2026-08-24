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

_MLB_RESULT = {  # the real MLB-20 ledger row (SP_RA drop) — content is sport-generic
    "id": "MLB-20", "sport": "mlb", "rung": 3,
    "name": "Starting pitcher — rolling runs allowed (SP_RA)",
    "eval_window": "2018–2024", "decision": "drop",
    "hypothesis": "Who takes the mound tonight should move the line more than any team-level stat.",
    "champion_metrics": {"su_acc": 0.5667, "winner_logloss": 0.6816, "margin_mae": 3.449, "total_mae": 3.564},
    "challenger_metrics": {"su_acc": 0.567, "winner_logloss": 0.6825, "margin_mae": 3.457, "total_mae": 3.562},
}

_MLB_SCORE = {
    "league": "MLB", "when": "WED · 7:05 PM ET",
    "away_name": "Los Angeles Dodgers", "home_name": "San Diego Padres",
    "away_city": "Los Angeles", "home_city": "San Diego",
    "away_score": 5, "home_score": 4, "winner_side": "away", "confidence": 0.55,
}

_NHL_RESULT = {  # the real NHL-06 ledger row (FORM kept -> nhl-v2) — the first NHL climb
    "id": "NHL-06", "sport": "nhl", "rung": 2, "name": "Last-10-game form (FORM)",
    "eval_window": "2018-19–2024-25", "decision": "keep",
    "hypothesis": "A recent hot/cold streak captures momentum the season goal average smooths over.",
    "champion_metrics": {"su_acc": 0.5728, "winner_logloss": 0.676, "margin_mae": 2.15, "total_mae": 1.865},
    "challenger_metrics": {"su_acc": 0.5765, "winner_logloss": 0.675, "margin_mae": 2.147, "total_mae": 1.865},
}

_NHL_SCORE = {
    "league": "NHL", "when": "SAT · 7:00 PM ET",
    "away_name": "Colorado Avalanche", "home_name": "Vegas Golden Knights",
    "away_city": "Colorado", "home_city": "Vegas",
    "away_score": 2, "home_score": 4, "winner_side": "home", "confidence": 0.57,
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


def test_experiment_log_renders_for_mlb():
    # Content generators are sport-generic: an MLB ledger row renders the same
    # experiment-log card, honest DROP styling, disclaimer intact.
    html = build_experiment_log_html(
        _MLB_RESULT, metric="auto",
        next_exp={"id": "MLB-21", "name": "Starting pitcher — rolling ERA (SP_ERA)",
                  "hypothesis": "ERA isolates the starter's own runs from the bullpen."})
    _no_unfilled(html)
    assert "Starting pitcher" in html and "DROPPED" in html
    assert "SP_ERA" in html and "A research project." in html


def test_score_card_builds():
    html = build_score_html(_SAMPLE_SCORE)
    _no_unfilled(html)
    assert "Buffalo Bills" in html and "Not betting advice" in html


def test_experiment_log_renders_for_nhl_keep():
    # An NHL KEEP (the first NHL climb) renders with the "kept" styling + NEXT block.
    html = build_experiment_log_html(
        _NHL_RESULT, metric="auto",
        next_exp={"id": "NHL-07", "name": "Rest days & rest differential",
                  "hypothesis": "Dense back-to-backs should tire a team."})
    _no_unfilled(html)
    assert "Last-10-game form" in html and "KEPT" in html
    assert "A research project." in html


def test_score_card_renders_for_mlb():
    html = build_score_html(_MLB_SCORE)
    _no_unfilled(html)
    assert "San Diego Padres" in html and "Los Angeles Dodgers" in html
    assert "MLB" in html and "Not betting advice" in html


def test_score_card_renders_for_nhl():
    html = build_score_html(_NHL_SCORE)
    _no_unfilled(html)
    assert "Vegas Golden Knights" in html and "Colorado Avalanche" in html
    assert "NHL" in html and "Not betting advice" in html


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
