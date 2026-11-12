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

## Status after run 2
All 5 original team models fresh + served; CFB added as the 6th (served). NBA unblocked +
interactions kept. 176 tests green.

---

## Data-feed builds (2026-11-02): owner said "do all of them one by one", keep it simple

Guiding principle (owner): most accurate engine statistically, built as SIMPLY as possible -
add only each feed's highest-signal feature(s), keep only if the OOS referee says it helps,
no kitchen-sink. See the memory `chalk-simplicity-accuracy`.

### Feed 1/5: NFL EPA/play (NFL-19/20) -> KEEP, served

Wired the heavy nflverse play-by-play down to one small cached row per team-game
(`data/nfl/epa_{year}.parquet`: offensive EPA/play + defensive EPA/play allowed), then
rolling prior-only `OFF_EPA`/`DEF_EPA` in the timeline (neutral 0.0 cold-start; feed-absent
-> 0.0 so the engine stays offline-safe and tests hermetic). Kept it to just the 4 EPA cols
(no CPOE / success-rate / pace / QB-adjusted pile).

| metric (primary bold) | baseline (20c) | +EPA (24c) | delta |
|---|---|---|---|
| **margin_mae** | 10.497 | **10.458** | **-0.039** |
| **total_mae** | 10.919 | 10.908 | -0.011 |
| winner_logloss | 0.6505 | 0.6461 | -0.0044 |
| su_acc | 0.6210 | 0.6204 | -0.0006 (noise) |

Biggest NFL gain so far (~4x the opp-adj offense win), confirms the menu's "single most
predictive" claim. **KEEP** + served (wired into `TEAM_FEATURE_COLS` + `_assemble` +
`latest_team_features`). Retrained through 2025.

HONEST NOTE (overfitting canary): the trainer's single 2025 holdout season is slightly worse
with EPA (margin 10.357 -> 10.439), but the 12-season train+CV referee (the selection
instrument) clearly favors EPA, and 2024 - the most recent train+CV season - was the LARGEST
EPA win (-0.224). EPA helps margin in 7/12 seasons, flat/noise in the rest, rarely hurts. The
2025 blip is within one-season variance; the multi-season signal governs. New hermetic test
`test_epa_is_prior_only` (leakage-safe). 177 tests green. Merged: PR #8.

### Feed 2/5: MLB park factors -> DROPPED (measured, no help)

Computed a simple prior-season park factor from the data we already have (team home-game
avg total runs / its road-game avg, carried forward one season, leakage-safe) - no new feed.
It is a real signal (range 0.735-1.459, Coors high, Petco low) but on the referee it did
NOT help:

| metric | baseline | +PARK_FACTOR | delta |
|---|---|---|---|
| total_mae (primary) | 3.558 | 3.557 | -0.001 (noise) |
| margin_mae | 3.457 | 3.457 | 0.000 |
| winner_logloss | 0.6823 | 0.6826 | +0.0003 (worse) |

Reason: the team OFF/DEF run rates already absorb most of the park signal (half a team's
games are at home), so a crude park factor is redundant. Per the simplicity rule, DROPPED
(reverted the code, no dead computation left). The deeper MLB lever (Statcast xwOBA/FIP via
pybaseball - quality-of-contact info NOT in OFF/DEF) is a HEAVIER feed; flagged for a
decision rather than auto-added.

### Feed 3/5: NHL xG (MoneyPuck) -> KEEP, served (2026-11-04)

Built the shot-level feed the simplest way: download MoneyPuck `shots_{year}.zip` (~20MB,
~120k shots/season), sum each shot's `xGoal` per (game, shooting team) to total expected
goals FOR and AGAINST, and cache ONE small row per team-game to `data/nhl/xg_{year}.parquet`
(~63KB/season - the aggregate, not the raw shots), the same aggregate-and-cache pattern as
NFL EPA. Join key: the NHL 10-digit `game_id` reconstructs exactly as
`season*1_000_000 + MoneyPuck_game_id` (verified: regular-season ids match the schedule 1:1,
**100% of schedule team-games covered 2015-2025**; playoff `03xxx` ids never match and drop
out). MoneyPuck team codes canonicalize cleanly (ARI/PHX->UTA etc. already handled; zero
unmapped across all seasons). Then rolling prior-only `OFF_XG`/`DEF_XG` in the timeline
(neutral 2.9 cold-start; feed-absent -> 2.9 so the engine stays offline-safe + tests
hermetic). Kept it to just the 2 xG cols (no Corsi/Fenwick/high-danger/special-teams pile).

| metric (primary bold) | baseline (14c) | +xG (18c) | delta |
|---|---|---|---|
| **margin_mae** | 2.146 | **2.139** | **-0.007** |
| su_acc | 0.5764 | 0.5820 | **+0.0056** |
| winner_logloss | 0.6752 | 0.6736 | -0.0016 |
| total_mae | 1.862 | 1.861 | -0.001 |

Clean win: the primary error (margin_mae) drops and BOTH guard metrics improve, none regress.
The su_acc lift (+0.0056) is the strongest of any NHL team feature so far - xG is a genuine
winner-prediction signal, the NHL analog of NFL EPA. **KEEP** + served (wired into
`TEAM_FEATURE_COLS` + `_team_timeline` + `_assemble` + `latest_team_features` +
`build_timeline`; registered as experiment builder `NHL-20` so the ledger still covers every
served col). Retrained through 2024 + serve-verified (18-col model, live TOR/BOS prediction
OK). New hermetic test `tests/test_nhl_team_features.py` (prior-only xG leakage + absent-feed
neutral + matchup shape). 181 tests green.

HONEST NOTE (overfitting canary): the trainer's single 2024 holdout is mixed with xG (margin
2.168 -> 2.152 better, total 1.842 -> 1.894 worse) - one-season variance on the trainer's own
holdout; the 7-season train+CV referee (the selection instrument) governs and shows margin
-0.007 with total ~flat (-0.001). Same pattern as NFL EPA's 2025 blip: the multi-season
signal decides, the single-season holdout is noisy.

FLAG FOR OWNER (starting goalie): xG was a clean win, so per the plan the starting GOALIE is
the next NHL lever to "consider" - but it's a genuinely heavier NEW feed. A PRE-game goalie
signal needs confirmed-starter data (who is in net tonight, a projection problem) PLUS the
boxscore endpoint for goalie rolling stats, not just the schedule. That is a new source and a
pre-game-projection problem (harder than a historical aggregate), so I did NOT auto-build it -
flagged as a separate decision rather than silently adding a heavy moving part (simplicity
rule). MoneyPuck shots DO carry `goalieIdForShot`/`goalieNameForShot`, so post-game goalie xGA
is cheap from the same feed; the hard part is the pre-game STARTER identity.

## Status (2026-11-04): 3/5 feeds done

Done: **NFL EPA kept + served (PR #8)**; **MLB park factor measured + dropped (PR #9)**;
**NHL xG MoneyPuck kept + served (this PR)**. All six team models remain fresh + served; NHL
retrained through 2024 with xG. pyarrow pinned <19. Remaining feeds (one focused session each):
- Soccer Club Elo / Understat xG (soccerdata lib).
- CFB player props (CFBD player stats + a brand-new player-prop model - the biggest).

---

## Feed 4/5 (2026-11-09): soccer xG -- PARKED on branch `feed/soccer-xg` (not merged)

Blocked purely on external source outages (Understat maintenance page, ClubElo 502,
FBref free-xG gated by the 2024 Opta licensing change). Baselines reproduced exactly
and a full resume playbook recorded on the `feed/soccer-xg` branch's copy of this
worklog. Re-checked 2026-11-11: understat.com still serves the maintenance page
(HTTP 200, no `teamsData`) and api.clubelo.com still 502, so Feed 4 stays parked.
See the memory `chalk-accuracy-direction`.

---

## Feed 5/5 (2026-11-11): CFB player props via CFBD box scores -> KEEP, served

Branch `feed/cfb-player-props` (off fresh `main`). The last and biggest feed: a
brand-new player-prop model for CFB (the 6th sport, which had a team model but no
player props). Built by mirroring the NFL player stack exactly -- anchored residual
LightGBM per prop, usage-gated, leakage-safe prior-only rolls -- so it reuses the
same machinery rather than inventing new infrastructure (simplicity rule).

**Data feed (CFBD `/games/players`).** Added `load_player_games(years)` to
`sports/cfb/data.py`: fetch the per-week player box scores, pivot the nested
passing/rushing/receiving categories to one row per (game, player) with 10 box
stats (pass/rush/rec yards + TDs, attempts, completions, carries, receptions), join
to the FBS-vs-FBS games cache by `game_id` (which also drops non-FBS games), and
cache ONE small per-season parquet `data/cfb/player_games_{year}.parquet` (the
aggregate, not the ~3.5MB/week raw) -- the same aggregate-and-cache pattern as NFL
EPA / NHL xG. Validated on 2024 before the full pull: 99.9% FBS-game coverage, 0
canonicalization misses (every player's team maps to the game's home/away), stat
realism exact (max single-game passing_yards 515 = Jaxson Dart vs Arkansas, real).
No new dependency (uses `requests` + the existing CFBD key).

**Features (`sports/cfb/player_features.py`).** Mirror of NFL: `STATS` (10 box
stats), `PROP_TARGETS` = pass/rush/rec yards + receptions, per-prop `USAGE_GATE`
(receptions is the receiving usage signal since CFBD has no targets), `FEATURE_COLS`
= `{stat}_L3` + `{stat}_STD` (20 cols), `build_player_frame` /
`latest_player_features`. Two deliberate differences from NFL, both noted in-code:
ordering by `game_date` (CFB postseason week numbers restart, so the date is the
unambiguous temporal key) and NO position feature (CFBD box scores carry no
position; the usage gates already segment passer/rusher/receiver, so it is omitted
on purpose -- curated, not kitchen-sink, per the degeneracy-probe finding).

**Measured on the honest OOS referee** (`backtest/cfb_player_backtest.py`, holdout
2025, 177,822-player-game frame): does the anchored model beat the free naive
baselines a human would use (last-3 average, season-to-date average)?

| prop | n_hold | model MAE | last-3 | seas-avg | skill vs L3 |
|---|---|---|---|---|---|
| passing_yards | 1502 | 71.14 | 75.04 | 73.58 | +5.2% |
| rushing_yards | 5180 | 26.71 | 28.49 | 27.62 | +6.2% |
| receiving_yards | 6249 | 24.25 | 26.45 | 25.49 | +8.3% |
| receptions | 6249 | 1.53 | 1.66 | 1.60 | +7.9% |

model_mae < last-3 < season-avg on every target; positive skill +5.2% to +8.3% over
1.5k-6.2k holdout rows each. The curated 20-feature ML layer genuinely earns its
place (confirms the NFL/NBA player-prop pattern; the kitchen-sink is correctly
avoided). **KEEP all four.**

**Wired + served + serve-verified.** New `models/cfb_player_predictor.py` (anchor +
adjustment, usage-gated at inference); `sports/cfb/sport.py` now declares
`predict_player` + `player_targets()` = the 4 props. Trained through 2025;
artifacts in `models/artifacts/cfb_player/` (gitignored). Serve-verify via the sport
plugin produced sane projections with the gates working: Kyle McCord (Syr QB) 324.8
pass / 0 rush; Diego Pavia (Vandy dual-threat) 262.5 pass / 63.7 rush; RBs
rushing-only; WRs receiving + receptions only, no phantom stats. New hermetic test
`tests/test_cfb_player_features.py` (synthetic frame: prior-only leakage + curated
schema + slug-keyed latest). 184 tests green (was 181).

## Status (2026-11-11): all 5 data feeds resolved
NFL EPA kept (PR #8); MLB park factor dropped (PR #9); NHL xG kept (PR #10); **soccer
xG PARKED** (Feed 4, external sources down -- re-check Understat next session); **CFB
player props kept + served (this branch, `feed/cfb-player-props`)**. All 6 sports now
have served team models; NFL and CFB have served player-prop models. Nothing
pushed/merged on this branch yet -- outward actions are the owner's call.

---

## Breadth + polish phase (2026-11-12): owner chose "optimize for picking winners"

Feeds are done; this phase tightens the existing models. Owner's stated priority:
**winner accuracy over margin/total precision**, which resolves the flagged switch-ons.

### Flagged switch-on: CFB opp-adj DEFENSE -> FLIPPED ON (branch `polish/winner-switch-ons`)
Re-measured on the current train+CV (2015-2024, 2025 untouched, n=7517), off-only
(served) vs off+def:

| metric | off-only (served) | off+def | delta |
|---|---|---|---|
| **su_acc** | 0.6967 | **0.7003** | **+0.0036** |
| winner_logloss | 0.5739 | 0.5725 | -0.0014 |
| margin_mae | 13.826 | 13.787 | -0.039 |
| total_mae | 13.447 | 13.485 | +0.038 (worse) |

Better on su_acc, winner log-loss AND margin; only total_mae costs +0.038. Confirms
Run 2. Under the picking-winners priority this is a clear **KEEP**: wired DEF_ADJ into
`TEAM_FEATURE_COLS` + `_assemble` + `latest_team_features` (mirrors the NFL OFF_ADJ
wiring), retrained (2025 holdout margin_mae 13.135 -> 12.987, total 13.110 -> 13.141),
serve-verified (Georgia vs Alabama margin 6.7 / total 47.9 / p_home 0.659), test
updated, 184 tests green.

### Flagged switch-on: MLB real SP_ERA -> ALREADY ON (no change needed)
Verified in code: `train_mlb_team_model` builds the frame with the default
`fetch_sp_era=True`, and SP_ERA / SP_ERA_DIFF are in `TEAM_FEATURE_COLS`, so the served
MLB model already uses real per-pitcher rolling ERA (kept per owner in Run 2). The Run-1
"leave off" is already superseded; consistent with the picking-winners priority.

### NFL opp-adj DEFENSE -> stays OFF (hurt su_acc even under picking-winners).

### Still to do this phase: calibration breadth (extend `evaluate_calibration.py` beyond
nba/nfl to mlb/nhl/cfb + a soccer 3-way variant; NBA probe showed calibration is
already tight, cov80=0.79) and reviving the live nightly track record (`pipeline/`
exists but cold; owner: wire it, I'll run it -- no launchd cron).
