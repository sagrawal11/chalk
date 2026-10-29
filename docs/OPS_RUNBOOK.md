# CHALK: Operational Runbook

How CHALK is run day to day: the nightly data+model pipeline, weekly retrain, calibration monitoring, recovery, health alerts, and storage. Companion to `docs/archive/CHALK_MASTER_PLAN.md` (the north star + Constitution), `FEATURE_ROADMAP.md` (the research plan), and `ARCHITECTURE.md` (the engineering blueprint). This doc doesn't restate those; it references them. Terminology (champion/challenger, the experiment ledger, the locked-slate track record) matches `ARCHITECTURE.md`.

---

## 1. Purpose & how to use

This runbook governs the operation of the modeling pipeline described in `ARCHITECTURE.md`. It answers "what fires when, what does it do when it breaks, and what does the owner actually touch." It doesn't cover what the model does (that's `FEATURE_ROADMAP.md` / `ARCHITECTURE.md`).

The pipeline is a deterministic GitHub Actions job: it refreshes data, grades yesterday's locked picks against real results, predicts today, locks the slate, and runs the day's scheduled experiment. No judgment, no human in the daily loop beyond a health glance; the owner sets the research direction and resolves failures.

Scope note: this runbook governs the modeling core of the `chalk` repo (`ARCHITECTURE.md` §3). It builds on the already-resilient daily/weekly CI (`.github/workflows/nightly_pipeline.yml`, `weekly_retrain.yml`, `pipeline/nightly.py`), extended, not rebuilt.

---

## 2. The daily rhythm

A normal day, end to end. All clock times are tunable, anchored to the existing `nightly_pipeline.yml` cron (`0 8 * * *`, 08:00 UTC, chosen to run after games finish). Times below are illustrative UTC.

| When (UTC) | Actor | What happens |
|---|---|---|
| ~08:00 | Pipeline | Nightly workflow fires: refresh data → grade yesterday → predict today → lock slate (SHA-256) before tip → run the day's scheduled experiment(s) → delta-upload to R2. (§3) |
| ~08:40 | Pipeline | Pipeline exits; writes `processed/nightly_last_run.json`; health summary + any failures pushed to the bot. (§6) |
| ~09:00 (Sun only) | Pipeline | Weekly heavy retrain fires after the daily refresh (`0 9 * * 0`). (§3) |
| Through the day | Games | Real results accrue. Nothing to do. |
| Next ~08:00 | Pipeline | Yesterday's locked picks are graded against finals into the track record at the top of the next run, closing the loop. |

One hard timing rule (from the Constitution + track-record discipline): the lock happens before tip, always. A pick that wasn't locked before tip is void, never back-dated (`ARCHITECTURE.md` §5f).

---

## 3. The automated pipeline

Deterministic. No judgment. Two GitHub Actions workflows (owner has Pro), extended from the existing CI per `ARCHITECTURE.md` §5j/§6-A.

### Daily job: `nightly_pipeline.yml` (extend), `0 8 * * *`
Runs on `ubuntu-latest`, Python 3.10, `config/requirements.txt` (the canonical Docker-3.10 env). The existing light path (download R2 bundle → `pipeline/nightly.py` refresh → warm cache → delta-upload) gains the experiment step. Ordered:

| # | Step | Maps to | Success looks like |
|---|---|---|---|
| 1 | Checkout + install + download training bundle from R2 | existing `download_full_training_bundle` | Bundle present locally |
| 2 | Refresh data (all active sports' free feeds) + warm Redis cache | `pipeline/nightly.py` | Each source fetched or gracefully skipped (retry pattern, `ARCHITECTURE.md` §5a) |
| 3 | Grade yesterday: settle locked picks vs finals | `track_record/grade.py` → `results_ledger.parquet` | Yesterday's locked slate graded against real results; winner + score scored per pick |
| 4 | Predict today per matchup → pick a winner + score | `daily_content.run_day` → `predict_game` | One `game_winner_picks` per game |
| 5 | Lock the slate (SHA-256) before tip | `track_record/lock.py` | Immutable hashed slate written for today |
| 6 | Run the day's scheduled experiment(s) per the cadence map | `experiments/run_experiment.py` over `roadmap.yaml` | Δ metrics computed on train+CV seasons; `experiments_ledger.parquet` appended regardless of outcome; champion promoted only if the pre-registered rule passes |
| 7 | Delta-upload artifacts to R2 | `utils/storage.py` | Updated ledgers, caches, and locked slate staged to R2 |
| 8 | Write run summary + notify | `processed/nightly_last_run.json` + bot | Exit 0; summary pushed; any failure routed |

Cadence (which sports experiment on which day) is config-driven per `docs/archive/CHALK_MASTER_PLAN.md` §7 / `ARCHITECTURE.md` §7: NFL/CFB roughly twice-weekly, NBA/NHL daily, MLB/soccer a few per week. Predictions/results are game-day-driven (no games → no predictions/results, but feature experiments can still run).

### Weekly job: `weekly_retrain.yml`, `0 9 * * 0` (Sundays, after the daily refresh)
The heavy path: `pipeline/nightly.py --rebuild-features --retrain-global --retrain-sports` (180-min timeout on a free 2-core runner). Rebuilds features + retrains every model; delta-uploads artifacts + per-sport caches to R2. Daily predictions use the most recent weekly models. Success = exit 0 + refreshed champion artifacts in R2. The owner confirms this ran each week (§8).

Artifacts to R2 (via `utils/storage.py`): training bundle, per-sport data caches, model artifacts (pinned per champion `model_version`), `experiments_ledger.parquet`, `results_ledger.parquet`, the locked slates.

What success means: workflow exits 0; `nightly_last_run.json` shows every stage `ok` (or an expected graceful skip, e.g. an off-season sport); today's slate locked before tip; yesterday graded. Any deviation is a failure (§5).

---

## 4. Anomalies & escalation

A failure halts the affected work and surfaces to the owner; the run continues for everything unaffected and still exits with a summary noting the failure count.

Trigger list:

| Trigger | Origin |
|---|---|
| Data source down / feed fetch failed past retries | pipeline step 2 |
| Unofficial API / scrape break (schema drift, endpoint moved) | pipeline (feeds wrapped with graceful skips) |
| Model won't train / regresses unexpectedly (champion metric drops beyond guard) | experiment/retrain steps |
| Implausible pick (out-of-range score, impossible prob, blank slate) | predict/pick step sanity check |

What happens on a failure: a failure alert with context (which trigger, the relevant numbers/logs, a suggested action) is pushed to the bot; the run continues for everything unaffected; the pipeline still exits with a summary noting the failure count.

How the owner resolves: fix the cause and re-trigger the workflow (`workflow_dispatch`), or wait for the next scheduled run (§5). A slate that never locked in time is simply void, never back-dated (Constitution honesty).

---

## 5. Failure modes & recovery

| Failure | Detected by | Automatic behavior | Owner action |
|---|---|---|---|
| Data feed down | Fetch retries exhausted (step 2) | Graceful skip for that source; if it blocks predictions for an active sport, flag a failure | If transient, re-run `workflow_dispatch`; else run that sport degraded / skip the day; note in summary |
| Unofficial API / scrape break (schema drift) | Parser error / empty result | Skip + flag a failure | Patch the adapter, push, re-run; the seam is isolated per sport (`ARCHITECTURE.md` §5a) |
| Model won't train / regresses | Trainer error, or champion metric drop beyond guard (step 6 / weekly) | Do not promote challenger; champion unchanged; flag a failure | Inspect `experiments_ledger`; if a real regression, keep prior champion + record the dud honestly (Constitution #1); fix + re-run |
| R2 upload fail | Storage step error | Retry via the delta-upload pool; if artifacts never staged, flag a failure | Verify R2 creds (§7); re-run the stage step |
| Missed day (runner outage, cron skipped) | No new `nightly_last_run.json`; track-record staleness (§6) | Next scheduled run grades whatever finished and proceeds; a slate never locked in time is simply void, never back-dated (Constitution honesty) | Acknowledge the gap; optionally `workflow_dispatch` a catch-up refresh/grade; do not fabricate a missed lock |

Recovery primitive: `workflow_dispatch` (manual re-trigger, both workflows have it).

---

## 6. Monitoring, health & alerts

What's watched:
- Pipeline exit status: GitHub Actions run result (both workflows).
- Per-run summary: `processed/nightly_last_run.json` (per-stage ok/skip/fail + counts: games predicted, slate locked, yesterday graded, experiments run/kept, failure count).
- Track-record freshness: is `results_ledger.parquet` grading current (did yesterday get graded)? Staleness is the canary for a missed day (§5).
- Champion-vs-untouched-test gap: the overfitting canary from `experiments/honest_readout.py` (`ARCHITECTURE.md` §5d); a widening gap is worth an alert.

Where alerts land: the Telegram/Slack bot, one channel for the daily health summary and failure escalations. One surface, on the phone.

Simple daily health check (owner, ~30 sec): open the bot summary → confirm clean exit + slate locked + yesterday graded + failure count is 0 (or expected). If the summary didn't arrive at all → treat as a missed day (§5). Weekly, also confirm the retrain (§8).

---

## 7. Secrets & rotation

Where keys live: GitHub Actions encrypted secrets (`ARCHITECTURE.md` §5k; `docs/archive/CHALK_MASTER_PLAN.md` §9.2). Locally: R2 is emulated by MinIO. No secrets in the repo, ever.

Inventory (extends the secrets already wired in the workflows: `KAGGLE_USERNAME`, `KAGGLE_KEY`, `UPSTASH_REDIS_URL`, `R2_ACCOUNT_ID`/`R2_ACCESS_KEY_ID`/`R2_SECRET_ACCESS_KEY`/`R2_BUCKET_NAME`):

| Secret(s) | Use | Rotation |
|---|---|---|
| `CFBD_API_KEY` | CFB data (CFBD) | On leak; watch free-tier limits (maybe ~$10/mo Patreon at scale, `docs/archive/CHALK_MASTER_PLAN.md` §7) |
| R2 creds (4) | Artifact + data-bundle storage | Periodic; on leak |
| Kaggle (`KAGGLE_USERNAME`/`KAGGLE_KEY`) | NBA backfill feed | On leak (note the KGAT-auth quirk in nightly CI) |
| `UPSTASH_REDIS_URL` | Prediction cache | On leak |
| Telegram/Slack bot token | Health + failure alerts | On leak |

Least-privilege notes: R2 keys scoped to the one CHALK bucket. Prefer short-lived/refresh flows where a provider offers them.

---

## 8. The owner's weekly cadence

The short recurring human list (everything else is automated):

- Daily (~30 sec): glance at the bot health summary. Clean exit? Slate locked? Yesterday graded? Failure count 0? (§6)
- Resolve failures: work any escalations from the bot (fix-upstream-and-re-run). (§4)
- Confirm the weekly retrain: after Sunday's `weekly_retrain.yml`, confirm it exited 0 and refreshed champion artifacts. (§3)
- Glance at the record: eyeball the track record + the experiment ledger/changelog. Is the story honest and current? Any dud that needs its paired "next move" (Constitution #1)? (`ARCHITECTURE.md` §5l)

---

## Open items

- Exact clock times: the daily cron (currently 08:00 UTC) and the weekly retrain window (§2).
- Champion-regression guard: the exact Δ threshold that trips a retrain/experiment failure (ties to the pre-registered keep/drop rules in `roadmap.yaml`, `ARCHITECTURE.md` §9).
- Alert surface: the concrete Telegram/Slack bot wiring for the health summary + failure escalations (§6).
- Missed-day catch-up policy: auto-catch-up vs. owner-triggered `workflow_dispatch` (§5).
