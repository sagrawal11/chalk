# CHALK — Build Plan (ordered milestones, Phase B)

> **Status:** Draft v0.1 for owner review · Phase-A doc #5 (the last one). This is the ordered, executable build plan for **Phase B**. It does **not** restate the other docs — it sequences them into milestones a builder can pick up.
>
> **Companion docs (read for the *what* and *why*; this doc is the *when* and *in-what-order*):**
> - `CHALK_MASTER_PLAN.md` — thesis, Constitution, cadence/rollout (§7), autonomy (§9), path-to-launch (§14).
> - `FEATURE_ROADMAP.md` — the pre-committed rung ladder per sport + the closing **"buildable today vs needs-a-backfill"** section (the data-readiness map this plan sequences against).
> - `ARCHITECTURE.md` — repo structure (§3), component detail (§5), discrepancies-to-fix (§8), cadence/config (§7).
> - `CONTENT_SPEC.md` — locked "Editorial Terminal" design, content types (§3), the 🟡 guardrail-check spec (§5), reel wiring (§6).
> - `OPS_RUNBOOK.md` — Green/Yellow/Red workflows, escalation, calibration, the `AUTONOMY_MODE` tighten switch. *(Phase-A doc #4; authored alongside this plan — the operational contract M4–M7 implement against.)*
>
> **Terminology is inherited, not redefined:** "champion/challenger", "walk-forward", "ledger", "honest readout", "Rung N", "Act 1/2/probe", "🟢/🟡/🔴", "port vs new" all carry their `ARCHITECTURE.md`/`FEATURE_ROADMAP.md` meaning.

---

## 1. Purpose & sequencing principles

The goal of Phase B is to stand up the **market-blind experiment-and-publish loop end-to-end**, then fan it out to six leagues. Three principles set the build order:

1. **Prove the loop on ONE sport, ONE rung-band, before fanning out.** The centerpiece isn't any single model — it's the loop: *add a feature → measure it walk-forward → record it → decide keep/drop → publish the delta.* Build that loop once on **NFL Rungs 1–3** (all buildable today from cached data, no backfill) and demonstrate a real champion→challenger→promotion cycle **before** touching a second sport, a second rung-band, or a second platform. M1→M2 is the spine; everything after is repetition and hardening.
2. **Port, don't rebuild (`ARCHITECTURE.md` §1).** The data adapters, feature engine + leakage guards, the **existing** `backtest/team_backtest.py::walk_forward_backtest` + `model_training/validation.py::walk_forward_train`, track-record, content renderer, storage, and CI come over mature. The experiment harness *orchestrates* the existing eval — it does not reinvent evaluation. New code is confined to the six **NEW** components in `ARCHITECTURE.md` §5 (experiments/, publish/, agent/, content extensions, copy drafting, `/api/experiments`) plus the CFB plugin.
3. **Start the model simple; features toggle on progressively.** Each sport's champion begins at its Rung-1 baseline. Feature-builders exist in code from day one but are **gated by the champion config** — "add one feature" is a config+retrain, not new code (`ARCHITECTURE.md` §5b/§5d). This is what makes the public climb *real* and cheap to run.
4. **Ship cautious (`CHALK_MASTER_PLAN.md` §10).** Automation lands **dark** behind `AUTONOMY_MODE=approve_all` and `--dry-run` before it ever posts. Reddit/X go live first; IG runs "approve → post manually" until Meta app-review clears. Autonomy loosens only per `OPS_RUNBOOK.md`, never by default.
5. **Market-blind champion is the control, always.** `MARKET_BLIND` default True (`config/settings.py::market_blind()`). Rung-8 probes run as challengers measured *against* the market and are **never** folded into the champion (`ARCHITECTURE.md` §4/§5d).

**Critical path:** `M0 → M1 → M2` (the loop) → `M3 → M4 → M5` (render/publish/orchestrate) → `M6` (cautious launch) → `M7+` (fan out). M3 can begin in parallel with M2 once M1's data contract is stable; M4 depends on M3 assets existing.

---

## 2. Milestones

Format per milestone: **Goal · Key tasks · Acceptance criteria (verifiable/demoable) · Dependencies.** Acceptance criteria are written to be *checked*, not admired.

---

### M0 — Repo surgery & infra port

**Goal.** A clean, public `chalk` repo that builds and passes tests under the canonical Docker 3.10 stack, with the three `ARCHITECTURE.md` §8 discrepancies fixed. The current repo becomes a private playground.

**Key tasks.**
- Rename/relabel the current repo → private **`betting_testingground`** (the playground; nothing is deleted, it stays as reference).
- Create the new **public `chalk`** repo. Port the tree per `ARCHITECTURE.md` §3: `backend/sports/` · `backend/models/` + `backend/model_training/` · `feature_engine.py` + `sports/*/team_features.py` · `backend/backtest/` · `backend/track_record/` · `backend/picks/` · `backend/odds/` · `backend/content/` · `backend/web/` · `backend/utils/storage.py` · `backend/config/` · `reel/` · `tests/` · `docker-compose.yml` + `Makefile` + `config/requirements.txt`. Port the frontend (`lovable/`).
- **Fix discrepancy #2 (brand):** make `CHALK` / `@playthechalk` the **code default** in `backend/content/brand_config.py` (currently defaults to `HOOPS ORACLE`); drop legacy naming. `brand.json` becomes an optional override, not the source of the correct name.
- **Fix discrepancy #3 (env):** do **not** carry the checked-in `betting_venv/` into `chalk`; canonical env = **Docker 3.10 + `config/requirements.txt`**. Update the Makefile/README so every run + every test path uses the Docker stack (anaconda's pyarrow repetition-level bug means the cached parquets must be read there).
- **Fix discrepancy #1 (reel):** land the wiring *seam* now — a `reel/` that reads a slate-JSON contract and a Python-side stub that will write it (the actual write happens in M3). Keep `reel/render-reel.mjs` + its slate schema in the tree and pinned in CI.
- Stand up **GitHub Actions CI** on `chalk` (owner has Pro): build the Docker image + run `tests/` green on every push. Port `nightly_pipeline.yml` / `weekly_retrain.yml` as **disabled/dark** scaffolds (wired live in M5).
- Secrets scaffolding: create the **GitHub Actions encrypted secrets** entries listed in `ARCHITECTURE.md` §5k (empty placeholders where creds aren't issued yet).

**Acceptance criteria.**
- Fresh clone of `chalk` builds the Docker 3.10 image and the **full test suite passes in CI** with zero reliance on a checked-in venv (grep confirms no `betting_venv/` in the tree).
- `python -c "from backend.content.brand_config import ..."` (or the repo's equivalent) returns **`CHALK` / `@playthechalk` with no `brand.json` present** — the default is correct in code.
- `reel/render-reel.mjs` renders the committed sample slate under CI/Node; the slate-JSON schema is documented and pinned.
- The playground repo is private; `chalk` is public with an initial README + LICENSE (already drafted).

**Dependencies.** None (first milestone).

---

### M1 — Day-1 NFL baseline + eval harness proof

**Goal.** A deliberately-simple **NFL champion at Rung 1**, with a reproducible honest walk-forward number from the **existing** backtest. This is the "start the model simple" anchor and proves the eval harness works in the clean repo before the experiment harness wraps it.

**Key tasks.**
- Define the NFL Rung-1 champion feature set from the roadmap's Rung-1 builders (`NFL-01..NFL-05`: `OFF`, `DEF`, `NET_DIFF`, `WINPCT`, `PRIOR_DIFF`) — the box-score baseline already computed in `sports/nfl/team_features.py`.
- Write the champion descriptor `artifacts/nfl/champion.json` = `{model_version: nfl-v1, active_feature_builders:[...], cumulative_metrics:{}}` (the schema the harness reads in M2).
- Wire `walk_forward_backtest` (`backend/backtest/team_backtest.py`, already present) to run this config over the NFL **train+CV seasons**, holding the final season **untouched**. Produce SU accuracy, winner log-loss, margin/total MAE + N + eval window.
- Confirm leakage discipline holds on the ported path (`shift(1)`, backward-exclusive `merge_asof`, output whitelist, train/serve column parity) — `ARCHITECTURE.md` §5b.
- Refit the shipped Rung-1 model via `walk_forward_train` at the validated config.

**Acceptance criteria.**
- `artifacts/nfl/champion.json` exists and validates against the harness schema.
- A single documented command produces a **reproducible** NFL Rung-1 walk-forward number (same seasons + config ⇒ same metrics), with the eval window + N printed. The final NFL season is provably **not** in the selection window.
- The number is *honest and unimpressive-by-design* (a box-score baseline) — no leakage, matches roadmap expectations for Rung 1.

**Dependencies.** M0.

---

### M2 — The Feature-Experiment Harness (the centerpiece)

**Goal.** The full champion/challenger loop over the existing backtest, with a public **experiment ledger**, an **honest readout** on the untouched test set, and **model-versioning + pre-registered promotion rules**. Demonstrated by climbing NFL from Rung 1 into Rung 2/3.

**Key tasks.** (all under `backend/experiments/`, per `ARCHITECTURE.md` §5d)
- **`roadmap.yaml`** — machine-readable port of `FEATURE_ROADMAP.md`: ordered list of `{id, sport, rung, name, builder(s), hypothesis, eval_metric, act:1|2|probe, keep_rule, status}`. Seed with the NFL ladder; other sports follow in M7. Order = the queue (held loosely; status is mutable).
- **`run_experiment.py`** — pop next `queued` (or a given id) → assemble challenger (champion's builders **+ this rung's builder**) → run `walk_forward_backtest` for champion & challenger on **train+CV only** (cache champion metrics; only the challenger reruns) → compute Δ accuracy / Δ log-loss / Δ MAE (Δ 3-way log-loss for soccer later) with window + N → apply the **pre-registered keep-rule** → **record to the ledger regardless of outcome** (duds are content) → if kept, promote: bump `model_version` (`nfl-v1→nfl-v2`), refit shipped model on all data at the validated config, rewrite `champion.json` → emit a structured `ExperimentResult`.
- **`data/experiments_ledger.parquet`** — one row per experiment (`id, sport, run_at, champion_version, challenger_version, delta_accuracy, delta_logloss, delta_mae, n_games, eval_window, decision, gap_to_market?, notes`). This ledger **is** the public progression record.
- **`honest_readout.py`** — infrequent eval of the **current champion** on the **untouched final test set**; also reports the **gap** between walk-forward-selected and untouched-test performance (the monitored overfitting signal). Never used for keep/drop.
- **Overfitting/honesty guards baked in** (`ARCHITECTURE.md` §5d): pre-registered thresholds committed in `roadmap.yaml` *before* the result is seen; cumulative multiple-comparisons exposure tracked (experiments run vs kept) and reported; walk-forward OOS deltas only.
- **Champion-version storage** — pin each champion's model artifacts in R2 keyed by `model_version` (resolves an `ARCHITECTURE.md` §9 TBD).

**Acceptance criteria.**
- Running the queue from **NFL-02 → NFL-03** (or the first two Rung-2/3 rungs) produces **ledger rows for each**, at least one **champion version bump** (`nfl-v1→v2→…`), and each decision cites the **pre-registered keep-rule that was set before the run**.
- A **kept** experiment refits the shipped model and rewrites `champion.json`; a **dropped/parked** experiment still writes a ledger row (dud recorded) and leaves the champion unchanged.
- `honest_readout.py` emits the champion's untouched-test number **and** the selected-vs-untouched gap; the multiple-comparisons counter increments correctly.
- The whole loop reuses `walk_forward_backtest` — no re-implemented evaluation (verifiable by import graph).

**Dependencies.** M1 (champion schema + eval path).

---

### M3 — Content generators (locked "Editorial Terminal" design)

**Goal.** The day's cards **and** reel render from **real** experiment/prediction/result data in the locked `CONTENT_SPEC.md` skin — including the wired reel and the pinned triptych.

**Key tasks.** (extend `backend/content/`, wire `reel/`, per `ARCHITECTURE.md` §5g + `CONTENT_SPEC.md` §3/§6)
- Port the locked reference `*.html` templates → `backend/content/templates/` with data slots; vendor the fonts (Fraunces · Archivo · Inter · IBM Plex Mono) for offline/CI rendering; ship the in-house SVG icon set.
- **Feature-post generator** (`content/feature_post.py`) — `ExperimentResult` → the signature **experiment-log** card/carousel (`CONTENT_SPEC.md` §3.2): before/after walk-forward metric chart + *tested X → what it did → what's next*.
- **Score-prediction card** (§3.1) from the market-blind `game_winner_picks`.
- **Results / graded card** (§3.3) from the graded `results_ledger` (unpriced picks → `units=NaN`, ROI-ineligible — never fabricated).
- **Multi-sport carousel** (§3.4) — combine the day's per-sport feature posts into one IG carousel.
- **Pinned triptych** (§3.5) — the three-tile continuous graphic.
- **Reel — PORT + WIRE (fixes discrepancy #1):** `daily_content` writes the slate JSON contract → invokes `render-reel.mjs` → one combined daily MP4 (`CONTENT_SPEC.md` §6).
- All generators emit into the locked palette/type/layout primitives.

**Acceptance criteria.**
- From a real M2 `ExperimentResult` + a real day's picks/results, the generators produce: an **experiment-log card**, a **score card**, a **results card**, a **multi-sport carousel**, the **triptych**, and a **combined daily MP4** — all in the `CONTENT_SPEC.md` skin, rendered under the Docker/CI + Node stack.
- The reel renders **from pipeline-written slate JSON** (not the hand-authored sample) — discrepancy #1 demonstrably closed.
- A design spot-check confirms fonts, icons, palette, and the disclaimer footer match the locked spec (feeds `/design-review`).

**Dependencies.** M1 (real predictions) + M2 (real `ExperimentResult`). Can start once M1's data contract is stable; final AC needs M2.

---

### M4 — Publishing + approval queue + guardrails

**Goal.** An approved draft posts to **X/Reddit idempotently** (IG manual-interim), gated by the automated 🟡 guardrail checks and an approval mechanism — all landing **dark** (`--dry-run` / `approve_all`) first.

**Key tasks.** (all NEW, `ARCHITECTURE.md` §5h/§5i; checks per `CONTENT_SPEC.md` §5)
- **`Publisher` ABC** (mirrors `OddsProvider`): `publish(platform, asset, text) -> PostRef`, `supports(platform)`, `MultiPublisher` fan-out. Adapters: `reddit.py` (PRAW), `x.py` (X API v2 + media; threads via reply-chain), `ig.py` (Graph API pulling media from a **public R2 URL** → assets stage to R2 first).
- **Idempotency + safety:** store returned `PostRef` keyed by draft id (never double-post); per-platform rate-limit backoff; `--dry-run`; a **global kill switch**.
- **IG interim mode:** `ig.py` runs "approve → post manually" until Meta app-review clears; Reddit/X auto-publish. Flip to full auto when access lands.
- **Draft store** (`publish/queue/`): pending posts as JSON/parquet `{id, platform, kind, asset_paths, caption/thread, checks[], status: pending|approved|rejected|posted}`.
- **Copy drafting** (`content/copy.py`, NEW): LLM-drafts captions/threads from **structured** experiment/prediction/result data only (never free-form) → into the Yellow queue. Uses the latest Claude by default (`ARCHITECTURE.md` §9 / `CONTENT_SPEC.md` §1). Voice guide applied.
- **Automated guardrail checks** (`publish/guardrails.py`) — implement all eight from `CONTENT_SPEC.md` §5, gating every Yellow item: (1) tout denylist, (2) retired-phrasing/stamp check, (3) **every stated number reconciles against the source record** (no hallucinated stats), (4) disclaimer present, (5) NEXT-explains-the-stat (experiment posts), (6) on-voice LLM check, (7) tragedy/serious-injury screen → route 🔴, (8) idempotency key.
- **Approval mechanism** — the recommended **Telegram/Slack bot**: DMs the rendered asset + drafted copy with ✅/✏️/❌ (approve from phone). (Owner's call per `OPS_RUNBOOK.md`; recommendation = bot.)
- **The tighten switch:** `AUTONOMY_MODE` flag (`approve_all | yellow_auto | …`) that reverts everything to full human approval in one setting.

**Acceptance criteria.**
- An **approved** draft posts to **X and Reddit**, returns a `PostRef`, and re-running the same draft **does not double-post** (idempotency proven).
- A crafted **tout-language** draft and a crafted **hallucinated-number** draft are both **blocked** by guardrails and never reach a platform; a crafted **tragedy/injury** draft routes to 🔴.
- IG path produces a staged public R2 URL + queued manual-post item (interim mode), without auto-posting.
- Setting `AUTONOMY_MODE=approve_all` forces every item through human approval; the **global kill switch** halts all posting.

**Dependencies.** M3 (assets + copy to publish).

---

### M5 — Orchestration & the scheduled Claude agent

**Goal.** A **full unattended day** runs end-to-end into the approval queue: the 🟢 GitHub Actions green pipeline + the 🟡 scheduled Claude agent + the weekly retrain, secrets wired.

**Key tasks.** (`ARCHITECTURE.md` §5j / §6A)
- **🟢 Green — GitHub Actions** (activate the M0 scaffolds): daily = data refresh → `daily_content.run_day` (predict market-blind → `select_best_bets` → `lock_predictions` SHA-256 → render cards + write reel slate + `render-reel.mjs` → grade yesterday) → **the day's scheduled experiment(s)** (`run_experiment.py` per the cadence config) → draft Yellow copy → stage assets to R2 → enqueue drafts. Deterministic; no judgment.
- **Weekly retrain** workflow = the heavy refit.
- **🟡 Yellow — scheduled Claude agent** (`backend/agent/`): fires on cadence to finalize/sanity-check drafted copy, run the judgment guardrail checks, and decide post-worthiness. In **cautious mode** it only assembles the batch for owner approval. Runs via a scheduled remote agent / cron.
- **🔴 Red escalation:** any pipeline/agent anomaly (data source down, model regression, hallucinated-number fail, tragedy/injury hit, implausible pick) → halt that item + escalate; never auto-post (`OPS_RUNBOOK.md`).
- Load all secrets from **Actions encrypted secrets** (`ARCHITECTURE.md` §5k); unofficial-API steps use the `nightly.py` retry + graceful-skip pattern.

**Acceptance criteria.**
- A **single scheduled run** executes the full daily chain unattended and lands drafts (cards + reel + copy, checks attached) in the approval queue — **zero posts** because `AUTONOMY_MODE=approve_all`.
- A deliberately-broken data source triggers a **🔴 escalation** and a graceful skip, not a crash or a bad post.
- The weekly retrain runs on schedule and produces a refit champion artifact.
- No secret is hardcoded; all pulled from Actions secrets.

**Dependencies.** M2 (experiments), M3 (render), M4 (queue + guardrails + publisher).

---

### M6 — Launch (cautious)

**Goal.** The first real week of NFL content posted **under owner approval**, with the public progression site live — and **zero Constitution violations**.

**Key tasks.**
- Wire **`/api/experiments`** (progression feed: champion-metric history + per-experiment results) and extend the frontend track-record page into the public **"changelog"** (`ARCHITECTURE.md` §5l).
- Seed the day-one honest track record from `walk_forward_predictions` (`track_record/seed_writer.py`).
- Post the **flagship / pinned triptych**; run in **`approve_all`** mode (owner ✅ every item via the bot).
- Publish the **first end-to-end NFL experiment** (an M2 result → M3 feature-post → M4 approved → posted to X/Reddit).
- Run the **go-live checklist** (§4) as the gate.

**Acceptance criteria.**
- The **first real week** of NFL content is posted under owner approval to the live platforms (X/Reddit; IG manual-interim).
- The **track-record/changelog site is live** and shows real champion-metric history + the first experiment(s).
- **Zero Constitution violations** (`CHALK_MASTER_PLAN.md` §3): no fabricated ROI, no touting, no hallucinated numbers, every posted pick locked pre-tip.
- Every §4 checklist item is green.

**Dependencies.** M5 (unattended pipeline into the queue) + the §4 go-live checklist.

---

### M7+ — Fan out (the repeatable phase)

**Goal.** Extend the proven loop to the remaining leagues on the `CHALK_MASTER_PLAN.md` §7 rollout order, unlock Rung-5 features via one-time free backfills, and loosen autonomy per `OPS_RUNBOOK.md`.

**Key tasks / ordered sub-milestones.**
- **M7a — CFB plugin (net-new) + MLB, for fall launch alongside NFL.**
  - Build `sports/cfb/` on the CFBD free API following the `sports/nfl/` shape (`teams.py` for 130+ FBS + FCS bucket, `geo.py` venue table, `data.py` cached HTTP client, `team_features.py`); add CFBD `/lines` to `backend/odds/` (grading only). Seed the CFB ladder into `roadmap.yaml`.
  - Bring MLB Rungs 1–4 online (buildable today, cached). Add both to the cadence config (NFL/CFB ~twice-weekly, MLB few-per-week).
- **M7b — NBA + NHL (October).** Enable each at Rungs 1–4 (buildable today); add to cadence (NBA/NHL daily).
- **M7c — Rung-5 backfills (one-time, free).** Run the historical backfills that unlock Rung 5+: **NFL PBP** (EPA/CPOE), **MLB Statcast/FanGraphs**, **NHL MoneyPuck** (xG), plus the NHL boxscore `lastPeriodType` (OT/SO) backfill. Then queue those sports' Rung-5+ experiments.
- **M7d — Soccer (later).** Poisson/Dixon-Coles 3-way; Rungs 1–4 buildable today; add Δ 3-way log-loss handling to the harness.
- **M7e — Loosen autonomy.** As guardrails prove out over the calibration weeks, step `AUTONOMY_MODE` toward `yellow_auto` per `OPS_RUNBOOK.md`; flip IG to full auto when Meta app-review clears.
- **Rung-8 probes** run as challengers per sport as the ladders reach them — recording **both** Δ-vs-champion and gap-to-market; champion stays market-blind.

**Acceptance criteria.**
- Each sport added reaches parity with NFL's loop: champion.json + ledger rows + rendered content + posts, at Rungs 1–4, with **zero Constitution violations**.
- A completed Rung-5 backfill demonstrably unlocks ≥1 Rung-5 experiment for that sport (ledger row produced from newly-available fields).
- Each autonomy step-up is gated by an `OPS_RUNBOOK.md` criterion, not a calendar date.

**Dependencies.** M6 (proven loop + live site). Backfills (M7c) gate the corresponding Rung-5+ experiments only — Rungs 1–4 need no backfill.

---

## 3. Buildable-today vs needs-backfill (data-readiness → unlock)

Direct sequencing map of `FEATURE_ROADMAP.md`'s closing section. "Buildable today" = cached data, zero new ingests; "needs-backfill" = a one-time **free** historical pull first.

| Sport | Rungs 1–4 (today) | Rung 5+ gate | Unlocks in |
|---|---|---|---|
| **NFL** | ✅ cached (box + schedule) | one-time **PBP** backfill (EPA/CPOE) | M1–M2 (Rungs 1–3), then M7c for Rung 5+ |
| **CFB** | ⛔ whole **CFBD plugin is net-new** (must build first) | same plugin/backfill covers 5+ | **M7a** (plugin) → 5+ same phase |
| **NBA** | ✅ cached (73-col parquet) | none needed for 1–4; deeper advanced already present | **M7b** |
| **NHL** | ✅ cached (schedule + goals) | **MoneyPuck** (xG) + boxscore `lastPeriodType` (OT/SO) backfill | **M7b** (1–4) → **M7c** (5+) |
| **MLB** | ✅ cached (StatsAPI box) | **Statcast/FanGraphs** backfill (starter-quality is king) | **M7a** (1–4) → **M7c** (5+) |
| **Soccer** | ✅ cached (football-data/Understat) | xG already in source for 5+ | **M7d** |

**Sequencing rule (from the roadmap):** stand up the day-1 baseline + eval harness on **NFL**, prove the loop on **Rungs 1–3**, *then* fan out. CFB is the one sport whose Rungs 1–4 are **not** buildable today (no plugin yet) — it's a build, not a backfill.

---

## 4. Go-live checklist (definition of done for cautious launch — the M6 gate)

Every item green before M6 posts a single real item:

**Loop & honesty**
- [ ] NFL champion promoted through **≥ Rung 3** with ledger rows for every experiment run (kept **and** dropped).
- [ ] `honest_readout.py` produces the champion's **untouched-test** number + the selected-vs-untouched **overfitting gap**; multiple-comparisons counter reported.
- [ ] Every pick is **locked (SHA-256) pre-tip**; graded results write `units=NaN` for unpriced picks (no fabricated ROI).

**Content & design**
- [ ] Cards + **combined reel** render from **real** data in the locked `CONTENT_SPEC.md` skin; reel is pipeline-wired (discrepancy #1 closed).
- [ ] Disclaimer footer present on every asset; `/design-review` spot-check passes.

**Publishing & guardrails**
- [ ] All **eight** `CONTENT_SPEC.md` §5 guardrail checks live and gating; tout / hallucinated-number / tragedy test drafts all correctly **blocked or 🔴-routed**.
- [ ] X + Reddit post **idempotently** (proven no-double-post); IG in approve→manual interim; **global kill switch** works.
- [ ] `AUTONOMY_MODE=approve_all` — owner ✅ every item; approval bot delivering assets + copy.

**Orchestration & infra**
- [ ] Full **unattended daily run** lands drafts in the queue with **zero auto-posts**; a broken source triggers 🔴 + graceful skip.
- [ ] All secrets in **Actions encrypted secrets**; no hardcoded creds; brand default = `CHALK`; **no `betting_venv/`** in `chalk`; tests green under Docker 3.10.

**Public record**
- [ ] `/api/experiments` + the **changelog/track-record site** live, showing real champion history and the first experiment(s).

**Constitution**
- [ ] A read-through against `CHALK_MASTER_PLAN.md` §3 confirms **zero violations** in the queued launch batch.

---

## 5. Risks & dependencies (top risks + mitigations)

| # | Risk | Impact | Mitigation | Handled in |
|---|---|---|---|---|
| R1 | **CFBD free-tier rate limits at daily scale** | CFB pipeline throttled/blocked in-season | Thin HTTP client with **on-disk response caching**; historical backfill fits free tier; budget the **~$10/mo Patreon tier** for live `/games`+`/lines` | `ARCHITECTURE.md` §4/§5a, `FEATURE_ROADMAP.md` CFB audit, master plan §7 |
| R2 | **IG (Meta) app-review timing** slips past fall launch | No IG auto-post at launch | `ig.py` ships in **approve→post-manual interim**; Reddit/X auto-publish carry launch; flip IG to auto when access lands | `ARCHITECTURE.md` §5i, M4/M7e |
| R3 | **Unofficial API breaks** (NHL, Statcast, CFBD-at-scale, ESPN slate) | A day's data missing / pipeline crash | Wrap each behind the sport's adapter with **retries + graceful skip** (`nightly.py` pattern); a source-down anomaly → **🔴 skip**, never a bad post | `ARCHITECTURE.md` §5a/§5j, `OPS_RUNBOOK.md` |
| R4 | **Overfitting the walk-forward set** (the credibility risk) | Published "climb" is illusory | **Untouched final test set** never used for selection; **pre-registered** thresholds + `roadmap.yaml` order; **multiple-comparisons counter**; `honest_readout.py` publishes the selected-vs-untouched **gap** as a monitored signal | `ARCHITECTURE.md` §5d, `FEATURE_ROADMAP.md` methodology, master plan §5 |
| R5 | **Solo-operator load** (approvals + ops on one person) | Burnout / missed days / rushed approvals | Everything **automated up to the ✅**; phone-based approval **bot**; `AUTONOMY_MODE` loosens as guardrails prove out; cadence is config, not manual | `ARCHITECTURE.md` §5h/§5j, `OPS_RUNBOOK.md`, master plan §9/§10 |
| R6 | **Hallucinated numbers / tout drift in LLM copy** | A single bad post breaks the honesty brand | Copy drafts only from **structured** records; guardrail check **reconciles every number to source**; tout denylist; on-voice + tragedy screens | `CONTENT_SPEC.md` §5, `ARCHITECTURE.md` §5h |
| R7 | **Market-blindness leaks** (line sneaks into the model) | Thesis invalidated | `MARKET_BLIND` default True enforced at `settings.market_blind()`; Rung-8 line usage is **probe/grading only**, architecturally separate | `ARCHITECTURE.md` §4/§5d, `config/settings.py` |
| R8 | **Model regression on a weekly retrain** | Silent quality drop shipped | Retrain validated via `walk_forward_train`; regression → **🔴**; champion artifacts pinned per `model_version` for rollback | `ARCHITECTURE.md` §5c/§5j, M2/M5 |

**Hard external dependencies to secure early:** CFBD API key (R1); Meta app-review submission started ASAP (R2); X + Reddit API credentials; R2 bucket + creds; the LLM API key for `content/copy.py`; the Telegram/Slack bot token. All live in Actions secrets (M0 scaffolds, M5 wires).

---

## 6. Open items / TBD

- **`OPS_RUNBOOK.md` finalization** — this plan assumes it defines the exact 🟢/🟡/🔴 workflows, escalation, calibration procedure, and the `AUTONOMY_MODE` step-up criteria. M4–M7 implement against it; if it lands after this doc, M5's agent behavior + M7e's loosening criteria inherit from it. **(Blocking for M5 agent semantics.)**
- **Approval UX** — Telegram vs Slack bot vs interactive dashboard. Recommendation = bot; owner's call. (`ARCHITECTURE.md` §9, `CONTENT_SPEC.md` §7.) **(Blocking for M4.)**
- **LLM provider/model for `content/copy.py`** — defaults to the latest Claude; confirm model id + budget. (`ARCHITECTURE.md` §9.)
- **Exact keep/drop thresholds per metric/sport** — pre-registered in `roadmap.yaml`; **tuned during the first NFL rungs (M2)** and then frozen per sport.
- **Champion-version storage shape** — `champion.json` per sport vs a versioned artifacts table; how R2 pins artifacts per `model_version`. (M2 picks one; `ARCHITECTURE.md` §9.)
- **CFBD tier decision** — free vs ~$10/mo Patreon for live in-season pulls; decide before M7a in-season load (R1).
- **Cadence config format** — the machine-readable per-sport experiment schedule the Green pipeline reads (`ARCHITECTURE.md` §7). Land with M5.
- **Repo cutover mechanics** — history strategy for the new public `chalk` (fresh init vs filtered import from the playground), and what (if anything) beyond code moves. (M0.)
- **Backfill storage footprint** — disk/R2 budget for NFL PBP + MLB Statcast + NHL MoneyPuck parquets before M7c.

---

*End of Phase-A planning package. Phase B begins at M0.*
