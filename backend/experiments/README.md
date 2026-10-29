# `experiments/`: the feature-experiment harness (NEW)

**Milestone:** M2 (`docs/BUILD_PLAN.md`). **Design:** `docs/ARCHITECTURE.md` §5d.

The champion/challenger loop over the existing `backtest/team_backtest.py`
walk-forward eval, plus a public experiment ledger and an honest readout
on the untouched test set. The daily unit of content:
*add one feature → measure it walk-forward → record it → decide keep/drop → publish the delta.*

Lands here in M2:

- `roadmap.yaml`: machine-readable port of `docs/FEATURE_ROADMAP.md` (the prioritized
  queue: `{id, sport, rung, name, builder(s), hypothesis, eval_metric, act, keep_rule, status}`).
- `run_experiment.py`: assemble a challenger (champion's builders + this rung's
  builder) → run the walk-forward backtest for champion vs challenger on
  train+CV only → Δ metrics → apply the pre-registered keep-rule → append to
  the ledger regardless of outcome (duds are content) → promote if kept
  (version bump + refit).
- `honest_readout.py`: infrequent eval of the champion on the untouched final
  test set + the selected-vs-untouched overfitting gap. Never used for selection.
- `data/experiments_ledger.parquet`: one row per experiment (the progression story).

Guards baked in: pre-registered thresholds, a cumulative multiple-comparisons
counter, walk-forward OOS deltas only, and `MARKET_BLIND` enforced on the champion.
