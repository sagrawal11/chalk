"""M5 orchestration — hermetic (no data/network). Proves per-step isolation (a broken
step routes to 🔴 and the run continues), the dark posture (zero posts), and the
draft -> guardrail -> enqueue chain."""
import datetime as dt

from agent.daily_run import StepRunner, _Skip, _draft_and_enqueue, run_day

_RESULT = {
    "id": "NFL-10", "name": "Opponent-adjusted offense", "hypothesis": "Adjust for schedule.",
    "decision": "keep", "eval_window": "2002–2024",
    "champion_metrics": {"su_acc": 0.6249, "winner_logloss": 0.6451, "margin_mae": 10.73, "total_mae": 10.953},
    "challenger_metrics": {"su_acc": 0.6247, "winner_logloss": 0.6442, "margin_mae": 10.704, "total_mae": 10.933},
}


def test_steprunner_isolates_failures():
    R = StepRunner()
    assert R.run("ok", lambda: "v") == "v"
    def boom():
        raise RuntimeError("source down")
    assert R.run("boom", boom) is None                 # no crash
    R.run("skip", lambda: (_ for _ in ()).throw(_Skip("nothing")))
    assert [r["status"] for r in R.results] == ["ok", "red", "skip"]
    assert len(R.reds) == 1


def test_run_day_is_dark_and_survives_a_broken_source(tmp_path, monkeypatch):
    import agent.daily_run as dr
    import publish.draft_queue as dq
    monkeypatch.setattr(dr, "SUMMARY_PATH", tmp_path / "summary.json")
    monkeypatch.setattr(dq, "DRAFTS_PATH", tmp_path / "drafts.json")
    monkeypatch.delenv("AUTONOMY_MODE", raising=False)
    # Wed 2026-08-26 is not NFL-due -> experiment skips (no data needed); source breaks -> 🔴.
    s = run_day("nfl", dt.date(2026, 8, 26), persist=False, force_experiment=False, break_source=True)
    assert s["posts"] == 0
    assert s["red_count"] == 1
    steps = {x["step"]: x["status"] for x in s["steps"]}
    assert steps["refresh_data"] == "red"
    assert steps["run_experiment"] == "skip"
    assert steps["predict_lock_render"] == "skip"
    assert s["autonomy_mode"] == "approve_all"


def test_draft_and_enqueue_gates_clean_experiment(tmp_path, monkeypatch):
    import publish.draft_queue as dq
    monkeypatch.setattr(dq, "DRAFTS_PATH", tmp_path / "drafts.json")
    drafts = _draft_and_enqueue(_RESULT, dt.date(2026, 8, 23), "nfl")
    assert len(drafts) == 2                              # reddit + x
    assert {d.platform for d in drafts} == {"reddit", "x"}
    assert all(d.checks.get("gate") == "pass" for d in drafts)
    assert all(d.status == "pending" for d in drafts)
    assert len(dq.DraftQueue().list()) == 2             # persisted to the (tmp) queue
