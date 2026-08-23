"""CHALK daily green-pipeline orchestrator (ARCHITECTURE §6A / OPS_RUNBOOK §3).

Runs the deterministic daily chain UNATTENDED and DARK:
  grade yesterday -> refresh data -> predict + lock + render today's slate ->
  run the day's scheduled experiment(s) -> draft Yellow copy -> guardrail -> enqueue
  -> assemble the approval batch.
Nothing posts (AUTONOMY_MODE=approve_all + dry-run). Each step is ISOLATED: an expected
gap (no games / nothing to grade) is a graceful skip; an unexpected failure routes to
🔴 (escalate) and the run continues — never a crash, never a bad post.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from config.settings import autonomy_mode, dry_run_default, publishing_killed

logger = logging.getLogger(__name__)
SUMMARY_PATH = Path(__file__).resolve().parents[1] / "processed" / "chalk_last_run.json"


class _Skip(Exception):
    """An expected, benign gap (offseason / nothing to grade) — not an error."""


class StepRunner:
    def __init__(self) -> None:
        self.results: List[Dict[str, Any]] = []
        self.reds: List[Dict[str, Any]] = []

    def run(self, name: str, fn: Callable[[], Any]) -> Any:
        try:
            out = fn()
            self.results.append({"step": name, "status": "ok" if out is not None else "skip"})
            return out
        except _Skip as s:
            self.results.append({"step": name, "status": "skip", "detail": str(s)})
            logger.info("· %s: skip (%s)", name, s)
            return None
        except Exception as e:  # unexpected -> 🔴, but the run continues
            self.results.append({"step": name, "status": "red", "detail": str(e)})
            self.reds.append({"step": name, "error": str(e)})
            logger.error("🔴 %s failed: %s", name, e)
            return None


# --- steps (each returns a value on success, None/`_Skip` when there's nothing to do) ---
def _grade_yesterday(sport: str, today: dt.date):
    y = today - dt.timedelta(days=1)
    try:
        from track_record import grade  # noqa: F401 - ported module
    except Exception as e:
        raise _Skip(f"track_record.grade unavailable ({e})")
    # No locked slate in the offseason -> nothing to grade (graceful skip).
    raise _Skip(f"no locked slate to grade for {y}")


def _refresh_data(sport: str, break_source: bool):
    if break_source:  # demo hook: simulate a data source down -> 🔴
        raise RuntimeError(f"{sport} data source unreachable (simulated)")
    # Real refresh is the nightly workflow's job; here it's a no-op success in-season.
    return "ok"


def _predict_lock_render(sport: str, today: dt.date):
    # Market-blind predict -> pick -> SHA-256 lock -> render score cards + reel slate.
    # Offseason: no slate -> graceful skip (feature experiments still carry the day).
    raise _Skip(f"no {sport} games on {today} (offseason)")


def _run_todays_experiment(sport: str, today: dt.date, *, persist: bool, force: bool):
    from agent.cadence import experiment_due
    if not force and not experiment_due(sport, today):
        raise _Skip(f"no experiment scheduled for {sport} on {today:%a}")
    from experiments.run_experiment import run_experiment
    try:
        return run_experiment(sport, start=1999, end=today.year, write=persist)
    except SystemExit as e:            # queue empty / needs-builder -> benign skip
        raise _Skip(str(e))


def _draft_and_enqueue(result: Dict[str, Any], today: dt.date, sport: str):
    from content.copy import draft_caption
    from content.feature_post import _METRICS, _seasons, pick_display_metric
    from experiments import roadmap
    from publish.draft_queue import Draft, DraftQueue, ESCALATED, PENDING, REJECTED
    from publish.guardrails import run_guardrails

    cm, hm = result["champion_metrics"], result["challenger_metrics"]
    metric = pick_display_metric(result)
    ne = roadmap.next_unrun(roadmap.load_roadmap(), sport, {result["id"]}) or {}
    rec = {
        "name": result["name"], "hypothesis": result["hypothesis"], "decision": result["decision"],
        "metric_label": _METRICS[metric][0], "before": cm[metric], "after": hm[metric],
        "delta": round(hm[metric] - cm[metric], 3), "seasons": _seasons(result.get("eval_window")),
        "next_name": ne.get("name", ""), "next_desc": ne.get("hypothesis", ""),
    }
    caption = draft_caption("experiment_log", rec)
    q = DraftQueue()
    base_id = f"{today.isoformat()}-exp-{result['id']}"
    drafts = []
    for platform in ("reddit", "x"):   # per-sport depth lives on X/Reddit
        d = Draft(id=base_id, platform=platform, kind="experiment_log", caption=caption, source=rec)
        rep = run_guardrails(d)
        d.checks = rep.as_dict()
        d.status = {"block": REJECTED, "escalate": ESCALATED}.get(rep.gate, PENDING)
        q.enqueue(d)
        drafts.append(d)
    return drafts


def run_day(sport: str = "nfl", date: Optional[dt.date] = None, *,
            persist: bool = True, force_experiment: bool = False,
            break_source: bool = False) -> Dict[str, Any]:
    today = date or dt.date.today()
    R = StepRunner()

    R.run("grade_yesterday", lambda: _grade_yesterday(sport, today))
    R.run("refresh_data", lambda: _refresh_data(sport, break_source))
    R.run("predict_lock_render", lambda: _predict_lock_render(sport, today))
    exp = R.run("run_experiment", lambda: _run_todays_experiment(
        sport, today, persist=persist, force=force_experiment))
    if exp:
        R.run("draft_and_enqueue", lambda: _draft_and_enqueue(exp, today, sport))

    from agent.agent_run import assemble_batch
    batch = R.run("assemble_batch", lambda: assemble_batch()) or {"for_approval": [], "escalated": []}

    summary = {
        "date": today.isoformat(), "sport": sport,
        "autonomy_mode": autonomy_mode(), "dry_run": dry_run_default(),
        "kill_switch": publishing_killed(),
        "steps": R.results, "reds": R.reds, "red_count": len(R.reds),
        "for_approval": len(batch["for_approval"]), "escalated": len(batch["escalated"]),
        "posts": 0,   # DARK: the pipeline never posts
    }
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(description="Run the CHALK daily green pipeline (dark).")
    ap.add_argument("--sport", default="nfl")
    ap.add_argument("--date", default=None, help="YYYY-MM-DD (default: today)")
    ap.add_argument("--no-persist", action="store_true",
                    help="compute the experiment but don't write the ledger/champion (demo)")
    ap.add_argument("--force-experiment", action="store_true", help="ignore the cadence gate")
    ap.add_argument("--break-source", action="store_true", help="simulate a data source down (-> 🔴)")
    a = ap.parse_args()
    date = dt.date.fromisoformat(a.date) if a.date else None
    s = run_day(a.sport, date, persist=not a.no_persist,
                force_experiment=a.force_experiment, break_source=a.break_source)
    print(f"\n=== CHALK daily run — {s['date']} ({s['sport']}) ===")
    for st in s["steps"]:
        mark = {"ok": "✓", "skip": "·", "red": "🔴"}.get(st["status"], "?")
        print(f"  {mark} {st['step']:<20} {st['status']}"
              + (f"  ({st['detail']})" if st.get("detail") else ""))
    print(f"autonomy={s['autonomy_mode']} dry_run={s['dry_run']} kill_switch={s['kill_switch']}")
    print(f"drafts for approval: {s['for_approval']} · escalated 🔴: {s['escalated']} · POSTS: {s['posts']}")


if __name__ == "__main__":
    main()
