# `publish/` — publishing, approval queue & guardrails (NEW)

**Milestone:** M4 (`docs/BUILD_PLAN.md`). **Design:** `docs/ARCHITECTURE.md` §5h/§5i,
`docs/CONTENT_SPEC.md` §5, `docs/OPS_RUNBOOK.md` §4–§5.

- **`Publisher` ABC** (mirrors `odds/OddsProvider`): `publish(platform, asset, text)
  -> PostRef`, `supports(platform)`, `MultiPublisher` fan-out. Adapters:
  `reddit.py` (PRAW), `x.py` (X API v2 + media; threads via reply-chain), `ig.py`
  (Graph API from a public R2 URL). IG runs **approve → post-manual** interim until
  Meta app-review clears; Reddit/X auto-publish.
- **`queue/`** — the draft store (`{id, platform, kind, asset_paths, caption/thread,
  checks[], status}`); idempotency keyed by draft id (never double-post); a global
  kill switch.
- **`guardrails.py`** — the eight automated pre-publish checks (`docs/CONTENT_SPEC.md`
  §5): tout denylist · retired-phrasing · **numbers reconcile to source** · disclaimer
  · NEXT-explains-the-stat · on-voice · **tragedy/injury → 🔴** · idempotency.

Everything ships **dark** (`--dry-run` / `AUTONOMY_MODE=approve_all`) before it can post.
