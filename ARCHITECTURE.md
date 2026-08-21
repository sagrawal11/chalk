# CHALK — Architecture (the engineering blueprint)

> **Status:** Draft v0.1 for owner review. Phase-A doc #2 (companion to `CHALK_MASTER_PLAN.md` + `FEATURE_ROADMAP.md`). Describes the target architecture of the clean **`chalk`** repo: what we **port** from the playground (mature, code-verified below), what we **build new** (the build-in-public pieces), and how it all runs under tiered autonomy.
>
> **Grounding:** the "port" descriptions cite real modules in the current repo. The "new" components are designed to *extend* those seams, not replace them.

---

## 1. Design principles

1. **Port the infra, start the model simple.** The data adapters, feature machinery, eval harness, track-record, content renderer, storage, and CI all come over mature. But each sport's *champion model* starts at its Rung-1 baseline and climbs the roadmap in public. Feature-builders exist in code from day one but are **toggled on progressively** by the champion config — so "add one feature" is a config+retrain, not new code each time.
2. **Extend the existing eval harness, don't rebuild it.** The walk-forward backtest (`backtest/team_backtest.py`) and training CV (`model_training/validation.py`) already produce honest OOS accuracy / log-loss / MAE. The new experiment harness *orchestrates* them; it doesn't reinvent evaluation.
3. **Vendor-agnostic seams.** The repo already isolates odds behind `OddsProvider`. We mirror that pattern for the new **`Publisher`** seam (IG/X/Reddit) and the **rasterizer** seam that already exists (`CHALK_RASTERIZER`).
4. **Market-blind champion = the control.** The champion model never sees the line (`MARKET_BLIND` default True). Market-adjacent features (Rung 8) run as *challengers/probes* measured against the market — never folded into the champion. This is the thesis, enforced architecturally.
5. **Tiered autonomy maps to components** (see §5j): 🟢 Green = the deterministic GitHub Actions pipeline; 🟡 Yellow = the draft queue + guardrails + scheduled agent; 🔴 Red = anomaly escalation.
6. **Honesty is enforced in code, not vibes.** Leakage guards, the untouched test set, the immutable SHA-256 slate lock, and the automated guardrail checks are all real code gates.

---

## 2. System overview

```
                         ┌───────────────────────── ORCHESTRATION ─────────────────────────┐
                         │  GitHub Actions (🟢 green pipeline)   +   Scheduled Claude agent (🟡/🔴) │
                         └──────────────────────────────┬───────────────────────────────────┘
                                                         │ drives
  DATA            FEATURES           MODEL / EXPERIMENT           PREDICT+PICK        CONTENT            APPROVE            PUBLISH
 ┌───────┐      ┌──────────┐        ┌───────────────────┐       ┌───────────┐      ┌──────────┐       ┌──────────┐       ┌──────────┐
 │ sport │─────▶│ feature  │───────▶│ champion/challenger│──────▶│ predict_  │─────▶│ feature  │──────▶│  draft   │──────▶│ Publisher│
 │ data  │      │ engine + │        │ + walk-forward     │       │ game →    │      │ post /   │  🟡   │  queue + │  🟢   │ IG/X/    │
 │ adapt.│      │ leakage  │        │ EXPERIMENT HARNESS │       │ best_bet  │      │ reel /   │       │ guardrail│       │ Reddit   │
 └───┬───┘      │ guards   │        │  (the new core)    │       │ (blind)   │      │ results  │       │ checks   │       └────┬─────┘
     │          └──────────┘        └─────────┬──────────┘       └─────┬─────┘      └────┬─────┘       └────┬─────┘            │
     │                                        │ Δmetrics                │ picks           │ assets           │ approve          │ post ids
     ▼                                        ▼                         ▼                 ▼                  ▼                  ▼
  R2/MinIO  ◀──────────────── experiments_ledger + champion versions + LOCK (SHA-256) ──▶ track_record (grade → aggregate) ──▶ /api/track-record ─▶ frontend "changelog"
```

Cross-cutting: **R2/MinIO** (artifacts, assets, bundles), **Redis** (prediction cache), **config/flags** (`MARKET_BLIND`, autonomy mode, cadence), **secrets** (GitHub Actions).

---

## 3. Repo structure for `chalk` (port vs new)

| Area | Path | Port / New | Notes |
|---|---|---|---|
| Sport plugin core | `backend/sports/` (`base.py` ABC + per-sport) | **Port** | Add `sports/cfb/` (new plugin). |
| Feature engine | `backend/feature_engine.py`, `sports/*/team_features.py` | **Port** | Feature-builders gated by champion config (see §5d). |
| Model trainers | `backend/model_training/`, `backend/models/` | **Port** | Champions start at Rung-1; climb via experiments. |
| Eval harness | `backend/backtest/`, `model_training/validation.py` | **Port** | Reused by the experiment harness. |
| **Experiment harness** | `backend/experiments/` | **NEW** | Roadmap-as-data + champion/challenger runner + ledger (§5d). |
| Track record | `backend/track_record/` | **Port** | Lock → grade → aggregate, SHA-256. |
| Picks | `backend/picks/` | **Port** | Market-blind `game_winner_picks`. |
| Odds (grading only) | `backend/odds/` | **Port** | Add CFBD `/lines` + confirm live providers. |
| Content render | `backend/content/` | **Port + extend** | Add feature-post + multi-sport carousel + results generators. |
| Reel | `reel/` (Remotion) | **Port + WIRE** | Wire into the pipeline (currently standalone — see §8). |
| **Publishing** | `backend/publish/` | **NEW** | `Publisher` ABC + IG/X/Reddit adapters + idempotency (§5i). |
| **Approval queue + guardrails** | `backend/publish/queue/`, `backend/publish/guardrails.py` | **NEW** | Draft store + automated checks + the bot (§5h). |
| **Autonomy agent** | `backend/agent/` | **NEW** | Scheduled-agent entrypoints + prompts + Red escalation (§5j). |
| Copy drafting | `backend/content/copy.py` | **NEW** | LLM-drafted captions/threads from structured data (§5g). |
| API | `backend/web/app.py` | **Port + extend** | Add `/api/experiments` (the progression feed). |
| Frontend | `lovable/` | **Port + extend** | Track-record page → the public "changelog"/progression view. |
| Storage | `backend/utils/storage.py` | **Port** | R2/MinIO; stage public asset URLs for IG. |
| Config | `backend/config/` | **Port** | Add autonomy mode + cadence + roadmap path. |
| Orchestration | `.github/workflows/` | **Port + extend** | Green pipeline + experiment step + draft/stage step. |
| Infra | `docker-compose.yml`, `Makefile`, `config/requirements.txt`, `tests/` | **Port** | Canonical env = Docker 3.10 (drop `betting_venv` reliance). |

**Fix-on-port (discrepancies found in the audit):** (a) **wire the reel** into the pipeline (write the slate JSON → invoke `render-reel.mjs`); (b) **unify the brand** — make `CHALK`/`@playthechalk` the code default in `brand_config.py`, not just a `brand.json` override; (c) **drop the checked-in `betting_venv/`** (canonical env is Docker 3.10 + `config/requirements.txt`).

---

## 4. The Sport plugin core (ported)

`backend/sports/base.py` — the `Sport` ABC + a lazy registry (`get_sport(key)` instantiates+caches; heavy imports deferred). Each sport implements: `canonical_team`, `current_season`, `season_from_date`, `player_targets`, `team_targets`, `score_ranges`, and (as capable) `predict_game`, `predict_player`, `schedule`; declares `capabilities` and answers `supports(cap)`.

Per-sport package shape (proven by `sports/nba/` and `sports/nfl/`): `teams.py` (canonical identity + aliases + season bridge), `data.py`/`*_data.py` (the free-feed adapter), `team_features.py` (+`player_features.py`), `geo.py` (travel/altitude), `sport.py` (the thin adapter wiring predictors + schedule). **New: `sports/cfb/`** follows this shape on the CFBD API (data adapter with cached HTTP client; `teams.py` for 130+ FBS + FCS bucket; `geo.py` venue table; `team_features.py`).

---

## 5. Component detail

### 5a. Data pipeline per sport (ported)
Each sport's `data.py` fetches its free feed (NFL nflverse, NBA Kaggle+SQLite+B-Ref logs, MLB StatsAPI+Statcast, NHL API+MoneyPuck, soccer football-data/Understat, **CFB CFBD**). Immutable historical parquets are cached; the current season is refetched live. Unofficial APIs are wrapped with retries + graceful skips (the `nightly.py` step pattern). Free odds are snapshotted for **grading only**.

### 5b. Feature engineering + leakage discipline (ported)
`feature_engine.py` (players) and `sports/*/team_features.py` (teams) enforce the discipline the whole brand rests on: `shift(1)` before every rolling window, `merge_asof(direction="backward", allow_exact_matches=False)` for all prior-state joins, expanding-mean opponent priors, a strict output **whitelist** dropping same-game leaky columns, and **train/serve parity** via `split_features_targets()` (one source of truth for columns; a mismatch logs loudly). Individual feature-builders (rolling form, opponent adjustment, Elo, availability `TM_OUT_*`, EPA/xG/etc.) are the roadmap rungs — see §5d for how they toggle on.

### 5c. Model & prediction (ported, market-blind)
`model_training/train_team_model.py` trains two LightGBM regressors (margin + total) via `walk_forward_train`, each with a robust residual σ (`1.2533·holdout_mae`). `models/team_predictor.py::predict_game()` produces μ/σ for margin+total → `p_home_win`, `home_pts`, `away_pts` → a `GamePrediction`. `config/settings.py::market_blind()` (default True) forces the pure-model path (no line as input); the market-anchored branch is reachable only with `MARKET_BLIND=0`. Soccer is Poisson/Dixon-Coles (3-way with a real P(draw)).

### 5d. The Feature-Experiment Harness — `backend/experiments/` (NEW — the centerpiece)
This operationalizes "add one feature → measure what it did → record it → decide → publish." It is an orchestration layer over the **existing** eval harness plus a ledger and model-versioning.

**Roadmap-as-data — `experiments/roadmap.yaml`.** A machine-readable port of `FEATURE_ROADMAP.md`: an ordered list of experiments, each `{id: NFL-06, sport: nfl, rung: 2, name, builder: <feature-builder key(s)>, hypothesis, eval_metric, act: 1|2|probe, status: queued}`. Order = the prioritized queue (held loosely — status can be reordered). This is the single source that ties the human roadmap ↔ the runner ↔ the results.

**Champion / challenger.** Each sport has a **champion** = `{model_version, active_feature_builders[], cumulative_metrics}` stored at `artifacts/<sport>/champion.json`. An experiment builds a **challenger** = champion's active builders **+ this rung's builder**. Because feature-builders are individually toggleable (§5b), a challenger is a config diff, not new code.

**The runner — `experiments/run_experiment.py`:**
1. Pop the next `queued` experiment (or a given id).
2. Assemble the challenger feature set (champion + this builder).
3. Run the **existing** `backtest/team_backtest.py::walk_forward_backtest` for champion and challenger over the **train+CV seasons only** (the final season stays untouched). Cache champion metrics so only the challenger reruns.
4. Compute Δ metrics (Δ accuracy, Δ log-loss, Δ MAE/score-MAE; for soccer Δ 3-way log-loss) with the eval window + N.
5. **Decision by pre-registered rule** (e.g. keep if Δ log-loss improves beyond a fixed threshold on walk-forward OOS; else drop or park). Record to the ledger *regardless of outcome* — duds are content.
6. If **kept**: promote challenger → new champion (bump `model_version`, e.g. `nfl-v3→nfl-v4`; refit the shipped model on all data at the validated config via `walk_forward_train`).
7. Emit a structured `ExperimentResult` → the feature-post generator (§5g).

**Experiment ledger — `data/experiments_ledger.parquet`.** One row per experiment: `{id, sport, run_at, champion_version, challenger_version, delta_accuracy, delta_logloss, delta_mae, n_games, eval_window, decision, gap_to_market?, notes}`. This ledger **is** the public progression story — the "accuracy climbing" chart is the champion-metric history over this ledger.

**Overfitting / honesty guards (baked in):**
- The **final untouched test set** is never used for keep/drop selection. A separate, *infrequent* `experiments/honest_readout.py` evaluates the current champion on it — that's the number we publish as the honest headline, and the gap between walk-forward-selected and untouched-test performance is itself a monitored (and postable) signal of overfitting.
- **Pre-registered thresholds** (decided before the result is seen) + the pre-committed `roadmap.yaml` order.
- **Cumulative multiple-comparisons exposure** is tracked (how many experiments run vs. kept) and reported.
- Walk-forward **OOS** deltas only — never in-sample fit.

**Market-adjacent probes (Rung 8).** Run as challengers too, but the champion stays market-blind. Their result records **two** numbers: Δ-vs-champion (does knowing injuries/lineups improve the blind model?) and **gap-to-market** (CLV / residual vs the closing line) — the Act-2 decomposition. A probe that helps the blind model but still can't beat the market is the thesis, captured as data.

### 5e. Picks (ported, market-blind)
`picks/best_bet.py::select_best_bets` → one odds-free `game_winner_picks` per game (favored side; `edge = model_prob − 0.5` as honest confidence, not a market edge). Every game gets a headline pick. Market path is opt-in only.

### 5f. Track record (ported)
`track_record/` lock → grade → aggregate: `lock.py` writes the immutable SHA-256-hashed slate **before tip**; `grade.py` grades vs real finals into `results_ledger.parquet` (unpriced picks → `units=NaN`, ROI-ineligible — never fabricated); `aggregate.py::headline()` serves record/win%/streak/score-MAE with winner accuracy as the hero. `seed_writer.py` seeds a day-one honest record from `walk_forward_predictions`.

### 5g. Content generators (extend `backend/content/` + wire `reel/`)
- **Feature post (NEW — the daily engine):** `content/feature_post.py` takes an `ExperimentResult` → a card/carousel with the before/after walk-forward metric chart + `tested X → what it did → what's next` copy.
- **Predictions reel (PORT + WIRE):** the pipeline writes the slate JSON contract (`reel/` already validates it) and invokes `render-reel.mjs` → one combined daily MP4. Fixes the standalone-reel discrepancy.
- **Results (PORT + extend):** the graded ledger → a results story + weekly "report card" reel.
- **Multi-sport IG carousel (NEW):** combine the day's per-sport feature posts into one IG carousel (per §8 of the master plan — per-sport depth goes to X/Reddit, IG gets the curated carousel).
- **Copy drafting (NEW — `content/copy.py`):** LLM-drafts captions/threads from **structured** experiment/prediction/result data (never free-form) → into the Yellow queue. Voice guide + guardrails applied.

### 5h. Approval queue + guardrails (NEW — the 🟡 Yellow tier)
- **Draft store — `publish/queue/`:** pending posts as JSON/parquet: `{id, platform, kind, asset_paths, caption/thread, checks[], status: pending|approved|rejected|posted}`.
- **Automated guardrail checks — `publish/guardrails.py`** (gate every Yellow item): tout-language denylist + LLM check; every stated number reconciles against the source data (no hallucinated stats); required disclaimer present; on-voice check; tragedy/serious-injury screen (keyword + LLM) → route to 🔴; idempotency key.
- **Approval mechanism:** recommended **Telegram/Slack bot** — DMs the rendered asset + drafted copy with ✅/✏️/❌ (approve from phone). Alternative: extend the existing static `content/review.py` page into an interactive dashboard. (Owner's call — master plan §13 TBD; recommendation = bot.)
- **The tighten switch:** an autonomy-mode flag (`AUTONOMY_MODE = approve_all | yellow_auto | ...`) that reverts everything to full human approval in one setting.

### 5i. Publishing layer (NEW — `backend/publish/`)
- **`Publisher` ABC** (mirrors `OddsProvider`): `publish(platform, asset, text) -> PostRef`, `supports(platform)`, `MultiPublisher` fans out. Adapters: `reddit.py` (PRAW), `x.py` (X API v2 + media; threads via reply-chain), `ig.py` (Graph API — pulls media from a **public R2 URL**, so assets stage to R2 first).
- **Idempotency + safety:** store returned `PostRef` (id/url) keyed by draft id → never double-post; per-platform rate-limit backoff; `--dry-run`; a global kill switch.
- **IG interim:** until Meta app-review clears, `ig.py` runs in "approve → post manually" mode (the current behavior), while Reddit/X publish automatically. Flip to full auto when access lands.

### 5j. Orchestration + tiered autonomy (NEW/extended)
- **🟢 Green — GitHub Actions** (extend `nightly_pipeline.yml` / `weekly_retrain.yml`): daily = data refresh → `daily_content.run_day` (predict + lock + render + grade) → **the day's scheduled experiment(s)** (`run_experiment.py` per the cadence in §7) → draft Yellow copy → stage assets to R2 → enqueue drafts. Weekly = the heavy retrain. Deterministic; no judgment.
- **🟡 Yellow — scheduled Claude agent (`backend/agent/`)**: fires on cadence to finalize/sanity-check drafted copy, run the judgment guardrail checks, and decide post-worthiness. In **cautious mode** it just assembles the batch for owner approval; as guardrails prove out, it can auto-approve within limits. Runs via a scheduled remote agent / cron.
- **🔴 Red**: any pipeline or agent anomaly (data source down, model regression, hallucinated-number check fail, tragedy/injury screen hit, implausible pick) → halt that item + escalate to the owner; never auto-post.

### 5k. Storage & secrets (ported + extended)
`utils/storage.py` = R2 (MinIO locally), delta-upload bundles + 20-thread pool. New: stage rendered **public asset URLs** for the IG Graph API. **Secrets** live in **GitHub Actions encrypted secrets**: `CFBD_API_KEY`, `ODDS_API_KEY`, R2 creds, X (consumer+access), Reddit (client+secret+refresh), IG (app id/secret + long-lived token + refresh), the LLM API key for drafting, Telegram/Slack bot token.

### 5l. API & frontend (ported + extended)
`web/app.py` keeps `/api/track-record`; **add `/api/experiments`** (the progression feed: champion-metric history + per-experiment results) so the frontend becomes the public **"changelog"** — the model's climb over time, every experiment listed, wins and duds. `lovable/TrackRecord.tsx` extends into that progression view.

---

## 6. End-to-end flows

**A. Daily green pipeline (GitHub Actions):** ingest/refresh → features → `predict_game` per matchup (market-blind) → `select_best_bets` → `lock_predictions` (SHA-256) → render cards + write reel slate JSON + `render-reel.mjs` → grade yesterday → run the day's scheduled experiment(s) → draft Yellow copy → stage assets to R2 → enqueue drafts → (weekly) retrain.

**B. A single feature experiment:** pop next `queued` from `roadmap.yaml` → build challenger (champion + one builder) → walk-forward backtest champion vs challenger on train+CV seasons → Δ metrics → pre-registered keep/drop → record to `experiments_ledger` → if kept, promote champion (version bump + refit) → emit `ExperimentResult` → feature-post draft.

**C. Approval → publish:** draft enters the Yellow queue → automated guardrail checks (tout/numbers/disclaimer/voice/tragedy) → scheduled agent finalizes / owner approves (cautious mode) → `Publisher` posts to Reddit/X (IG manual-interim) → store `PostRef` (idempotent) → later, `grade` settles the locked pick into the track record.

---

## 7. Cadence & config

- **Experiment cadence** (which sports run an experiment on which days) is config-driven per master plan §7: NFL/CFB ~twice-weekly, NBA/NHL daily, MLB/soccer few-per-week. The Green pipeline reads a cadence config to decide the day's experiments.
- **Key flags:** `MARKET_BLIND` (default True), `AUTONOMY_MODE` (approve_all → yellow_auto), the cadence map, `ROADMAP_PATH`, `CHALK_RASTERIZER`, brand overrides.

---

## 8. Discrepancies to fix on port (from the audit)
1. **Reel not wired** — `reel/render-reel.mjs` expects a slate JSON the Python side never writes. Fix: `daily_content` writes the slate + invokes the reel.
2. **Brand name split** — `brand_config.py` defaults to `HOOPS ORACLE`; `content/brand.json` overrides to `CHALK`. Fix: make CHALK the code default; drop legacy naming.
3. **`betting_venv/` checked in** but not the run env — remove; canonical env is Docker 3.10 + `config/requirements.txt`.
4. **Capabilities vary per sport** — always check `supports(cap)` before calling `predict_player`/`predict_game`/`schedule` (soccer has no player preds; MLB/NHL/soccer aren't in `LiveMarketProvider`).

---

## 9. Open questions / TBD
- **Approval bot vs dashboard** (recommendation: Telegram/Slack bot). → resolved in `CONTENT_SPEC.md` / `OPS_RUNBOOK.md`.
- **LLM for copy drafting** — which model/provider for `content/copy.py` (defaults to the latest Claude). → `CONTENT_SPEC.md`.
- **Champion-version storage** — `champion.json` per sport vs a versioned artifacts table; and how model artifacts are pinned in R2 per version.
- **Exact keep/drop thresholds** per metric/sport — pre-registered in `roadmap.yaml`; tuned during the first NFL rungs.
- **CFBD rate limits at daily scale** — may need the ~$10/mo Patreon tier (master plan §7).

Next Phase-A docs: **`CONTENT_SPEC.md`** (post templates × platform, reel spec, voice guide, guardrail-check spec) → **`OPS_RUNBOOK.md`** (Green/Yellow/Red workflows, escalation, calibration, recovery) → **`BUILD_PLAN.md`** (ordered milestones).
