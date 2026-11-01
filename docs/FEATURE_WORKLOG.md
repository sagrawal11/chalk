# CHALK Feature Worklog

The running record of the accuracy loop: every measured change, before → after on the
honest out-of-sample referee, and whether it was kept or dropped and why. This is the
durable state a resumed session reads first. See `docs/FEATURE_MENU.md` for the candidate
inventory and the memories `chalk-accuracy-direction` / `chalk-autonomous-loop-guardrails`
for the rules.

## The referee

`backtest/team_backtest.walk_forward_backtest` over TRAIN+CV seasons only, with the
most-recent full season held UNTOUCHED (never in a keep/drop decision). Deterministic
(seed 42, single thread). Binary-margin sports report su_acc / winner_logloss /
margin_mae / total_mae; soccer uses the 3-way path (`backtest/soccer_backtest`) reporting
three_way_logloss / three_way_acc / total_mae. Keep a feature only if it lowers the
primary error (margin/total MAE, or 3-way logloss) without worsening the guard metric
(su_acc / winner_logloss). Measurement window and tooling: `scratch/measure.py`.

## Environment note (this run, 2026-11-01)

Local env had `pyarrow==19.0.0`, which cannot read the repo's cached parquets
("Repetition level histogram size mismatch", a known 19.0.0 regression). Downgraded to
`pyarrow==18.1.0` (satisfies the repo pin `pyarrow>=14`); all caches read again. Installed
`nfl_data_py==0.3.3 --no-deps` per `config/requirements.txt`. Network reachable
(football-data.co.uk, nflverse, statsapi.mlb.com all up).

---

## Task #9: honest baselines (2026-11-01)

Established on the untouched-holdout referee. Data availability this run:

| Sport | Data source | Status | Window | Holdout |
|---|---|---|---|---|
| Soccer | football-data EPL (cached 2021-24) | measured | 2021-2024 | n/a (per-season WF) |
| NFL | nflverse (live) | measured | 2010-2025 | 2025 |
| NHL | schedule parquets (cached 2015-25) | measured | 2015-2025 | 2025 |
| MLB | schedule + pitcher_starts (cached 2015-25) | measured | 2015-2025 | 2025 |
| NBA | Kaggle parquet | BLOCKED (file missing) | - | - |

**NBA is blocked:** `data/processed/kaggle_team_games.parquet` and
`data/auxiliary/team_availability.parquet` are both absent. Rebuilding them needs the
Kaggle CLI + credentials (a new-feed/credentials stop per the guardrails). Left for the
owner to decide.

Baseline numbers (train+CV OOS, served feature set):

| Sport | primary | guard | detail |
|---|---|---|---|
| **Soccer** (cross_season OFF) | 3way_logloss **1.1383** | 3way_acc 0.4969 | total_mae 1.619, n=1274 |
| **NFL** | margin_mae **10.517**, total_mae 10.915 | su_acc 0.6207, winner_LL 0.6509 | n=3277, 12 seasons |
| **NHL** | margin_mae **2.146**, total_mae 1.862 | su_acc 0.5764, winner_LL 0.6752 | n=8469, 7 seasons |
| **MLB** (no real SP_ERA) | margin_mae **3.454**, total_mae 3.558 | su_acc 0.5647, winner_LL 0.6824 | n=15557, 7 seasons |

---

## Switch-on reconciliation (2026-11-01)

### Soccer CROSS-SEASON prior (SOC-03) -> KEEP, wire into served model

| metric (primary bold) | cross_season OFF (baseline) | cross_season ON | delta |
|---|---|---|---|
| **3-way logloss** | 1.1383 | **1.0500** | **-0.0883** |
| 3-way acc | 0.4969 | 0.5212 | +0.0243 |
| total_mae | 1.619 | 1.492 | -0.127 |
| draw calibration (pred/act) | 0.196/0.225 | 0.198/0.225 | ~same |

Clean win on every metric, confirms the ledger champion `soccer-v2`. **KEEP.**

WIRED + VERIFIED (2026-11-01): the served predictor uses `latest_team_ratings`, a separate
estimator the standard backtest never exercises (the drift the memory warned about). Added
an opt-in `cross_season` blend to `latest_team_ratings` (mirrors `_blend_prior_season`'s
PRIOR_K math, default off so all existing tests hold) and turned it on in
`models/soccer_predictor.py`. Measured on the SERVING estimator itself with a production-
simulating walk-forward (ratings from strictly-prior matches per match,
`scratch/measure_soccer_serving.py`) over 2022-2024, identical gated set n=956:

| metric | serving OFF | serving ON | delta |
|---|---|---|---|
| 3-way logloss | 1.1336 | **1.0579** | **-0.0757** |
| 3-way acc | 0.5021 | 0.5262 | +0.0241 |

Confirms the win lands on the served path, not just the backtest path. 24 soccer tests green.

### NFL opponent-adjusted OFFENSE (NFL-10) -> KEEP, wire into served model

| metric (primary bold) | baseline (served) | +opp_adj_OFF | delta |
|---|---|---|---|
| **margin_mae** | 10.517 | **10.508** | **-0.009** |
| **total_mae** | 10.915 | 10.913 | -0.002 |
| su_acc | 0.6207 | 0.6225 | +0.0018 |
| winner_logloss | 0.6509 | 0.6502 | -0.0007 |

Marginal but every metric moves the right way and none regress. Confirms the ledger
(NFL-10 kept). **KEEP.** Action: add `HOME_OFF_ADJ`/`AWAY_OFF_ADJ` to the served trainer's
feature set + the inference path (`latest_team_features` + `matchup_features`).

### NFL opponent-adjusted DEFENSE (NFL-11) -> DROP

Adding DEF on top of OFF: su_acc 0.6225 -> 0.6164 (**-0.0061**, guard worsens), margin_mae
flat. Confirms the ledger drop. **Leave DEFENSE off.**

### MLB real SP_ERA (honest re-test with per-pitcher backfill) -> LEAVE OFF

The ledger dropped SP_ERA; the memory flagged it as possibly mis-measured on a
league-average fill. Re-tested with the real per-pitcher rolling ERA (the cached
`pitcher_starts` parquets already carry ER/IP, so no network needed):

| metric (primary bold) | no SP_ERA | +SP_ERA (real) | delta |
|---|---|---|---|
| **margin_mae** | 3.454 | 3.457 | **+0.003 (worse)** |
| **total_mae** | 3.558 | 3.558 | 0.000 |
| su_acc | 0.5647 | 0.5671 | +0.0024 |
| winner_logloss | 0.6824 | 0.6823 | -0.0001 |

Mixed and marginal: real SP_ERA nudges winner accuracy up (+0.0024) but the primary error
(margin_mae) ticks the wrong way (+0.003). By the keep rule (must lower the primary error),
this is **not a keep** - the honest re-test CONFIRMS the ledger's drop rather than
overturning it. (Sanity-check: with the league-avg fill, SP_ERA is a constant and the delta
is exactly 0.000 on every metric, which is why the original climb saw nothing.)
FLAG FOR OWNER: the small su_acc gain is real; if winner accuracy is valued over margin MAE
for MLB, this is a borderline keep worth a second look.

---

## Pending this run
- Wire soccer cross_season into served predictor + verify.
- Wire NFL opp_adj_OFF into served trainer + inference + verify.
- One measured pass over already-buildable team features (NBA blocked; NFL/NHL/MLB base
  sets already validated above as the current best buildable-now sets).
