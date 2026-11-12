"""Track record: lock immutability + tamper detection, winner+score grading,
aggregation. Hermetic (tmp lock dir + ledger)."""
import json

import pandas as pd
import pytest

import track_record.grade as grade
import track_record.lock as lock
import pipeline.track_record as tr
from track_record.aggregate import headline, summarize
from predictions.schema import GamePrediction

GK = "nba:2025-01-15:BOS@LAL"


def _gp(date="2025-01-15", home="LAL", away="BOS", mu_margin=6.0,
        pred_home=115.0, pred_away=109.0):
    return GamePrediction(sport="nba", game_date=date, home=home, away=away,
                          mu_total=224.0, sigma_total=20.0, mu_margin=mu_margin,
                          sigma_margin=14.0, pred_home_pts=pred_home,
                          pred_away_pts=pred_away, p_home_win=0.66)


def test_lock_immutable_and_verifiable(tmp_path, monkeypatch):
    monkeypatch.setattr(lock, "LOCKED_DIR", tmp_path / "locked")
    p = lock.lock_predictions("nba", "2025-01-15", [_gp()])
    assert p.exists()
    assert lock.verify_lock("nba", "2025-01-15")
    with pytest.raises(FileExistsError):
        lock.lock_predictions("nba", "2025-01-15", [_gp()])  # immutable
    doc = lock.load_lock("nba", "2025-01-15")
    assert len(doc["game_predictions"]) == 1


def test_verify_detects_tampering(tmp_path, monkeypatch):
    monkeypatch.setattr(lock, "LOCKED_DIR", tmp_path / "locked")
    lock.lock_predictions("nba", "2025-01-15", [_gp()])
    path = lock.lock_path("nba", "2025-01-15")
    d = json.loads(path.read_text())
    d["game_predictions"][0]["mu_margin"] = 99.0  # tamper after the fact
    path.write_text(json.dumps(d))
    assert lock.verify_lock("nba", "2025-01-15") is False


def test_grade_winner_and_score(tmp_path, monkeypatch):
    monkeypatch.setattr(lock, "LOCKED_DIR", tmp_path / "locked")
    monkeypatch.setattr(grade, "RESULTS_LEDGER", tmp_path / "ledger.parquet")
    lock.lock_predictions("nba", "2025-01-15", [_gp()])
    res = grade.grade_date("nba", "2025-01-15", {GK: {"home_pts": 120, "away_pts": 110}})
    r = res.iloc[0]
    assert r["result"] == "win" and r["side"] == "home" and r["subject"] == "LAL"
    assert r["home_pts_err"] == pytest.approx(5.0)   # pred 115 vs 120
    assert r["away_pts_err"] == pytest.approx(1.0)   # pred 109 vs 110
    assert grade.append_ledger(res) == 1


def test_grade_tie_is_loss(tmp_path, monkeypatch):
    monkeypatch.setattr(lock, "LOCKED_DIR", tmp_path / "locked")
    lock.lock_predictions("nba", "2025-01-16", [_gp("2025-01-16")])
    res = grade.grade_date("nba", "2025-01-16",
                           {"nba:2025-01-16:BOS@LAL": {"home_pts": 110, "away_pts": 110}})
    assert res.iloc[0]["result"] == "loss"           # a tie beats neither side


def test_aggregate_headline_and_summary():
    df = pd.DataFrame([
        {"sport": "nba", "game_date": "2025-01-15", "home": "LAL", "away": "BOS",
         "subject": "LAL", "side": "home", "result": "win",
         "home_pts_err": 2.0, "away_pts_err": 3.0},
        {"sport": "nba", "game_date": "2025-01-16", "home": "MIA", "away": "NYK",
         "subject": "NYK", "side": "away", "result": "win",
         "home_pts_err": 1.0, "away_pts_err": 4.0},
        {"sport": "nba", "game_date": "2025-01-17", "home": "GSW", "away": "DEN",
         "subject": "GSW", "side": "home", "result": "loss",
         "home_pts_err": 6.0, "away_pts_err": 5.0},
    ])
    h = headline(df)
    assert h["record"] == "2-1"
    assert h["win_pct"] == pytest.approx(0.6667, abs=1e-3)
    assert h["streak"] == -1              # most recent (01-17) is a loss
    assert h["score_mae"] is not None
    assert not summarize(df, ["sport"]).empty


def _pp(slug="lebron_james", stat="PTS", mu=27.0):
    from predictions.schema import PlayerPropPrediction
    return PlayerPropPrediction(sport="nba", game_date="2025-01-15", player_slug=slug,
                                stat=stat, mu=mu, home="LAL", away="BOS")


def test_grade_props_mae_and_bias(tmp_path, monkeypatch):
    from track_record.aggregate import prop_headline
    monkeypatch.setattr(lock, "LOCKED_DIR", tmp_path / "locked")
    monkeypatch.setattr(grade, "PROP_RESULTS_LEDGER", tmp_path / "props.parquet")
    lock.lock_predictions("nba", "2025-01-15", [_gp()],
                          prop_predictions=[_pp("lebron_james", "PTS", 27.0),
                                            _pp("anthony_davis", "PTS", 22.0)])
    res = grade.grade_props_date("nba", "2025-01-15",
                                 {"lebron_james:PTS": 30.0, "anthony_davis:PTS": 18.0})
    assert len(res) == 2
    lebron = res[res["player_slug"] == "lebron_james"].iloc[0]
    assert lebron["abs_err"] == pytest.approx(3.0) and lebron["err"] == pytest.approx(-3.0)
    assert grade.append_prop_ledger(res) == 2
    h = prop_headline(res)                        # |27-30|=3, |22-18|=4 -> MAE 3.5
    assert h["n"] == 2 and h["mae"] == pytest.approx(3.5)
    assert h["by_stat"]["PTS"] == pytest.approx(3.5)


def test_grade_props_skips_unknown_actuals(tmp_path, monkeypatch):
    monkeypatch.setattr(lock, "LOCKED_DIR", tmp_path / "locked")
    lock.lock_predictions("nba", "2025-01-16", [_gp("2025-01-16")],
                          prop_predictions=[_pp("luka_doncic", "AST", 9.0)])
    assert grade.grade_props_date("nba", "2025-01-16", {}).empty


# --- live orchestrator (pipeline.track_record): the new lock->grade->report loop ---
def test_nhl_season_year_boundary():
    assert tr._nhl_season_year("2026-01-15") == 2025   # Jan -> prior season start
    assert tr._nhl_season_year("2025-11-12") == 2025   # Nov -> same year
    assert tr._nhl_season_year("2026-10-08") == 2026


def test_games_on_shapes_slate_and_finals(monkeypatch):
    """A played game is gradeable (final=True, scores present); a scheduled game is
    lockable but not gradeable (final=False, NaN scores)."""
    import sports.nhl.data as nhldata
    synth = pd.DataFrame({
        "game_id": [1, 2], "season": [2025, 2025],
        "game_date": ["2026-01-15", "2026-01-15"],
        "home": ["BOS", "NYR"], "away": ["SEA", "TBL"],
        "home_goals": [4, None], "away_goals": [2, None], "status": ["OFF", "FUT"],
    })
    monkeypatch.setattr(nhldata, "load_schedules", lambda years: synth)
    g = tr._games_on("nhl", "2026-01-15")
    assert list(g["final"]) == [True, False]
    assert g.loc[0, "home_pts"] == 4 and pd.isna(g.loc[1, "home_pts"])
    assert tr._games_on("basketballcricket", "2026-01-15") is None  # unwired -> skip


def test_lock_grade_roundtrip(tmp_path, monkeypatch):
    """cmd_lock predicts+locks a slate (matchup only), cmd_grade grades it vs finals.
    Both picks favor home (mu +2): the home-winning game is a win, the away-winning a loss."""
    monkeypatch.setattr(lock, "LOCKED_DIR", tmp_path / "locked")
    monkeypatch.setattr(grade, "RESULTS_LEDGER", tmp_path / "ledger.parquet")
    frame = pd.DataFrame({
        "home": ["LAL", "MIA"], "away": ["BOS", "NYK"],
        "home_pts": [4.0, 1.0], "away_pts": [2.0, 3.0], "final": [True, True],
    })
    monkeypatch.setattr(tr, "_games_on", lambda sport, date: frame)

    class _FakeSport:  # home always favored by mu_margin +2
        def predict_game(self, home, away, game_date):
            return GamePrediction(sport="nhl", game_date=game_date, home=home, away=away,
                                  mu_total=6.0, sigma_total=1.5, mu_margin=2.0,
                                  sigma_margin=1.5, pred_home_pts=4.0, pred_away_pts=2.0,
                                  p_home_win=0.6)
    monkeypatch.setattr(tr, "get_sport", lambda s: _FakeSport())

    assert tr.cmd_lock("nhl", "2026-01-15") == 2
    assert lock.lock_path("nhl", "2026-01-15").exists()
    assert tr.cmd_lock("nhl", "2026-01-15") == 0          # immutable: refuses re-lock
    assert tr.cmd_grade("nhl", "2026-01-15") == 2
    led = pd.read_parquet(tmp_path / "ledger.parquet")
    assert (led["result"] == "win").sum() == 1 and (led["result"] == "loss").sum() == 1
    assert grade.append_ledger(grade.grade_date("nhl", "2026-01-15", {})) == 0  # idempotent
