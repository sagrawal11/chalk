"""The scheduled Claude agent (ARCHITECTURE §5j, OPS_RUNBOOK §4) — the 🟡 judgment layer.

Fires on cadence AFTER the 🟢 pipeline has drafted + guardrailed + enqueued. In cautious
mode (AUTONOMY_MODE=approve_all, the default) it only ASSEMBLES the batch for the owner —
it posts NOTHING — and surfaces 🔴 escalations for a human. As the guardrails prove out,
a later phase (M7e) lets it auto-approve gated items within limits.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from config.settings import autonomy_mode
from publish.draft_queue import ESCALATED, PENDING, DraftQueue

logger = logging.getLogger(__name__)


def assemble_batch(queue: Optional[DraftQueue] = None) -> Dict[str, Any]:
    """Gather the day's gated drafts for the owner. Cautious mode never auto-posts."""
    q = queue or DraftQueue()
    for_approval = q.list(PENDING)      # passed guardrails, awaiting the owner
    escalated = q.list(ESCALATED)       # 🔴 / held — need a human
    return {
        "mode": autonomy_mode(),
        "auto_post": autonomy_mode() == "auto",   # False in cautious mode
        "for_approval": for_approval,
        "escalated": escalated,
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    b = assemble_batch()
    print(f"scheduled agent — mode={b['mode']} "
          f"({'auto-post gated items' if b['auto_post'] else 'cautious: assemble only, no auto-post'})")
    print(f"  {len(b['for_approval'])} draft(s) awaiting approval · {len(b['escalated'])} escalated 🔴")
    for d in b["for_approval"]:
        print(f"   ✅?  {d.id}:{d.platform} [{d.kind}] — {d.caption[:72]}…")
    for d in b["escalated"]:
        gate = (d.checks or {}).get("gate", "?")
        print(f"   🔴   {d.id}:{d.platform} — held ({gate})")


if __name__ == "__main__":
    main()
