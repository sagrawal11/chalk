# CHALK: Operational Runbook (Green / Yellow / Red)

How CHALK is run day to day: the automated pipeline, the draft-to-approve loop, escalation, calibration, recovery, monitoring, and the tighten-back switch. Companion to `CHALK_MASTER_PLAN.md` (the north star + Constitution + tiered autonomy), `FEATURE_ROADMAP.md` (the research plan), `ARCHITECTURE.md` (the engineering blueprint), and `CONTENT_SPEC.md` (post templates + the §5 guardrail-check spec). This doc doesn't restate those; it references them. Terminology (🟢/🟡/🔴, `AUTONOMY_MODE`, champion/challenger, the Yellow queue, the `Publisher` seam) matches `ARCHITECTURE.md`.

---

## 1. Purpose & how to use

This runbook governs the operation of the semi-autonomous system described in `CHALK_MASTER_PLAN.md` §9 (Tiered Autonomy) and `ARCHITECTURE.md` §5j. It answers "what fires when, what does it do when it breaks, and what does the human actually touch." It doesn't cover what to post (that's `CONTENT_SPEC.md`) or what the model does (that's `FEATURE_ROADMAP.md` / `ARCHITECTURE.md`).

The machine vs. the owner, the whole split in one table:

| Tier | Who | Judgment? | Can post? |
|---|---|---|---|
| 🟢 Green | GitHub Actions (deterministic pipeline) | No | Never posts, only produces + stages |
| 🟡 Yellow | Scheduled Claude agent + guardrail checks; owner approves per `AUTONOMY_MODE` | Yes (bounded) | Yes, once gated + (per mode) approved |
| 🔴 Red | Owner | Human only | Never auto-posts; halted until owner resolves |

The owner is the creative director who sets the rules once (voice, Constitution, roadmap, what's post-worthy) and then clears batches and resolves 🔴s. Everything green is autonomous; everything red stops for a human; yellow is the loosening dial (§6). The direction is locked, not on autopilot; only execution is automated (`CHALK_MASTER_PLAN.md` §9).

Scope note: this runbook governs the target public `chalk` repo (`ARCHITECTURE.md` §3). It builds on the already-resilient daily/weekly CI in the playground (`.github/workflows/nightly_pipeline.yml`, `weekly_retrain.yml`, `pipeline/nightly.py`), extended, not rebuilt.

---

## 2. The daily rhythm

A normal day, end to end. All clock times are tunable, anchored to the existing `nightly_pipeline.yml` cron (`0 8 * * *`, 08:00 UTC, chosen to run after games finish). Times below are illustrative UTC; the owner-facing windows should be set to the owner's timezone + posting-strategy per `CONTENT_SPEC.md` §4.

| When (UTC) | Actor | What happens |
|---|---|---|
| ~08:00 | 🟢 Green | Nightly workflow fires: refresh data → grade yesterday → predict today → lock slate (SHA-256) before tip → render cards + reel → run the day's scheduled experiment(s) → draft 🟡 copy → stage assets to R2 → enqueue drafts. (§3) |
| ~08:40 | 🟢 Green | Pipeline exits; writes `processed/nightly_last_run.json`; health summary + any 🔴s pushed to the bot. (§9) |
| ~09:00 (Sun only) | 🟢 Green | Weekly heavy retrain fires after the daily refresh (`0 9 * * 0`). (§3) |
| ~09:00–11:00 | 🟡 Agent | Scheduled Claude agent wakes: finalizes/sanity-checks drafted copy, runs the judgment guardrail checks, decides post-worthiness, routes 🔴s. Assembles the day's batch. (§4) |
| Morning window (tunable) | Owner / mode | The approval window. Per `AUTONOMY_MODE`: `approve_all` → every 🟡 waits; `batch` → owner clears the one daily batch; `auto` → gated items already posting, owner spot-checks. (§4, §6) |
| Posting windows (tunable, per-platform) | 🟡 Publisher | Approved items publish: Reddit (PRAW) + X (API v2) auto; IG interim = approve then post manually until Meta app-review clears (`ARCHITECTURE.md` §5i). Predictions reel + score cards must post before first tip (the slate is already locked). |
| Through the day | Games | Real results accrue. Nothing to do. |
| Next ~08:00 | 🟢 Green | Yesterday's locked picks are graded into the track record at the top of the next run, closing the loop. |

Two hard timing rules (from the Constitution + track-record discipline):
- The lock happens before tip, always. A pick that wasn't locked before tip is void, never back-dated (`ARCHITECTURE.md` §5f).
- Predictions post before tip; results post after finals. No pick is published after the game has started.

---

## 3. 🟢 Green: the automated pipeline

Deterministic. No judgment, never posts. Two GitHub Actions workflows (owner has Pro), extended from the existing playground CI per `ARCHITECTURE.md` §5j/§6-A.

### Daily job: `nightly_pipeline.yml` (extend), `0 8 * * *`
Runs on `ubuntu-latest`, Python 3.10, `config/requirements.txt` (the canonical Docker-3.10 env; not the checked-in `betting_venv`). The existing light path (download R2 bundle → `pipeline/nightly.py` refresh → warm cache → delta-upload) gains the CHALK content + experiment steps. Ordered:

| # | Step | Maps to | Success looks like |
|---|---|---|---|
| 1 | Checkout + install + download training bundle from R2 | existing `download_full_training_bundle` | Bundle present locally |
| 2 | Refresh data (all active sports' free feeds) + warm Redis cache | `pipeline/nightly.py` | Each source fetched or gracefully skipped (retry pattern, `ARCHITECTURE.md` §5a) |
| 3 | Grade yesterday: settle locked picks vs finals | `track_record/grade.py` → `results_ledger.parquet` | Yesterday's locked slate graded; unpriced picks → `units=NaN` (never fabricated) |
| 4 | Predict today (market-blind) per matchup → pick a winner+score | `daily_content.run_day` → `predict_game` + `picks/best_bet.py` | One `game_winner_picks` per game; `MARKET_BLIND=True` |
| 5 | Lock the slate (SHA-256) before tip | `track_record/lock.py` | Immutable hashed slate written for today |
| 6 | Render score cards + write reel slate JSON + invoke `render-reel.mjs` | `content/` + wired `reel/` (fixes the standalone-reel discrepancy, `ARCHITECTURE.md` §8) | PNGs + one combined daily MP4 produced |
| 7 | Run the day's scheduled experiment(s) per the cadence map | `experiments/run_experiment.py` over `roadmap.yaml` | Δ metrics computed on train+CV seasons; `experiments_ledger.parquet` appended regardless of outcome; champion promoted only if the pre-registered rule passes |
| 8 | Draft 🟡 copy from the structured records (LLM) | `content/copy.py` | Captions/threads drafted from structured data only (never free-form) |
| 9 | Stage assets to R2 (public URLs for IG) | `utils/storage.py` delta-upload | Assets at public R2 URLs; ready for the Publisher |
| 10 | Enqueue drafts into the Yellow queue | `publish/queue/` | Pending drafts with `checks[]` attached; hand-off to §4 |
| 11 | Write run summary + notify | `processed/nightly_last_run.json` + bot | Exit 0; summary pushed; any 🔴 routed |

Cadence (which sports experiment on which day) is config-driven per `CHALK_MASTER_PLAN.md` §7 / `ARCHITECTURE.md` §7: NFL/CFB roughly twice-weekly, NBA/NHL daily, MLB/soccer a few per week. Predictions/results are game-day-driven (no games → no predictions/results, but feature-experiment content can still run).

### Weekly job: `weekly_retrain.yml`, `0 9 * * 0` (Sundays, after the daily refresh)
The heavy path: `pipeline/nightly.py --rebuild-features --retrain-global --retrain-sports` (180-min timeout on a free 2-core runner). Rebuilds features + retrains every model; delta-uploads artifacts + per-sport caches to R2. Daily predictions use the most recent weekly models. Success = exit 0 + refreshed champion artifacts in R2. The owner confirms this ran each week (§12).

Artifacts to R2 (via `utils/storage.py`): training bundle, per-sport data caches, model artifacts (pinned per champion `model_version`), rendered cards/reel MP4 (public URLs), `experiments_ledger.parquet`, `results_ledger.parquet`, the locked slates.

What "green success" means: workflow exits 0; `nightly_last_run.json` shows every stage `ok` (or an expected graceful skip, e.g. an off-season sport); today's slate locked before tip; yesterday graded; drafts enqueued with checks attached. Any deviation → 🔴 (§5).

---

## 4. 🟡 Yellow: the draft→approve workflow

This is where copy meets a human-or-agent gate. The pipeline (§3) drafts and enqueues; the scheduled Claude agent (`ARCHITECTURE.md` §5j) does the judgment; the owner approves per `AUTONOMY_MODE`.

How a draft is made: `content/copy.py` LLM-drafts captions/threads from structured experiment / prediction / result records only (never free-form invention), applying the voice + copy laws in `CONTENT_SPEC.md` §1.

The guardrail-check gate: every draft is gated by the 8 automated checks in `CONTENT_SPEC.md` §5 (= `ARCHITECTURE.md` §5h/§9.1) before it can post or enter the batch:
1. Tout denylist · 2. Retired-phrasing/stamp check · 3. Numbers reconcile with source data (no hallucinated stats) · 4. Disclaimer/footer present · 5. NEXT-explains-the-stat (experiment posts) · 6. On-voice · 7. Tragedy/serious-injury screen → any hit routes to 🔴 · 8. Idempotency (store post URL).
A hard fail on 1/3/4/7 blocks the item. A soft/ambiguous result → 🔴 (hold for the human, Constitution #4).

The scheduled agent's job (bounded judgment): finalize/tighten the gated copy, sanity-check the reel + card against the numbers, decide post-worthiness ("is this clearly worth posting?"), and route anything uncertain or screen-flagged to 🔴. In `approve_all` it just assembles the batch; as guardrails prove out it can auto-approve within limits (§6, §7).

Approval mechanism (recommended): a Telegram/Slack bot (approve from phone; `CHALK_MASTER_PLAN.md` §13, `ARCHITECTURE.md` §5h, `CONTENT_SPEC.md` §7 all carry this as the recommendation over a web dashboard). Per item the owner sees:
- the rendered asset (card/carousel/reel thumbnail) pulled from its public R2 URL,
- the final drafted copy,
- a compact check summary (which of the 8 passed/flagged) + the source numbers it reconciled against,
- the target platform(s) + kind,
- buttons: ✅ approve · ✏️ edit · ❌ reject (and for 🔴: acknowledge / override / hold).

Batching per `AUTONOMY_MODE`:
- `approve_all` → each gated 🟡 item is DMed individually and waits (the calibration default, weeks 1–4).
- `batch` → gated items collect into one once-daily batch; nothing posts until the owner clears it; the owner taps through ✅/✏️/❌ in one sitting.
- `auto` → gated items auto-post in their posting window; the owner gets a spot-check digest after the fact.

In every mode: failed-guardrail and 🔴 items never auto-post and always surface to the owner. IG items in the interim always require the manual post step regardless of mode (`ARCHITECTURE.md` §5i).

---

## 5. 🔴 Red: anomalies & escalation

🔴 = halt the affected item + escalate to the owner; never auto-post. 🔴 fires in every `AUTONOMY_MODE` (the ladder never suppresses it, see §6). A 🔴 halts only the item(s) it touches; unrelated healthy items proceed under the current mode.

Trigger list (any one → 🔴):

| Trigger | Origin |
|---|---|
| Data source down / feed fetch failed past retries | 🟢 pipeline step 2 |
| Unofficial API / scrape break (schema drift, endpoint moved) | 🟢 pipeline (feeds wrapped with graceful skips) |
| Model won't train / regresses unexpectedly (champion metric drops beyond guard) | 🟢 experiment/retrain steps |
| Implausible pick (out-of-range score, impossible prob, blank slate) | 🟢 predict/pick step sanity check |
| Hallucinated-number check fail (copy number ≠ source data) | 🟡 guardrail #3 |
| Tragedy / serious-injury screen hit | 🟡 guardrail #7 (Constitution #5, absolute hard rule) |
| Publish auth failure / API error / rate-limit exhausted | 🟡 `Publisher` adapter |
| Guardrail ambiguity / low-confidence post-worthiness | 🟡 agent (Constitution #4: when in doubt, hold) |

What happens on 🔴: the item is marked halted in the Yellow queue (not posted, not deleted); a 🔴 alert with context (which trigger, which item, the relevant numbers/logs, a suggested action) is pushed to the bot; the run continues for everything unaffected; the pipeline still exits with a summary noting the 🔴 count.

How the owner resolves / overrides (from the bot):
- Approve/override: if the owner judges it safe (e.g. a benign check flag), approve it through the normal ✅ path.
- Edit: fix the copy (✏️) and re-run the checks.
- Hold / drop: leave it halted or reject it (e.g. tragedy screen, usually drop; per Constitution #5 the safe default is hold+escalate, and if the slate is dominated by such an event, hold the whole slate).
- Fix upstream + re-run: for pipeline 🔴s (data/model), fix the cause and re-trigger the workflow (`workflow_dispatch`) or wait for the next scheduled run (§8).
- Kill switch: for anything systemic, flip the global kill switch (§11) to stop all publishing.

---

## 6. Autonomy modes & the tighten-back switch

The `AUTONOMY_MODE` ladder (`ARCHITECTURE.md` §5h). It only ever loosens the 🟡 tier; 🟢 always runs free, 🔴 always escalates, in every mode. The owner can snap back to `approve_all` at any time (see below).

| Mode | What auto-posts | What waits | When to use |
|---|---|---|---|
| `approve_all` | Nothing. Every 🟡 item DMed individually. | Every gated 🟡 item. | Default, weeks 1–4 calibration; and any time the owner wants full control (§7). |
| `batch` | Nothing until cleared; gated items collect into one daily batch the owner clears in a sitting. | The whole batch until the owner taps through it. | After voice + guardrails are calibrated but the owner still wants eyes on everything before it ships. |
| `auto` | Gated 🟡 items auto-post in their windows; owner gets a spot-check digest. | Only guardrail-failures + 🔴s. | After the checks have proven out on real output (§7); steady-state. |

The single tighten-back switch: set `AUTONOMY_MODE = approve_all` (a config/flag + repo secret/variable read by the pipeline and the agent). One setting reverts everything to full human approval, effective on the next run. IG stays manual-post regardless. (This is the "single switch" promised in `CHALK_MASTER_PLAN.md` §10.)

---

## 7. Calibration (weeks 1–4) → loosen

Posture (`CHALK_MASTER_PLAN.md` §10): ship careful, loosen deliberately. It's much easier than clawing back trust. Start in `approve_all`; loosen only when the guardrails have proven out on real output.

Weeks 1–4 process (`approve_all`):
- The owner approves/edits every 🟡 item and logs why on each edit/reject (the source of the growing voice guide; `CONTENT_SPEC.md` §7 notes it "grows during the cautious calibration weeks").
- Track, per item: guardrail verdict vs. owner verdict. Log every case where a check passed but the owner edited/rejected (a false-negative for the guardrails) and every case a check flagged something the owner approved (a false-positive).
- Watch: tout-language slips, number-reconciliation misses, off-voice drift, tragedy-screen accuracy, any near-miss on the Constitution.

Loosening criteria (sensible defaults, tune with the owner):

| Move | Gate to clear |
|---|---|
| `approve_all` → `batch` | ≥ ~2 weeks in `approve_all`; zero hard-guardrail escapes (tout/number/disclaimer/tragedy) reaching the owner as edits; owner-edit rate on gated copy trending low (e.g. < ~20%); no Constitution near-miss in the trailing week. |
| `batch` → `auto` | ≥ ~2 further weeks in `batch`; owner clears batches with near-zero substantive edits (e.g. < ~5%); the tragedy/serious-injury screen has never produced a false-negative; idempotency + publish path clean (no double-posts, no unresolved auth 🔴s). |

Loosen one tier at a time, one platform-comfortable at a time if desired, and only forward when the trailing window is clean. Any regression → snap back to `approve_all` (§6) and re-tune.

---

## 8. Failure modes & recovery

| Failure | Detected by | Automatic behavior | Owner action |
|---|---|---|---|
| Data feed down | Fetch retries exhausted (step 2) | Graceful skip for that source; if it blocks predictions for an active sport → 🔴 | If transient, re-run `workflow_dispatch`; else run that sport degraded / skip the day; note in summary |
| Unofficial API / scrape break (schema drift) | Parser error / empty result | Skip + 🔴 | Patch the adapter (playground first if useful), push, re-run; the seam is isolated per sport (`ARCHITECTURE.md` §5a) |
| Model won't train / regresses | Trainer error, or champion metric drop beyond guard (step 7 / weekly) | Do not promote challenger; champion unchanged; 🔴 | Inspect `experiments_ledger`; if a real regression, keep prior champion + record the dud honestly (it's content, Constitution #1); fix + re-run |
| Render / reel fail | Non-zero from `render-reel.mjs` / renderer; missing PNG/MP4 | That content item can't enqueue → 🔴; text-only picks/track record unaffected | Re-render; check slate JSON contract + vendored fonts (`CONTENT_SPEC.md` §6); re-run |
| R2 upload fail | Storage step error / missing public URL | Retry via the delta-upload pool; if assets never staged, IG/publish for those items → 🔴 (no public URL) | Verify R2 creds (§10); re-run the stage step |
| Publish API error / rate-limit | `Publisher` adapter (429/5xx/auth) | Per-platform backoff + retry; on exhaustion → 🔴, item stays `approved` un-posted (idempotency prevents dupes) | Retry after cooldown; if quota, defer to next window |
| IG long-lived token expired (~60-day) | IG Graph publish auth fail | IG item → 🔴 (and IG is manual-interim anyway) | Refresh the long-lived token and update the secret (§10); re-post manually |
| LLM-draft outage | `content/copy.py` API error | No drafts enqueued → 🔴 (nothing silently posts) | Retry; if provider down, either post nothing that cycle or hand-write copy through the approval path; picks stay locked + graded regardless |
| Missed day (runner outage, cron skipped) | No new `nightly_last_run.json`; track-record staleness (§9) | Next scheduled run grades whatever finished and proceeds; a slate never locked in time is simply void, never back-dated (Constitution honesty) | Acknowledge the gap; optionally `workflow_dispatch` a catch-up refresh/grade; do not fabricate a missed lock |

Recovery primitives: `workflow_dispatch` (manual re-trigger, both workflows have it), the `--dry-run` publish path (`ARCHITECTURE.md` §5i), idempotency keys (never double-post), and the global kill switch (§11).

---

## 9. Monitoring, health & alerts

What's watched:
- Pipeline exit status: GitHub Actions run result (both workflows).
- Per-run summary: `processed/nightly_last_run.json` (per-stage ok/skip/fail + counts: games predicted, slate locked, yesterday graded, experiments run/kept, drafts enqueued, 🔴 count).
- Track-record freshness: is `results_ledger.parquet` grading current (did yesterday get graded)? Staleness is the canary for a missed day (§8).
- Post success: stored `PostRef` per approved item (idempotency store); an `approved` item with no `PostRef` past its window = a publish problem.
- Champion-vs-untouched-test gap: the overfitting canary from `experiments/honest_readout.py` (`ARCHITECTURE.md` §5d); a widening gap is a (postable) signal, occasionally worth an alert.

Where alerts land: the Telegram/Slack bot, one channel for (a) the daily green health summary, (b) 🟡 approvals/batches, (c) 🔴 escalations. One surface, on the phone.

Simple daily health check (owner, ~30 sec): open the bot summary → confirm green exit + slate locked + yesterday graded + 🔴 count is 0 (or expected). If the summary didn't arrive at all → treat as a missed day (§8). Weekly, also confirm the retrain (§12).

---

## 10. Secrets & rotation

Where keys live: GitHub Actions encrypted secrets (`ARCHITECTURE.md` §5k; `CHALK_MASTER_PLAN.md` §9.2). Locally: R2 is emulated by MinIO. No secrets in the repo, ever.

Inventory (extends the secrets already wired in the workflows: `KAGGLE_USERNAME`, `KAGGLE_KEY`, `ODDS_API_KEY`, `UPSTASH_REDIS_URL`, `R2_ACCOUNT_ID`/`R2_ACCESS_KEY_ID`/`R2_SECRET_ACCESS_KEY`/`R2_BUCKET_NAME`):

| Secret(s) | Use | Rotation |
|---|---|---|
| `CFBD_API_KEY` | CFB data (CFBD) | On leak; watch free-tier limits (maybe ~$10/mo Patreon at scale, `CHALK_MASTER_PLAN.md` §7) |
| `ODDS_API_KEY` | Free odds snapshot for grading only (never a model input) | On leak |
| R2 creds (4) | Artifact/asset storage + public IG URLs | Periodic; on leak |
| Kaggle (`KAGGLE_USERNAME`/`KAGGLE_KEY`) | NBA backfill feed | On leak (note the KGAT-auth quirk in nightly CI) |
| `UPSTASH_REDIS_URL` | Prediction cache | On leak |
| X (consumer + access) | X API v2 publish | On leak / app policy change |
| Reddit (client + secret + refresh) | PRAW publish | Refresh token as Reddit requires; on leak |
| IG (app id + secret + long-lived token) | IG Graph publish | Long-lived token ~every 60 days; the one scheduled rotation that will bite (§8 IG-token row). Track its expiry; refresh before it lapses. |
| LLM API key | `content/copy.py` drafting | On leak |
| Telegram/Slack bot token | Approvals + alerts + health | On leak |

Least-privilege notes: scope each platform token to post + read-own only (no DM/admin scopes beyond what publishing needs); R2 keys scoped to the one CHALK bucket; the ODDS key is grading-only by design (reinforces market-blind). Prefer short-lived/refresh flows where the platform offers them. The IG ~60-day token is the standing rotation reminder; put it on the owner's weekly glance (§12) so it never silently expires.

---

## 11. Incident / public-correction protocol

Governs the case where something wrong or off-Constitution actually posted. Constitution #6: corrections are public and prompt; never quiet-delete-and-pretend (`CHALK_MASTER_PLAN.md` §3).

Steps:
1. Contain: flip the global kill switch (halts all `Publisher` posting; set `AUTONOMY_MODE=approve_all` too so nothing new ships while you sort it). The kill switch is a config flag both the pipeline and agent honor.
2. Assess: what posted, on which platforms, is it a factual error (wrong number/pick) or a Constitution breach (tout language, a tragedy/injury slip)?
3. Correct in the open: per Constitution #6, edit the reel / card to the corrected version and add a pinned correction comment stating what was wrong and the fix. Never delete-and-pretend. A visible correction is on-brand; a hidden one is the opposite of the brand.
4. Tragedy/injury breach: remove the offending framing, post a straight correction/acknowledgement, and treat it as a top-severity guardrail miss (feed it into calibration §7; tighten the screen).
5. Root-cause: which guardrail (`CONTENT_SPEC.md` §5) should have caught it? Log it as a false-negative, patch the check, add a regression case before re-opening the gate.
6. Resume: clear the kill switch and step the mode back only to `approve_all` first; re-earn `batch`/`auto` per §7.

Who flips the kill switch: the owner, from the bot. The scheduled agent can auto-engage it defensively on a systemic 🔴 (e.g. mass publish-auth failure or a tragedy-screen storm) and notify; but only the owner clears it.

---

## 12. The owner's weekly cadence

The short recurring human list (everything else is 🟢 or agent-handled):

- Daily (~30 sec): glance at the bot health summary. Green exit? Slate locked? Yesterday graded? 🔴 count 0? (§9)
- Approve: clear the daily batch (in `batch`) or approve individual 🟡 items (in `approve_all`); in `auto`, skim the spot-check digest. (§4)
- Resolve 🔴s: work any escalations from the bot (approve/edit/hold/drop or fix-upstream-and-re-run). (§5)
- Confirm the weekly retrain: after Sunday's `weekly_retrain.yml`, confirm it exited 0 and refreshed champion artifacts. (§3)
- Glance at the record: eyeball the public track record + the experiment ledger/changelog. Is the story honest and current? Any dud that needs its paired "next move" (Constitution #1)? (`ARCHITECTURE.md` §5l)
- IG token watch: once a week, check the IG long-lived token isn't near its ~60-day expiry; refresh early if so. (§10)
- Calibration (weeks 1–4 only): log edit/reject reasons; check the loosening criteria; decide whether to step the mode. (§7)

---

## Open items

- Exact clock times: the green cron (currently 08:00 UTC), the agent wake time, and per-platform posting windows in the owner's timezone (§2).
- Approval UX: Telegram vs. Slack bot (recommended over a dashboard, carried from `ARCHITECTURE.md` §5h / `CONTENT_SPEC.md` §7); build it in Phase B.
- Loosening thresholds: the §7 percentages/durations are sensible defaults; finalize after seeing real week-1 output.
- Champion-regression guard: the exact Δ threshold that trips a retrain/experiment 🔴 (ties to the pre-registered keep/drop rules in `roadmap.yaml`, `ARCHITECTURE.md` §9).
- Kill switch + `AUTONOMY_MODE` mechanism: config flag vs. repo variable vs. bot command; confirm both pipeline and agent read it live (§6, §11).
- Agent scheduling: the concrete scheduled-remote-agent / cron mechanism and its own failure/alert path (if the agent doesn't wake, that's its own 🔴).
- Weekly "report card" reel ops: when it renders + posts in the weekly rhythm (`CONTENT_SPEC.md` §7).
- Missed-day catch-up policy: auto-catch-up vs. owner-triggered `workflow_dispatch` (§8).
