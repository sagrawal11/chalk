"""M4 publishing + guardrails. Hermetic (no network, no real platform APIs).

Everything runs in the DARK posture: dry-run publishing, tmp stores, env-flag
monkeypatching. Proves the guardrail gate, idempotency, the kill switch, the
autonomy tighten-switch, the queue, and copy-law-compliant drafting.
"""
import pytest

from config.settings import autonomy_mode
from content.copy import draft_caption
from publish.draft_queue import APPROVED, PENDING, Draft, DraftQueue
from publish.guardrails import _found, _TOUT, run_guardrails
from publish.publisher import PostStore, Publisher


def _draft(**over):
    base = dict(id="2026-08-23-exp-NFL-10", platform="reddit", kind="experiment_log",
                caption="Experiment log: Opponent-adjusted offense. Result: MARGIN MAE "
                        "10.73 → 10.70 (-0.03) over 23 seasons, kept. Next: EPA/play, "
                        "Expected Points Added per play, a cleaner efficiency read. A research project.",
                source={"before": 10.73, "after": 10.70, "delta": -0.03, "seasons": 23,
                        "next_desc": "Expected Points Added per play, a cleaner efficiency read."})
    base.update(over)
    return Draft(**base)


# --- guardrails ---
def test_clean_experiment_passes():
    assert run_guardrails(_draft()).gate == "pass"


def test_tout_language_blocks():
    d = _draft(caption="Lock of the day 🔒, hammer this. A research project.")
    rep = run_guardrails(d)
    assert rep.gate == "block"
    assert any(c.name == "tout_denylist" and c.status == "fail" for c in rep.checks)


def test_hallucinated_number_blocks():
    # 68.9% appears nowhere in the source record -> unsourced stat -> block.
    d = _draft(kind="score", source={"home_score": 27, "away_score": 24, "conf": 58},
               caption="The model's call: Bills to win, 27–24. Model confidence 68.9%. "
                       "Graded tomorrow. A research project. Not betting advice.")
    rep = run_guardrails(d)
    assert rep.gate == "block"
    assert any(c.name == "numbers_reconcile" and c.status == "fail" for c in rep.checks)


def test_sourced_numbers_pass():
    d = _draft(kind="score", source={"home_score": 27, "away_score": 24, "conf": 58},
               caption="The model's call: Bills to win, 27–24. Model confidence 58%. "
                       "Graded tomorrow, win or lose. A research project. Not betting advice.")
    assert run_guardrails(d).gate == "pass"


def test_missing_disclaimer_blocks():
    d = _draft(caption="Opponent-adjusted offense, kept. MARGIN MAE 10.73 → 10.70.")
    rep = run_guardrails(d)
    assert rep.gate == "block"
    assert any(c.name == "disclaimer" and c.status == "fail" for c in rep.checks)


def test_pick_card_requires_not_betting_advice():
    d = _draft(kind="score", source={"conf": 58},
               caption="The model's call: Bills, 58%. A research project.")  # missing "not betting advice"
    assert run_guardrails(d).gate == "block"


def test_tragedy_escalates():
    d = _draft(caption="Star QB carted off with a serious injury last night. A research project.")
    rep = run_guardrails(d)
    assert rep.gate == "escalate"
    assert any(c.name == "tragedy_screen" and c.status == "escalate" for c in rep.checks)


def test_retired_phrasing_holds():
    d = _draft(caption="Our market-blind model doesn't beat the market. A research project.")
    assert run_guardrails(d).gate == "escalate"   # soft flag -> hold for the human


# --- idempotency / kill switch ---
class _Dummy(Publisher):
    platform = "reddit"


def test_idempotent_no_double_post(tmp_path):
    store = PostStore(tmp_path / "posted.jsonl")
    d, pub = _draft(), _Dummy()
    r1 = pub.publish(d, dry_run=True, store=store)
    r2 = pub.publish(d, dry_run=True, store=store)
    assert r1 is not None and r1.dry_run
    assert r1.posted_at == r2.posted_at                # same stored ref, not re-created
    assert len(store._rows()) == 1                     # recorded exactly once


def test_kill_switch_halts(tmp_path, monkeypatch):
    monkeypatch.setenv("CHALK_KILL_SWITCH", "1")
    store = PostStore(tmp_path / "posted.jsonl")
    assert _Dummy().publish(_draft(), dry_run=True, store=store) is None
    assert store._rows() == []


# --- autonomy tighten-switch ---
def test_autonomy_defaults_to_approve_all(monkeypatch):
    monkeypatch.delenv("AUTONOMY_MODE", raising=False)
    assert autonomy_mode() == "approve_all"
    monkeypatch.setenv("AUTONOMY_MODE", "auto")
    assert autonomy_mode() == "auto"
    monkeypatch.setenv("AUTONOMY_MODE", "nonsense")    # invalid -> safe default
    assert autonomy_mode() == "approve_all"


# --- queue ---
def test_queue_enqueue_and_approve(tmp_path):
    q = DraftQueue(tmp_path / "drafts.json")
    q.enqueue(_draft())
    assert len(q.list(PENDING)) == 1
    q.approve("2026-08-23-exp-NFL-10", "reddit")
    assert q.get("2026-08-23-exp-NFL-10", "reddit").status == APPROVED


# --- copy drafting (template fallback; LLM disabled without a key) ---
def test_template_copy_is_compliant(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("CHALK_COPY_LLM", raising=False)
    cap = draft_caption("score", {"winner": "Buffalo Bills", "score": "27–24", "conf": 58})
    assert "a research project" in cap.lower() and "not betting advice" in cap.lower()
    assert not _found(_TOUT, cap)
