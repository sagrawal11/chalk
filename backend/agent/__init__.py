"""Scheduled Claude agent (NEW, 🟡/🔴 judgment). Wired in M5.

See docs/ARCHITECTURE.md §5j and docs/OPS_RUNBOOK.md §4–§5. Fires on cadence to finalize /
sanity-check drafted copy, run the judgment guardrail checks, decide post-worthiness,
and route anomalies to 🔴. In cautious mode (`AUTONOMY_MODE=approve_all`) it only
assembles the batch for owner approval; it posts nothing.
"""
