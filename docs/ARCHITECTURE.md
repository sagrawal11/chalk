# CHALK Architecture

Companion to `FEATURE_ROADMAP.md`. This describes the architecture of the `chalk` repo: a backend modeling core that predicts players and teams from their own features and grades those predictions against real results. The descriptions cite real modules in the repo. (The outward-facing surfaces, a frontend, a reel, a content renderer, a social-posting pipeline, and a web API, are deferred to the `archive/outward-facing` branch and are not part of the current architecture; the earlier planning docs that covered them live under `docs/archive/`.)

---

## 1. Design principles

1. Port the infra, start the model simple. The data adapters, feature machinery, eval harness, track record, storage, and CI all come over mature, but each sport's champion model starts at its Rung-1 baseline and climbs the roadmap. Feature-builders exist in code from day one and toggle on progressively via the champion config, so adding a feature is a config change plus a retrain, not new code each time.
2. Extend the existing eval harness, don't rebuild it. The walk-forward backtest (`backtest/team_backtest.py`) and training CV (`model_training/validation.py`) already produce honest OOS accuracy, log-loss, and MAE. The experiment harness orchestrates them; it doesn't reinvent evaluation.
3. Honesty is enforced in code. Leakage guards, the untouched test set, the immutable SHA-256 slate lock, and the walk-forward-only selection rule are all real code gates.

---

## 2. System overview

```
                         ┌──────────────── ORCHESTRATION ────────────────┐
                         │  GitHub Actions (🟢 nightly + weekly retrain)  │
                         └───────────────────────┬────────────────────────┘
                                                 │ drives
  DATA              FEATURES              MODEL / EXPERIMENT              PREDICT
 ┌───────┐        ┌──────────┐          ┌───────────────────┐          ┌───────────┐
 │ sport │───────▶│ feature  │─────────▶│ champion/challenger│─────────▶│ predict_  │
 │ data  │        │ engine + │          │ + walk-forward     │          │ game →    │
 │ adapt.│        │ leakage  │          │ EXPERIMENT HARNESS │          │ winner +  │
 └───┬───┘        │ guards   │          │   (the core)       │          │ score     │
     │            └──────────┘          └─────────┬──────────┘          └─────┬─────┘
     │                                            │ Δmetrics                   │ preds
     ▼                                            ▼                            ▼
  R2/MinIO  ◀──────────── experiments_ledger + champion versions + LOCK (SHA-256) ──▶ track_record (grade → aggregate)
```

Cross-cutting: R2/MinIO (artifacts, bundles), config/flags (cadence, roadmap path), and secrets (GitHub Actions).

---

## 3. Repo structure

| Area | Path | Notes |
|---|---|---|
| Sport plugin core | `backend/sports/` (`base.py` ABC + per-sport) | Six sports; players and teams. |
| Feature engine | `backend/feature_engine.py`, `sports/*/team_features.py` | Feature-builders gated by champion config (see §5d). |
| Model trainers | `backend/model_training/`, `backend/models/` | Champions start at Rung-1; climb via experiments. |
| Eval harness | `backend/backtest/`, `model_training/validation.py` | Reused by the experiment harness. |
| Experiment harness | `backend/experiments/` | Roadmap-as-data + champion/challenger runner + ledger (§5d). |
| Track record | `backend/track_record/` | Lock, grade, aggregate, SHA-256. |
| Data collection | `backend/data_collection/` | Injury/availability/DvP/log collectors feeding features. |
| Storage | `backend/utils/storage.py` | R2 (MinIO locally); delta-upload bundles. |
| Config | `backend/config/` | Settings, paths, cadence, roadmap path. |
| Orchestration | `.github/workflows/`, `backend/pipeline/nightly.py` | Nightly data+model pipeline + weekly retrain + CI. |
| Infra | `docker-compose.yml`, `Makefile`, `config/requirements.txt`, `tests/` | Canonical env is Docker 3.10. |

---

## 4. The sport plugin core

`backend/sports/base.py` is the `Sport` ABC plus a lazy registry (`get_sport(key)` instantiates and caches; heavy imports deferred). Each sport implements `canonical_team`, `current_season`, `season_from_date`, `player_targets`, `team_targets`, `score_ranges`, and (as capable) `predict_game`, `predict_player`, `schedule`; it declares `capabilities` and answers `supports(cap)`.

Per-sport package shape (proven by `sports/nba/` and `sports/nfl/`): `teams.py` (canonical identity + aliases + season bridge), `data.py`/`*_data.py` (the free-feed adapter), `team_features.py` (and `player_features.py`), `geo.py` (travel/altitude), `sport.py` (the thin adapter wiring predictors + schedule).

---

## 5. Component detail

### 5a. Data pipeline per sport
Each sport's `data.py` fetches its free feed (NFL nflverse, NBA Kaggle+SQLite+B-Ref logs, MLB StatsAPI+Statcast, NHL API+MoneyPuck, soccer football-data/Understat, CFB CFBD). Immutable historical parquets are cached; the current season is refetched live. Unofficial APIs are wrapped with retries and graceful skips (the `nightly.py` step pattern).

### 5b. Feature engineering + leakage discipline
`feature_engine.py` (players) and `sports/*/team_features.py` (teams) enforce the discipline the whole project rests on: `shift(1)` before every rolling window, `merge_asof(direction="backward", allow_exact_matches=False)` for all prior-state joins, expanding-mean opponent priors, a strict output whitelist dropping same-game leaky columns, and train/serve parity via `split_features_targets()` (one source of truth for columns; a mismatch logs loudly). Individual feature-builders (rolling form, opponent adjustment, Elo, availability `TM_OUT_*`, EPA/xG, and so on) are the roadmap rungs; see §5d for how they toggle on.

### 5c. Model & prediction
`model_training/train_team_model.py` trains two LightGBM regressors (margin + total) via `walk_forward_train`, each with a robust residual σ (`1.2533·holdout_mae`). `models/team_predictor.py::predict_game()` produces μ/σ for margin and total, then `p_home_win`, `home_pts`, `away_pts`, and a `GamePrediction`. Each prediction is the pure-model output from the team's own features. Soccer is Poisson/Dixon-Coles (3-way with a real P(draw)).

### 5d. The feature-experiment harness: `backend/experiments/`
This operationalizes "add one feature, measure what it did, record it, decide." It is an orchestration layer over the existing eval harness plus a ledger and model-versioning.

Roadmap-as-data (`experiments/roadmap.yaml`): a machine-readable port of `FEATURE_ROADMAP.md`, an ordered list of experiments, each `{id: NFL-06, sport: nfl, rung: 2, name, builder: <feature-builder key(s)>, hypothesis, eval_metric, status: queued}`. Order is the prioritized queue (held loosely, since status can be reordered). This is the single source that ties the roadmap to the runner to the results.

Champion / challenger: each sport has a champion = `{model_version, active_feature_builders[], cumulative_metrics}` stored at `artifacts/<sport>/champion.json`. An experiment builds a challenger = the champion's active builders plus this rung's builder. Because feature-builders are individually toggleable (§5b), a challenger is a config diff, not new code.

The runner (`experiments/run_experiment.py`):
1. Pop the next `queued` experiment (or a given id).
2. Assemble the challenger feature set (champion + this builder).
3. Run the existing `backtest/team_backtest.py::walk_forward_backtest` for champion and challenger over the train+CV seasons only (the final season stays untouched). Cache champion metrics so only the challenger reruns.
4. Compute Δ metrics (Δ accuracy, Δ log-loss, Δ MAE/score-MAE; for soccer Δ 3-way log-loss) with the eval window and N.
5. Decide by pre-registered rule (for example, keep if Δ log-loss improves beyond a fixed threshold on walk-forward OOS; else drop or park). Record to the ledger regardless of outcome.
6. If kept, promote the challenger to new champion (bump `model_version`, e.g. `nfl-v3→nfl-v4`; refit the shipped model on all data at the validated config via `walk_forward_train`).

Experiment ledger (`data/experiments_ledger.parquet`): one row per experiment, `{id, sport, run_at, champion_version, challenger_version, delta_accuracy, delta_logloss, delta_mae, n_games, eval_window, decision, notes}`. The "accuracy climbing" view is the champion-metric history over this ledger.

Overfitting and honesty guards (baked in):
- The final untouched test set is never used for keep/drop selection. A separate, infrequent `experiments/honest_readout.py` evaluates the current champion on it, that's the honest headline number, and the gap between walk-forward-selected and untouched-test performance is itself a monitored signal of overfitting.
- Pre-registered thresholds (decided before the result is seen) plus the pre-committed `roadmap.yaml` order.
- Cumulative multiple-comparisons exposure is tracked (how many experiments run vs. kept) and reported.
- Walk-forward OOS deltas only, never in-sample fit.

### 5e. Track record
`track_record/` locks, grades, then aggregates: `lock.py` writes the immutable SHA-256-hashed slate before tip; `grade.py` grades vs real finals into `results_ledger.parquet` (winner correct/incorrect plus per-side score error, no lines or odds); `aggregate.py::headline()` serves record/win%/streak/score-MAE with winner accuracy as the hero. `seed_writer.py` seeds a day-one honest record from the walk-forward backtest.

### 5f. Storage & secrets
`utils/storage.py` is R2 (MinIO locally), with delta-upload bundles and a 20-thread pool. Secrets live in GitHub Actions encrypted secrets: `CFBD_API_KEY` and R2 creds.

### 5g. Orchestration
🟢 GitHub Actions (`nightly_pipeline.yml` / `weekly_retrain.yml`, driving `backend/pipeline/nightly.py`): nightly is data refresh, then feature rebuild, then the day's scheduled experiment(s) (`run_experiment.py` per the cadence in §7), then grade yesterday's locked slate and upload artifacts. Weekly is the heavy retrain. Deterministic, no judgment. `ci.yml` runs lint, type-check, and tests for these modules.

---

## 6. End-to-end flows

A. Nightly pipeline (GitHub Actions): ingest/refresh, rebuild features, `predict_game` per matchup, `lock_predictions` (SHA-256), grade yesterday, run the day's scheduled experiment(s), upload artifacts, and (weekly) retrain.

B. A single feature experiment: pop the next `queued` from `roadmap.yaml`, build the challenger (champion + one builder), walk-forward backtest champion vs challenger on train+CV seasons, compute Δ metrics, apply the pre-registered keep/drop, record to `experiments_ledger`, and if kept promote the champion (version bump + refit).

---

## 7. Cadence & config

- Experiment cadence (which sports run an experiment on which days) is config-driven: NFL/CFB roughly twice-weekly, NBA/NHL daily, MLB/soccer a few per week. The nightly pipeline reads a cadence config to decide the day's experiments.
- Key flags: the cadence map, `ROADMAP_PATH`, and brand overrides.

---

## 8. Discrepancies to fix on port (from the audit)
1. `betting_venv/` checked in but not the run env: remove it, since the canonical env is Docker 3.10 + `config/requirements.txt`.
2. Capabilities vary per sport: always check `supports(cap)` before calling `predict_player`/`predict_game`/`schedule` (soccer has no player preds).

---

## 9. Open questions / TBD
- Champion-version storage: `champion.json` per sport vs a versioned artifacts table, and how model artifacts are pinned in R2 per version.
- Exact keep/drop thresholds per metric/sport: pre-registered in `roadmap.yaml`, tuned during the first NFL rungs.
- CFBD rate limits at daily scale: may need the roughly $10/mo Patreon tier.

Companion docs: `FEATURE_ROADMAP.md` (the rung-by-rung feature ladder), `OPS_RUNBOOK.md` (pipeline recovery and calibration), and `DATA_SOURCES.md` (per-sport feeds).
