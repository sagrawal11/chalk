# `agent/` — the scheduled autonomy agent (NEW)

**Milestone:** M5 (`docs/BUILD_PLAN.md`). **Design:** `docs/ARCHITECTURE.md` §5j,
`docs/OPS_RUNBOOK.md` §4–§6.

The 🟡 judgment layer the deterministic 🟢 GitHub Actions pipeline hands off to:
finalize/tighten drafted copy, sanity-check the reel/cards against the numbers,
decide post-worthiness, and route anything uncertain or screen-flagged to 🔴.
Bounded by `AUTONOMY_MODE` (starts `approve_all` — assembles the batch for owner
approval, posts nothing). Runs via a scheduled remote agent / cron.
