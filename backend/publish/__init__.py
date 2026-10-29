"""Publishing layer + approval queue + guardrails (NEW, 🟡 Yellow). Wired in M4.

See docs/ARCHITECTURE.md §5h/§5i, docs/CONTENT_SPEC.md §5, docs/OPS_RUNBOOK.md §4. A `Publisher`
ABC (mirrors odds/OddsProvider) with reddit/x/ig adapters + idempotency; the draft
queue lives in `publish/queue/`; `guardrails.py` implements the eight pre-publish
checks. Everything lands DARK (`--dry-run` / `AUTONOMY_MODE=approve_all`) first.
"""
