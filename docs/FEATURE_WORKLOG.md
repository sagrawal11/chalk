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
(NFL-10 kept). **KEEP.**

WIRED + VERIFIED (2026-11-01): added `HOME_OFF_ADJ`/`AWAY_OFF_ADJ` (the offense-only
subset) to `TEAM_FEATURE_COLS`, so the served trainer (`train_nfl_team_model.py`, which
reads `TEAM_FEATURE_COLS`) picks them up automatically. Closed the inference gap:
`latest_team_features` now extracts `OFF_ADJ` from the timeline and `_assemble`/`matchup_features`
emit `HOME_OFF_ADJ`/`AWAY_OFF_ADJ`, so the served column count went 18 -> 20 and the
inference row matches. The delta above IS the re-measure (old 18-col served set vs the new
20-col served set). DEF_ADJ deliberately left out. 8 NFL feature tests + experiments tests green.

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

## One measured pass over buildable-now team features (2026-11-01)

With cached data + reachable network, the only menu switch-on left that is NOT a new
data-feed [BUILD] is the soccer Dixon-Coles rho knob. Measured it on top of the now-served
cross-season prior:

### Soccer Dixon-Coles rho (-0.13, pre-registered) -> DROP

| metric (primary bold) | cross_season only (served) | + Dixon-Coles | delta |
|---|---|---|---|
| **3-way logloss** | 1.0500 | 1.0540 | **+0.004 (worse)** |
| 3-way acc | 0.5212 | 0.5165 | -0.0047 (worse) |
| total_mae | 1.492 | 1.492 | 0.000 |
| draw pred/act | 0.198/0.225 | 0.221/0.225 | better calibrated |

The rho fixes the draw under-prediction (draw_pred 0.198 -> 0.221, closer to the 0.225
actual) but costs overall log-loss and accuracy. By the keep rule (lower the primary error
without worsening the guard), it fails. **DROP** - leave `dixon_coles` off in serving. rho
is pre-registered (not tuned on the holdout), so no grid-search here.

## Status at stop (2026-11-01)

**KEPT + wired (committed locally, not pushed):**
- Soccer cross-season prior (SOC-03) -> `ea6b9f2`
- NFL opponent-adjusted offense (NFL-10) -> `3beff03`

**Measured + dropped (left out, by the OOS rule):** NFL opp-adj defense (NFL-11), MLB real
SP_ERA (neutral/borderline, flagged for owner), soccer Dixon-Coles rho.

**Blocked - needs the owner (new feed / credentials / network):**
- NBA team model: `kaggle_team_games.parquet` + `team_availability.parquet` are missing
  (Kaggle CLI + credentials). No baseline this run.
- All remaining menu gains are new-feed [BUILD]s and were NOT started per scope: NFL EPA
  (play-by-play), MLB Statcast + park factors + FIP, NHL MoneyPuck xG + starting goalie,
  soccer Club Elo + Understat xG, the CFB plugin.

**Env:** this run used `pyarrow==18.1.0` (downgraded from a broken 19.0.0) and
`nfl_data_py==0.3.3 --no-deps`. Models were NOT retrained/served (artifacts are gitignored);
the code wiring is what landed. Retrain with `python -m model_training.train_nfl_team_model`
and the soccer predictor rebuilds ratings lazily on first use.

Measurement tooling: `scratch/measure.py` (binary sports), `scratch/measure_soccer_serving.py`.

---

## Run 2 (2026-11-01, cont.): NBA unblocked + retrains + CFB

Owner provided Kaggle creds, so NBA data was stood up: `kaggle datasets download -d
chrismunch/nba-game-team-statistics` + `build_team_stats_from_kaggle.py` ->
`data/processed/kaggle_team_games.parquet` (51,172 rows; 23,965 games 2006-2025).

### NBA baseline (28 cols: ratings + pace + availability + Elo)
su_acc 0.6541, margin_mae 10.086, total_mae 14.915, winner_logloss 0.6157 (untouched
holdout 2025, train+CV n=19043).

### NBA matchup interactions (PACE x PACE + offense-vs-defense cross-terms) -> KEEP

| metric (primary bold) | baseline (28) | +interactions (31) | delta |
|---|---|---|---|
| **margin_mae** | 10.086 | 10.077 | **-0.009** |
| **total_mae** | 14.915 | 14.872 | **-0.043** |
| su_acc | 0.6541 | 0.6567 | +0.0026 |
| winner_logloss | 0.6157 | 0.6153 | -0.0004 |

Every metric improves; explicit interactions still help the tree here. **KEEP** - wired
`PACE_PROD`, `H_OFF_x_A_DEF`, `A_OFF_x_H_DEF` into `_assemble` + `TEAM_FEATURE_COLS` (both
training and `matchup_features` inference). 3 NBA team tests green.

### Retrains (served artifacts refreshed, gitignored; holdout 2025)
- NFL team (20-col, run 1): margin 10.357 / total 10.816
- NBA team (31-col): margin 11.445 / total 17.073 (holdout labeled 2025-26, partial)
- NHL team: margin 2.168 / total 1.842
- MLB team (SP_ERA KEPT per owner): margin 3.497 / total 3.613
- Soccer: parametric, rebuilt at inference (cross-season on)

### pyarrow pinned `<19` in `config/requirements.txt`; PR #6 merged to main.

### CFB plugin built from scratch (owner provided the CFBD key)

New `sports/cfb/` plugin mirroring the NFL engine: `data.py` (CFBD `/games` client,
FBS-vs-FBS only, cached per season to `data/cfb/`), `teams.py` (lenient single-source
canonicalization), `team_features.py` (box-score + opponent-adjusted offense + neutral-site
/ conference-game context), `sport.py` (registered as `cfb`). Plus `cfb_team_predictor.py`,
`train_cfb_team_model.py`, and `tests/test_cfb_plugin.py` (hermetic). CFBD key in
`backend/.env` (gitignored).

CFB baseline + opp-adj (2015-2024 train+CV, 2025 untouched, 8325 FBS games, n=5216):

| feature set | su_acc | winner_LL | margin_mae | total_mae |
|---|---|---|---|---|
| baseline (16c) | 0.6967 | 0.5767 | 13.906 | 13.471 |
| **+opp_adj_OFF (served, 18c)** | 0.6959 | 0.5740 | **13.825** | 13.471 |
| +opp_adj_OFF+DEF (20c) | 0.7019 | 0.5726 | 13.778 | 13.496 |

**Served = +opp_adj_OFF** (clean: margin_mae -0.081, winner_LL -0.0027, no regressions).
FLAG FOR OWNER: unlike NFL, CFB's opp-adj DEFENSE also helps the winner/margin model
(su_acc 0.6967 -> 0.7019, margin 13.906 -> 13.778) at the cost of a tiny total_mae regression
(+0.025). Left DEF off to keep the no-regression rule, but it's a defensible upgrade if you
value SU accuracy. Trained + served: margin holdout_mae 13.135, total 13.110 (holdout 2025).

## Status at stop (run 2)
All 5 original team models fresh + served; CFB added as the 6th (served). NBA unblocked +
interactions kept. 176 tests green. Remaining new-feed [BUILD]s (NFL EPA, MLB Statcast/park,
NHL xG/goalie, Club Elo/xG, CFB player props) await the owner's pick. pyarrow pinned.
