"""Daily content loop end-to-end (backend/pipeline/daily_content.py). Hermetic:
stub team predictor + manual odds + monkeypatched lock dir / ledger."""
import sys

import pandas as pd

import pipeline.daily_content as dc
import track_record.grade as grade
import track_record.lock as lock
from odds.providers.manual import ManualProvider
from pipeline.daily_content import outcomes_for_date, run_day
from predictions.schema import GamePrediction
from sports.base import available_sports


class _StubTP:
    def predict_game(self, home, away, game_date, season=None):
        return GamePrediction(sport="nba", game_date=game_date, home=home, away=away,
                              mu_total=224.0, sigma_total=20.0, mu_margin=6.0, sigma_margin=14.0,
                              pred_home_pts=115.0, pred_away_pts=109.0, p_home_win=0.66)


def _odds_csv(tmp):
    p = tmp / "odds.csv"
    pd.DataFrame([
        {"sport": "nba", "game_date": "2025-01-15", "market_family": "spread", "subject": "LAL",
         "side": "home", "line": -3.5, "odds_american": -110, "home": "LAL", "away": "BOS"},
        {"sport": "nba", "game_date": "2025-01-15", "market_family": "spread", "subject": "BOS",
         "side": "away", "line": 3.5, "odds_american": -110, "home": "LAL", "away": "BOS"},
    ]).to_csv(p, index=False)
    return p


def test_run_day_end_to_end(tmp_path, monkeypatch):
    monkeypatch.setattr(lock, "LOCKED_DIR", tmp_path / "locked")
    monkeypatch.setattr(grade, "RESULTS_LEDGER", tmp_path / "ledger.parquet")

    summary = run_day(
        "nba", "2025-01-15",
        games=[{"home": "LAL", "away": "BOS"}],
        team_predictor=_StubTP(),
        odds_provider=ManualProvider(_odds_csv(tmp_path)),
        out_root=tmp_path / "content",
    )
    assert summary["games"] == 1
    assert summary["picks"] >= 1                 # spread home is a value pick (+6 vs -3.5)
    assert summary["cards"] >= 2                 # score + best-bet (+ record)

    # immutable lock written and verifiable
    assert (tmp_path / "locked" / "nba" / "2025-01-15.json").exists()
    assert lock.verify_lock("nba", "2025-01-15")
    # a real content card was rendered
    assert (tmp_path / "content" / "2025-01-15" / "score_BOS_at_LAL.png").exists()


def test_outcomes_for_date_returns_dict():
    # Reads the real team parquet if present (returns {} if absent); must not error.
    out = outcomes_for_date("nba", "2025-01-15")
    assert isinstance(out, dict)


def test_outcomes_for_date_mlb(monkeypatch):
    """MLB grading keys off the StatsAPI schedule: only Final games on the date,
    keyed sport:date:away@home with home/away run totals."""
    import sports.mlb.data as mlb_data

    def fake(years):
        return pd.DataFrame([
            {"game_id": 1, "season": 2025, "game_date": "2025-07-04", "home": "NYY",
             "away": "BOS", "home_score": 5, "away_score": 3, "status": "Final"},
            {"game_id": 2, "season": 2025, "game_date": "2025-07-04", "home": "LAD",
             "away": "SFG", "home_score": 2, "away_score": 1, "status": "In Progress"},
            {"game_id": 3, "season": 2025, "game_date": "2025-07-05", "home": "CHC",
             "away": "STL", "home_score": 7, "away_score": 6, "status": "Final"},
        ])

    monkeypatch.setattr(mlb_data, "load_schedules", fake)
    out = outcomes_for_date("mlb", "2025-07-04")
    assert out == {"mlb:2025-07-04:BOS@NYY": {"home_pts": 5.0, "away_pts": 3.0}}


def test_outcomes_for_date_nhl(monkeypatch):
    """NHL grading keys off the NHL-API schedule: only OFF/FINAL games on the date,
    keyed with home/away goals."""
    import sports.nhl.data as nhl_data

    def fake(years):
        return pd.DataFrame([
            {"game_id": 1, "season": 2023, "game_date": "2024-01-15", "home": "TOR",
             "away": "BOS", "home_goals": 4, "away_goals": 2, "status": "OFF"},
            {"game_id": 2, "season": 2023, "game_date": "2024-01-15", "home": "EDM",
             "away": "CGY", "home_goals": 0, "away_goals": 0, "status": "FUT"},
        ])

    monkeypatch.setattr(nhl_data, "load_schedules", fake)
    out = outcomes_for_date("nhl", "2024-01-15")
    assert out == {"nhl:2024-01-15:BOS@TOR": {"home_pts": 4.0, "away_pts": 2.0}}


def test_outcomes_for_date_soccer(monkeypatch):
    """Soccer (EPL) grading keys off the football-data results cache: goals on the
    date, keyed sport:date:away@home with canonical team names."""
    import sports.soccer.team_features as sf

    def fake(seasons):
        return pd.DataFrame([
            {"season": "2024", "date": pd.Timestamp("2025-05-10"), "home": "Arsenal",
             "away": "Chelsea", "fthg": 2, "ftag": 1},
            {"season": "2024", "date": pd.Timestamp("2025-05-11"), "home": "Liverpool",
             "away": "Everton", "fthg": 3, "ftag": 0},   # different date -> excluded
        ])

    monkeypatch.setattr(sf, "build_epl_matches", fake)
    out = outcomes_for_date("soccer", "2025-05-10")
    assert out == {"soccer:2025-05-10:Chelsea@Arsenal": {"home_pts": 2.0, "away_pts": 1.0}}


def test_main_all_sports_iterates_every_sport(monkeypatch):
    """`--sport all` runs (and grades) every registered sport."""
    ran, graded = [], []
    monkeypatch.setattr(dc, "run_day", lambda sport, date, **k: ran.append(sport))
    monkeypatch.setattr(dc, "grade_previous_day", lambda sport, gd: graded.append(sport))
    monkeypatch.setattr(sys, "argv", ["daily_content.py", "--sport", "all",
                                      "--date", "2025-01-15", "--grade-date", "2025-01-14",
                                      "--no-render"])
    dc.main()
    assert sorted(ran) == available_sports()
    assert sorted(graded) == available_sports()


def test_main_all_sports_isolates_failure(monkeypatch):
    """One sport's feed/model failure must not abort the others."""
    ran = []

    def flaky(sport, date, **k):
        if sport == "mlb":
            raise RuntimeError("feed down")
        ran.append(sport)

    monkeypatch.setattr(dc, "run_day", flaky)
    monkeypatch.setattr(sys, "argv", ["daily_content.py", "--sport", "all", "--date", "2025-01-15"])
    dc.main()  # must not raise despite mlb blowing up
    assert set(ran) == set(available_sports()) - {"mlb"}
