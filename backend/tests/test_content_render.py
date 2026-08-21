"""Content rendering (backend/content/render.py). Hermetic — renders to tmp."""
from PIL import Image

from content.render import (
    caption_for_score,
    render_best_bet_card,
    render_record_card,
    render_score_card,
    render_slate,
)
from picks.best_bet import Pick
from predictions.schema import GamePrediction


def _gp():
    return GamePrediction(sport="nba", game_date="2025-01-15", home="LAL", away="BOS",
                          mu_total=224.0, sigma_total=20.0, mu_margin=6.0, sigma_margin=14.0,
                          pred_home_pts=115.0, pred_away_pts=109.0, p_home_win=0.66)


def _pick():
    return Pick(sport="nba", game_date="2025-01-15", market_family="spread", subject="LAL",
                side="home", model_prob=0.57, fair_prob=0.5, edge=0.07, confidence="medium",
                line=-3.5, odds_american=-110)


def test_score_card_is_feed_sized(tmp_path):
    p = render_score_card(_gp(), tmp_path)
    assert p.exists()
    assert Image.open(p).size == (1080, 1350)


def test_best_bet_card(tmp_path):
    p = render_best_bet_card(_pick(), tmp_path)
    assert p.exists() and Image.open(p).size == (1080, 1350)


def test_record_card(tmp_path):
    p = render_record_card({"record": "22-8", "units": 6.4, "win_pct": 0.733, "streak": 4, "n_picks": 30}, tmp_path)
    assert p.exists()


def test_caption_includes_compliance():
    c = caption_for_score(_gp()).lower()
    assert "not betting advice" in c and "21+" in c


def test_render_slate_writes_cards_and_captions(tmp_path):
    paths = render_slate(
        "2025-01-15", [_gp()], [_pick()],
        {"record": "22-8", "units": 6.4, "win_pct": 0.73, "streak": 4, "n_picks": 30},
        out_root=tmp_path,
    )
    assert len(paths) >= 3  # score + best bet + record
    assert (tmp_path / "2025-01-15" / "score_BOS_at_LAL.txt").exists()


# --- 3-way (soccer) + new-sport prop displays ---
def _soccer_gp():
    return GamePrediction(sport="soccer", game_date="2025-08-16", home="Arsenal", away="Chelsea",
                          mu_total=2.7, sigma_total=1.4, mu_margin=0.8, sigma_margin=1.3,
                          pred_home_pts=1.7, pred_away_pts=1.1,
                          p_home_win=0.52, p_draw=0.26, p_away_win=0.22)


def test_soccer_score_card_is_3way(tmp_path):
    # p_draw set -> render_score_card must delegate to the 3-way card and still be feed-sized
    p = render_score_card(_soccer_gp(), tmp_path)
    assert p.exists() and Image.open(p).size == (1080, 1350)


def test_soccer_caption_shows_all_three_outcomes():
    c = caption_for_score(_soccer_gp())
    assert "Home 52%" in c and "Draw 26%" in c and "Away 22%" in c
    assert "Arsenal to win" in c              # favored outcome named
    assert "not betting advice" in c.lower()  # compliance still present


def test_props_cards_render_for_mlb_and_nhl(tmp_path):
    from content.render import caption_for_props, render_props_card
    # MLB batter, MLB pitcher (K), NHL skater — each a valid feed PNG + sport-aware caption
    mlb_bat = render_props_card("Aaron Judge", {"hits": 1.4, "totalBases": 2.6, "homeRuns": 0.4},
                                tmp_path, "NYY vs BOS", sport="mlb")
    mlb_pit = render_props_card("Gerrit Cole", {"strikeouts": 6.8}, tmp_path, "NYY vs BOS", sport="mlb")
    nhl = render_props_card("Connor McDavid", {"points": 1.3, "shots": 3.6}, tmp_path, "EDM vs CGY", sport="nhl")
    for p in (mlb_bat, mlb_pit, nhl):
        assert p.exists() and Image.open(p).size == (1080, 1350)
    assert "K" in caption_for_props("Gerrit Cole", {"strikeouts": 6.8}, sport="mlb")
    assert "SOG" in caption_for_props("Connor McDavid", {"points": 1.3, "shots": 3.6}, sport="nhl")


def test_mlb_pitcher_slate_projections_ranks_and_filters(monkeypatch):
    # Hermetic: stub the model + schedule so no network/artifacts are touched.
    import pandas as pd

    import sports.mlb.data as mlb_data
    from models.mlb_pitcher_predictor import MLBPitcherPredictor

    pred = MLBPitcherPredictor.__new__(MLBPitcherPredictor)
    pred._blob = {"feature_cols": []}  # available() -> True
    ks = {101: 7.4, 102: 5.1, 103: 6.2, 104: 4.0}
    pred.predict = lambda pid, season=None: ks.get(int(pid))
    pred.pitcher_name = lambda pid: {101: "Ace One", 102: "Arm Two", 103: "Slinger", 104: "Junk"}[int(pid)]
    monkeypatch.setattr(mlb_data, "load_schedules", lambda years: pd.DataFrame([
        {"game_id": 1, "season": 2025, "game_date": "2025-08-09", "home": "NYY", "away": "BOS",
         "home_sp": 101, "away_sp": 102, "home_score": None, "away_score": None, "status": "S"},
        {"game_id": 2, "season": 2025, "game_date": "2025-08-09", "home": "LAD", "away": "SF",
         "home_sp": 103, "away_sp": 104, "home_score": None, "away_score": None, "status": "S"},
        {"game_id": 3, "season": 2025, "game_date": "2025-08-10", "home": "CHC", "away": "STL",
         "home_sp": 999, "away_sp": 998, "home_score": None, "away_score": None, "status": "S"},
    ]))
    games = [{"home": "NYY", "away": "BOS", "date": "2025-08-09"},
             {"home": "LAD", "away": "SF", "date": "2025-08-09"}]
    cards = pred.slate_projections(games, season="2025")
    got = [c["projections"]["strikeouts"] for c in cards]
    assert got == sorted(got, reverse=True)                 # ranked by K desc
    assert len(cards) == 4 and all(c["sport"] == "mlb" for c in cards)
    assert all(c["projections"].get("strikeouts") is not None for c in cards)
    names = [c["player_name"] for c in cards]
    assert "999" not in "".join(names)                      # off-date game excluded
