# Archive: the original full-scope vision

These docs describe CHALK's original plan, before the simplification to a backend modeling core. They are kept for reference, not as the current direction.

The original scope had two things the project has since set aside:

- A "market-blind" betting hook: the model was framed as a control against the betting market, with market-anchored branches and Rung-8 CLV/line-movement probes. That framing and all betting infrastructure have been removed; the models now simply predict players and teams from their own features and are graded against the real result.
- An outward-facing publish layer: a React frontend, a Remotion reel, a content renderer, and an autonomy/guardrail posting pipeline. That work is deferred (not abandoned) while the models get good; the code lives on the `archive/outward-facing` branch.

Contents:

- `CHALK_MASTER_PLAN.md`: the original thesis, constitution, cadence, autonomy tiers, and path to launch.
- `BUILD_PLAN.md`: the Phase B milestone sequencing (M0 to M7) for the full experiment-and-publish loop.
- `CONTENT_SPEC.md`: the "Editorial Terminal" design system and content types for the reel and posts.
- `LAUNCH.md`: the original launch checklist.

For the current project, see the top-level `README.md` and the active docs in `docs/` (`FEATURE_ROADMAP.md`, `ARCHITECTURE.md`, `DATA_SOURCES.md`, `OPS_RUNBOOK.md`).
