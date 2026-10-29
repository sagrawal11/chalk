# CHALK: Feature Roadmap (the pre-committed research plan)

> **Held loosely (per master plan §5):** the order is a prioritized queue, not an immutable script. When a feature does nothing or hurts, the next pick can honestly respond ("that didn't work, so next we try…").
>
> **Every rung maps to a real, available free-data field.** No aspirational features, each was grounded by reading the existing sport plugins + `DATA_SOURCES.md`, or (for CFB) the verified CollegeFootballData.com schema.

---

## How to read this

Each sport has a **data-availability audit** (the free dataset + the exact fields it exposes) followed by a **feature ladder** (~30–45 rungs in climb order). Every rung uses this format:

```
#### <SPORT>-NN · <feature name>   (Rung N, <rung name>)
- Data field / source: <exact field(s), from the plugin / dataset>
- Hypothesis: <what signal this feature may capture>
- Impact measured: <walk-forward metric + window, vs the prior model>
```

### The rung ladder (shared across sports)

1. **Basic box stats**: the deliberately-simple day-1 baseline
2. **Rolling windows**: last-N form, recency-weighted
3. **Opponent adjustment**: strength of schedule, opponent-allowed
4. **Rest / schedule / travel**
5. **Derived efficiency stats**: per-possession / pace-adjusted / sport-specific advanced
6. **Matchup & interaction features**
7. **Situational**: home/road, motivation, rest/tanking spots
8. **Availability & personnel**: injuries, confirmed lineups, starter/goalie/QB changes, coaching/referee tendency

### Methodology & discipline (applies to every feature)

- **Leakage-safe construction:** prior-only rolling features (`shift(1)`), backward-exclusive as-of merges, walk-forward training/eval. No feature ever sees the game it predicts.
- **Champion vs challenger:** a champion model climbs this pre-committed ladder. Each candidate feature runs as a challenger, added on top of the current champion, and is measured walk-forward and out-of-sample on historical results: Δ accuracy / Δ log-loss / Δ Brier / score MAE vs the immediately-prior model, over the seasons the data covers. A challenger that beats the champion is promoted; one that does nothing or hurts is reported as such and dropped.
- **Multiple-comparisons guard:** this pre-registered roadmap + a **final untouched test set** (never used for feature selection) + honest effect sizes with the eval window stated.
- **Team targets only** (winner / margin / total / (for soccer) 1X2 & goals), graded against real results. Player props can be modeled but are out of scope here. Team-outcome backtesting is fully feasible for all six.
- **Every result published honestly:** help, nothing, or hurt. There is no to-beat number and no outside reference, a feature is judged only by whether it moves the model's error on real outcomes.

### At a glance

| Sport | Free data source | Rungs | Notes |
|---|---|---|---|
| NFL | `nflverse` / `nfl_data_py` | 44 | PBP incl. EPA/CPOE since 1999 |
| College Football | CollegeFootballData.com (CFBD) free API | 43 | SP+/PPA + recruiting |
| NBA | Kaggle team parquet + player logs + `nba.sqlite` (existing) | 40 | deepest existing build (73-col parquet) |
| NHL | NHL API + MoneyPuck (xG) | 39 | shot-quality since 2007-08 |
| MLB | `pybaseball` + Statcast + MLB StatsAPI | 39 | pitch-level since 2015; starter is king |
| Soccer | StatsBomb / Understat / football-data.co.uk | 35 | 3-way outcome; the hardest target |

**Cross-sport operational notes:** several APIs are unofficial (NHL, Statcast, CFBD-at-scale) → wrap behind each sport's data adapter with retries + graceful skips. The cached parquets must be read under the **Docker 3.10 / betting-venv stack** (anaconda's pyarrow hits a repetition-level bug). MoneyPuck (NHL) and Statcast/FanGraphs (MLB Rung-5+) require a one-time historical backfill before those rungs are buildable; Rungs 1–4 are buildable today from cached data.

---

## NFL 🏈

### Data availability: NFL
- **Source / client:** `nflverse` via `nfl_data_py` (Python). The plugin (`backend/sports/nfl/data.py`) wraps `import_schedules`; the deeper feeds (`import_pbp_data`, `import_ngs_data`, `import_snap_counts`, `import_injuries`, `import_weekly_data`) are installed in `betting_venv` and available but not yet wired into features.
- **History:** Schedules + play-by-play back to **1999** (EPA/WP/CPOE/air-yards on every play). NGS ~2016+, snap counts ~2012+, injury reports ~2009+, FTN charting 2022+. Team-outcome backtest horizon = **1999–present** (~25 seasons, ~7k games).
- **Core fields / tables available:**
  - *Schedule* (`import_schedules`, one row/game): `home_score`, `away_score`, `result`, `total`, `overtime`, `home_rest`, `away_rest`, `div_game`, `roof`, `surface`, `temp`, `wind`, `home_qb_id/name`, `away_qb_id/name`, `home_coach`, `away_coach`, `referee`, `stadium_id`, `location`. Already normalized in the plugin: `home/away` (canonical), `game_date`, plus a `game_context()` deriving `IS_DOME`, `WIND`, `TEMP`, `DIV_GAME`.
  - *Team-game substrate* (`load_team_games`): one row/team-game with `pts`, `opp_pts`, `is_home`, `opponent`. Plugin already computes prior-only `OFF`, `DEF`, `WINPCT`, `FORM` (last-3 point diff), `REST`, `PRIOR_DIFF`, plus `NET_DIFF`/`REST_DIFF`.
  - *Play-by-play* (`import_pbp_data`, ~380 cols): `epa`, `qb_epa`, `cpoe`, `pass_oe`, `xpass`, `success`, `series_success`, `air_yards`, `yac_epa`, `xyac_epa`, `wp/wpa`, `vegas_wp`, `play_type`, `down`, `ydstogo`, `shotgun`, `no_huddle`, `qb_dropback`, `sack`, `interception`, `fumble_lost`, `penalty`/`penalty_yards`, `third_down_converted/failed`, `fourth_down_converted/failed`, `drive`, `series`, `drive_time_of_possession`, `fixed_drive_result`.
  - *Next Gen Stats* (`import_ngs_data('passing')`): `completion_percentage_above_expectation`, `avg_time_to_throw`, `aggressiveness`, `avg_air_yards_to_sticks`.
  - *Availability*: `import_snap_counts` (`offense_pct`), `import_injuries` (`report_status`, `report_primary_injury`).
- **Known gaps / limits:** `temp`/`wind` null for domes (plugin neutral-fills). Injury reports have gametime-decision noise; snap counts are prior-week only. PBP is sparse-per-team (~17 games/yr) so rolling windows are shallow.

### Feature ladder: NFL

#### NFL-01 · Season-to-date points scored (OFF)   (Rung 1 - Basic box stats)
- **Data field / source:** `pts` → `OFF` (expanding mean, `shift(1)`), `team_features.py`
- **Hypothesis:** A team's own scoring rate is the crudest predictor of how many points it will put up next week.
- **Impact measured:** Δ score MAE + Δ margin/total log-loss vs a league-average constant baseline, walk-forward 1999–present.

#### NFL-02 · Season-to-date points allowed (DEF)   (Rung 1 - Basic box stats)
- **Data field / source:** `opp_pts` → `DEF` (expanding mean, `shift(1)`)
- **Hypothesis:** Points allowed captures baseline defensive quality that shapes the opponent's total.
- **Impact measured:** Δ score MAE / total log-loss vs NFL-01-only model, walk-forward from 1999.

#### NFL-03 · Net point differential (NET_DIFF)   (Rung 1 - Basic box stats)
- **Data field / source:** `(HOME_OFF − HOME_DEF) − (AWAY_OFF − AWAY_DEF)` = `NET_DIFF`
- **Hypothesis:** Point differential is a better team-strength summary than win/loss and should predict margin directly.
- **Impact measured:** Δ margin MAE / winner accuracy vs OFF+DEF entered separately, walk-forward.

#### NFL-04 · Season-to-date win pct (WINPCT)   (Rung 1 - Basic box stats)
- **Data field / source:** `win = pts > opp_pts` → `WINPCT` (expanding mean, `shift(1)`)
- **Hypothesis:** Raw win rate is a noisy but non-zero prior on who wins in a low-sample sport.
- **Impact measured:** Δ winner log-loss vs NET_DIFF-only; expect near-zero once differential is in (records noisy at ~17 games).

#### NFL-05 · Prior-season point differential carryover (PRIOR_DIFF)   (Rung 1 - Basic box stats)
- **Data field / source:** last season's mean `diff`, merged onto `season+1` = `PRIOR_DIFF`
- **Hypothesis:** With only ~17 games/year, last year's team strength is a strong Week-1 prior before this year's sample accrues.
- **Impact measured:** Δ margin MAE especially in Weeks 1–4 (early-season slice), walk-forward.

#### NFL-06 · Last-3-game form (FORM)   (Rung 2 - Rolling windows)
- **Data field / source:** `diff` → `FORM` (`shift(1).rolling(3)` mean), `team_features.py`
- **Hypothesis:** Recent point-differential form captures in-season improvement/decline the season-average smooths over.
- **Impact measured:** Δ margin MAE vs season-to-date-only model, walk-forward from 1999.

#### NFL-07 · Recency-weighted OFF/DEF (EWMA)   (Rung 2 - Rolling windows)
- **Data field / source:** `pts`/`opp_pts` re-rolled as `shift(1).ewm(halflife≈4 games)`
- **Hypothesis:** Exponentially decaying weights beat a flat expanding mean by tracking the current roster/scheme.
- **Impact measured:** Δ score MAE, EWMA vs flat mean at matched leakage; tune half-life on walk-forward folds.

#### NFL-08 · Last-3 scoring & allowed variance (volatility)   (Rung 2 - Rolling windows)
- **Data field / source:** `shift(1).rolling(3).std()` of `pts` and `opp_pts`
- **Hypothesis:** Boom/bust teams have wider score distributions; volatility should sharpen total (over/under) calibration, not the point estimate.
- **Impact measured:** Δ total log-loss / calibration (reliability curve) vs mean-only, walk-forward.

#### NFL-09 · Rolling form window sweep (last-5 / last-8)   (Rung 2 - Rolling windows)
- **Data field / source:** `diff` rolled at windows {3,5,8} with `shift(1)`
- **Hypothesis:** There's an optimal memory length for NFL form; too short is noise, too long ignores change.
- **Impact measured:** Δ margin MAE across window choices on walk-forward folds; keep the best, publish the curve.

#### NFL-10 · Opponent-adjusted OFF (offense vs schedule faced)   (Rung 3 - Opponent adjustment)
- **Data field / source:** `OFF` minus mean `DEF` of prior opponents (from `opponent` in `load_team_games`)
- **Hypothesis:** Raw scoring is inflated/deflated by schedule; adjusting for defenses faced isolates true offense.
- **Impact measured:** Δ margin/total MAE vs unadjusted OFF/DEF, walk-forward from 1999.

#### NFL-11 · Opponent-adjusted DEF (defense vs offenses faced)   (Rung 3 - Opponent adjustment)
- **Data field / source:** `DEF` minus mean `OFF` of prior opponents faced
- **Hypothesis:** A defense that faced weak offenses looks better than it is; adjusting reveals real defensive strength.
- **Impact measured:** Δ margin MAE / winner log-loss vs NFL-10-only, walk-forward.

#### NFL-12 · Iterative strength-of-schedule rating (SRS-style)   (Rung 3 - Opponent adjustment)
- **Data field / source:** prior-only fixed-point solve of `diff` adjusted for `opponent` strength (Simple Rating System)
- **Hypothesis:** One convergent net rating that nets out schedule beats one-pass opponent adjustment as a single strength summary.
- **Impact measured:** Δ margin MAE vs NFL-10/11 one-pass adjustment, walk-forward.

#### NFL-13 · Strength-of-schedule faced (past & future)   (Rung 3 - Opponent adjustment)
- **Data field / source:** mean prior-opponent `PRIOR_DIFF`/rating from the schedule
- **Hypothesis:** A hard past slate depresses a team's raw stats; encoding SoS explicitly lets the model discount them.
- **Impact measured:** Δ margin MAE vs opponent-adjusted-only, walk-forward.

#### NFL-14 · Rest days (REST) and rest differential (REST_DIFF)   (Rung 4 - Rest / schedule / travel)
- **Data field / source:** `home_rest`, `away_rest` (schedule) and plugin `REST`/`REST_DIFF` from `game_date` diffs
- **Hypothesis:** More rest than the opponent is a real edge; the rest gap should move margin.
- **Impact measured:** Δ margin MAE / winner accuracy vs no-rest model, walk-forward.

#### NFL-15 · Off-a-bye flag   (Rung 4 - Rest / schedule / travel)
- **Data field / source:** `home_rest`/`away_rest` ≥ 13 (bye-week rest) as a binary
- **Hypothesis:** Coming off a bye (extra prep + health) is a well-known situational bump, distinct from the linear rest term.
- **Impact measured:** Δ winner accuracy / margin MAE on the bye-team subset, walk-forward.

#### NFL-16 · Short week / Thursday game   (Rung 4 - Rest / schedule / travel)
- **Data field / source:** `home_rest`/`away_rest` ≤ 4 (or `weekday == 'Thursday'` from schedule)
- **Hypothesis:** Short-week teams are fatigued/under-prepared, depressing scoring and margin.
- **Impact measured:** Δ total/margin MAE on short-week games vs baseline, walk-forward.

#### NFL-17 · Travel distance & time-zone shift   (Rung 4 - Rest / schedule / travel)
- **Data field / source:** `stadium_id`/`location` → lat-long → haversine + tz delta between consecutive games
- **Hypothesis:** Long travel and body-clock mismatch (esp. West→East early kickoffs) shave points off the traveling team.
- **Impact measured:** Δ margin MAE / road-team winner accuracy on high-travel subset vs no-travel model, walk-forward.

#### NFL-18 · International / neutral-site game   (Rung 4 - Rest / schedule / travel)
- **Data field / source:** `location` == 'Neutral' (London/Munich/Mexico) from schedule
- **Hypothesis:** Neutral-site games erase home advantage and add travel, a distinct regime worth flagging.
- **Impact measured:** Δ margin MAE on neutral-site subset; small-N but published, walk-forward.

#### NFL-19 · Offensive EPA/play (prior-only)   (Rung 5 - Derived efficiency)
- **Data field / source:** team mean `epa` on offensive plays from `import_pbp_data`, rolled `shift(1)`
- **Hypothesis:** EPA/play is the single most predictive team-efficiency metric and should beat raw points once schedule-noise is stripped.
- **Impact measured:** Δ margin MAE / winner log-loss vs box-score-only model (expected to be one of the biggest single-feature gains), walk-forward.

#### NFL-20 · Defensive EPA/play allowed   (Rung 5 - Derived efficiency)
- **Data field / source:** team mean `epa` allowed (opponent offensive plays), rolled `shift(1)`
- **Hypothesis:** EPA allowed measures defense far better than points allowed (which is drive/field-position contaminated).
- **Impact measured:** Δ margin MAE vs points-allowed (DEF) feature, walk-forward.

#### NFL-21 · Pass-EPA vs rush-EPA split (offense & defense)   (Rung 5 - Derived efficiency)
- **Data field / source:** `epa` split by `play_type in {pass,run}` / `qb_epa`, per team, `shift(1)`
- **Hypothesis:** Pass efficiency is stickier and more predictive than rush efficiency; splitting them adds signal over blended EPA.
- **Impact measured:** Δ margin MAE vs single blended-EPA feature, walk-forward.

#### NFL-22 · Success rate (offense & defense)   (Rung 5 - Derived efficiency)
- **Data field / source:** team mean `success` (down-adjusted positive-EPA share) from PBP, `shift(1)`
- **Hypothesis:** Success rate captures consistency/floor where EPA captures explosiveness, complementary to NFL-19/20.
- **Impact measured:** Δ margin MAE and total calibration vs EPA-only, walk-forward.

#### NFL-23 · CPOE, completion pct over expected   (Rung 5 - Derived efficiency)
- **Data field / source:** team offensive `cpoe` from PBP (or `completion_percentage_above_expectation` from NGS), `shift(1)`
- **Hypothesis:** CPOE isolates QB/passing-game accuracy independent of scheme depth and should add to pass-EPA.
- **Impact measured:** Δ margin MAE vs pass-EPA-only, walk-forward from PBP era (1999)/NGS era (2016).

#### NFL-24 · EPA-composite (CPOE+EPA passing rating)   (Rung 5 - Derived efficiency)
- **Data field / source:** blended `qb_epa` + `cpoe` (nflverse's standard passing composite), rolled `shift(1)`
- **Hypothesis:** The community-standard EPA+CPOE passing metric is more stable per-game than either alone.
- **Impact measured:** Δ margin MAE vs NFL-21/23 entered separately, walk-forward.

#### NFL-25 · Pace / plays & seconds-per-play   (Rung 5 - Derived efficiency)
- **Data field / source:** offensive play count per game + `game_seconds_remaining` deltas / `no_huddle` rate from PBP, `shift(1)`
- **Hypothesis:** Faster teams create more possessions, lifting the game total independent of per-play efficiency.
- **Impact measured:** Δ total MAE / total calibration vs efficiency-only model, walk-forward.

#### NFL-26 · Explosive-play & early-down EPA rate   (Rung 5 - Derived efficiency)
- **Data field / source:** share of plays with `air_yards`/gain over threshold; `epa` filtered to `down in {1,2}` from PBP, `shift(1)`
- **Hypothesis:** Explosiveness and early-down efficiency drive scoring variance and predict blowout margins.
- **Impact measured:** Δ margin MAE (esp. tails) vs mean-EPA-only, walk-forward.

#### NFL-27 · Third/fourth-down conversion & red-zone rate   (Rung 5 - Derived efficiency)
- **Data field / source:** `third_down_converted/failed`, `fourth_down_converted/failed`, drive `inside20`/`fixed_drive_result` from PBP, `shift(1)`
- **Hypothesis:** Finishing drives (situational conversion) turns yards into points and should add to total prediction.
- **Impact measured:** Δ total/points MAE vs EPA+pace model; may be partly redundant with EPA (publish either way), walk-forward.

#### NFL-28 · Turnover & giveaway rate   (Rung 5 - Derived efficiency)
- **Data field / source:** per-play `interception` + `fumble_lost` (offense) and takeaways (defense) from PBP, rolled `shift(1)`
- **Hypothesis:** Turnover margin swings games, but it's noisy/low-stickiness, so it should help less than efficiency (a "regresses hard" lesson).
- **Impact measured:** Δ margin MAE / winner log-loss vs efficiency-only; expect small/unstable gains, walk-forward.

#### NFL-29 · Sack & pressure rate (offense allowed / defense generated)   (Rung 5 - Derived efficiency)
- **Data field / source:** per-dropback `sack` rate from PBP (and `avg_time_to_throw` from NGS), `shift(1)`
- **Hypothesis:** Pass-rush/protection is a stable trench signal that shapes pass-EPA and scoring.
- **Impact measured:** Δ margin MAE vs pass-EPA-only, walk-forward.

#### NFL-30 · Penalty rate & penalty yards   (Rung 5 - Derived efficiency)
- **Data field / source:** `penalty`, `penalty_yards` per team from PBP, rolled `shift(1)`
- **Hypothesis:** Discipline (few penalties) is a minor persistent team trait nudging field position and drives.
- **Impact measured:** Δ margin MAE vs model without it; expect near-zero (a "does nothing" honest result), walk-forward.

#### NFL-31 · Net EPA matchup (off-EPA vs opp def-EPA)   (Rung 6 - Matchup & interaction)
- **Data field / source:** interaction of NFL-19 `home off-EPA` with NFL-20 `away def-EPA` (and symmetric), from rolled PBP
- **Hypothesis:** What matters is each offense against that specific defense, the interaction beats the two main effects alone.
- **Impact measured:** Δ margin MAE vs additive off-EPA + def-EPA, walk-forward.

#### NFL-32 · Pass-offense vs pass-defense mismatch   (Rung 6 - Matchup & interaction)
- **Data field / source:** interaction of team pass-EPA/CPOE (NFL-21/23) with opponent pass-EPA allowed, from PBP
- **Hypothesis:** A strong passing attack vs a weak pass defense is the highest-leverage mismatch in the modern NFL.
- **Impact measured:** Δ margin MAE on high-pass-mismatch games vs generic net-EPA, walk-forward.

#### NFL-33 · Rush-offense vs rush-defense mismatch   (Rung 6 - Matchup & interaction)
- **Data field / source:** interaction of team rush-EPA/success (NFL-21/22) with opponent rush-EPA allowed, from PBP
- **Hypothesis:** Rush mismatches matter mainly for game-script/clock control, so expect a smaller edge than the pass mismatch.
- **Impact measured:** Δ total/margin MAE vs pass-mismatch-only, walk-forward.

#### NFL-34 · Pace × pace interaction (game-total driver)   (Rung 6 - Matchup & interaction)
- **Data field / source:** product/sum of both teams' pace & pass-rate (NFL-25) with combined off-efficiency
- **Hypothesis:** Two fast, pass-heavy offenses compound into shootouts; the interaction predicts totals better than summed pace.
- **Impact measured:** Δ total MAE / total calibration vs additive pace, walk-forward.

#### NFL-35 · Trench-mismatch composite (pressure vs protection)   (Rung 6 - Matchup & interaction)
- **Data field / source:** interaction of defense sack/pressure rate (NFL-29) with opponent sack-allowed rate
- **Hypothesis:** A dominant pass rush against a leaky line disproportionately collapses the opponent's passing game.
- **Impact measured:** Δ margin MAE on high-trench-gap games vs main effects, walk-forward.

#### NFL-36 · Home-field advantage (is_home + HFA constant)   (Rung 7 - Situational)
- **Data field / source:** `is_home` (plugin) and the schedule home/away assignment
- **Hypothesis:** Home teams win at a persistent baseline rate; encoding HFA is a cheap, reliable margin shift.
- **Impact measured:** Δ margin MAE / winner accuracy vs no-HFA model (should confirm the ~2-pt HFA), walk-forward.

#### NFL-37 · Divisional-game flag (DIV_GAME)   (Rung 7 - Situational)
- **Data field / source:** `div_game` → `DIV_GAME` (plugin `game_context`)
- **Hypothesis:** Familiar division rivals play tighter, lower-variance games; margins compress toward zero.
- **Impact measured:** Δ margin MAE / winner accuracy on divisional subset vs non-div, walk-forward.

#### NFL-38 · Weather, wind & temperature   (Rung 7 - Situational)
- **Data field / source:** `WIND`, `TEMP`, `IS_DOME` (plugin `game_context`, from schedule `wind`/`temp`/`roof`)
- **Hypothesis:** High wind and extreme cold suppress passing/kicking, lowering the total.
- **Impact measured:** Δ total MAE / total calibration on high-wind (>15mph) & cold games vs neutral, walk-forward.

#### NFL-39 · Surface & roof (turf vs grass, dome)   (Rung 7 - Situational)
- **Data field / source:** `surface`, `roof` (schedule)
- **Hypothesis:** Dome/turf environments modestly lift scoring vs open-air grass; a small controlled-conditions bump.
- **Impact measured:** Δ total MAE vs weather-only model; expect small, walk-forward.

#### NFL-40 · Motivation, late-season playoff/elimination stakes   (Rung 7 - Situational)
- **Data field / source:** derived from `week` + standings implied by cumulative `result` (prior-only win totals)
- **Hypothesis:** Teams eliminated or locked into seeds late (esp. Week 18 rest) play with different intensity, distorting margins.
- **Impact measured:** Δ margin MAE on Weeks 15–18 subset vs no-motivation model, walk-forward.

#### NFL-41 · Backup/rookie QB start (availability proxy)   (Rung 8 - Availability & personnel)
- **Data field / source:** `home_qb_id`/`away_qb_id` (schedule) diffed against the team's usual starter; cross-check `import_injuries` `report_status`
- **Hypothesis:** QB is the highest-value position; a backup start should move margin more than any other single-player change.
- **Impact measured:** Δ margin MAE / winner log-loss on backup-QB games vs the prior model, walk-forward.

#### NFL-42 · Key-injury / inactives load (snaps-weighted)   (Rung 8 - Availability & personnel)
- **Data field / source:** `import_injuries` `report_status` (Out/Doubtful) weighted by prior-week `offense_pct`/`defense_pct` from `import_snap_counts`
- **Hypothesis:** Losing high-snap starters degrades a team in proportion to the snaps vacated.
- **Impact measured:** Δ margin MAE / winner log-loss on high-injury-load games vs the prior model, walk-forward (injury data 2009+, snaps 2012+).

#### NFL-43 · QB-adjusted team efficiency (EPA with current QB only)   (Rung 8 - Availability & personnel)
- **Data field / source:** re-roll offensive `qb_epa`/`cpoe` filtered to the announced `*_qb_id` (from PBP by passer), `shift(1)`
- **Hypothesis:** Attributing offensive efficiency to the actual starting QB (not the team) should sharpen the margin estimate, most on QB-change games.
- **Impact measured:** Δ margin MAE / winner log-loss vs team-level EPA, walk-forward.

#### NFL-44 · Coaching / referee tendency   (Rung 8 - Availability & personnel)
- **Data field / source:** `home_coach`/`away_coach`, `referee` (schedule) → historical pace/penalty/total tendencies, prior-only
- **Hypothesis:** Some coaches (aggressive 4th-down / tempo) and refs (penalty-heavy) nudge totals; effects are expected to be tiny.
- **Impact measured:** Δ total MAE / Δ accuracy vs the prior model; expect near-zero (an honest null), walk-forward.

---

## College Football 🏈

### Data availability: CFB
- **Source / client:** CollegeFootballData.com (CFBD) free JSON API. No existing plugin; this is a net-new `sports/cfb/` Sport plugin following the `sports/nfl/` pattern. Free API key required (Bearer token); a thin HTTP client with on-disk response caching keeps us under free rate limits. Live in-season `/games` refreshes may justify the ~$10/mo Patreon tier; historical backfill fits the free tier.
- **History:** Games/scores robust from ~2001 (FBS). Advanced/PPA stats reliable ~2013+. SP+ ~2005+, Elo ~2001+. Recruiting composites ~2010+; returning production ~2014+; team talent ~2015+. Practical modeling window: **2014–present** where every rung has coverage; early box-only rungs extend to ~2001.
- **Core fields / tables available:** `/games` & `/calendar` (schedule, scores, `venue`, `neutralSite`, `conferenceGame`, `week`, `seasonType`); `/games/teams` (per-team box: `rushingYards`, `netPassingYards`, `firstDowns`, `thirdDownEff`, `fourthDownEff`, `totalYards`, `turnovers`, `possessionTime`, `penalties`/`penaltyYards`, `yardsPerRushAttempt`, `yardsPerPass`); `/games/players`; `/drives`; `/plays`; `/ppa/games` & `/ppa/teams` (PPA overall + by down/quarter, `passingPPA`/`rushingPPA`); `/stats/season/advanced` & `/stats/game/advanced` (`successRate`, `explosiveness`, `lineYards`, `stuffRate`, `havoc`, field position, finishing); `/ratings/sp`, `/ratings/srs`, `/ratings/elo`; `/roster`, `/player/returning`, `/talent`, `/recruiting/teams` & `/recruiting/players`.
- **Known gaps / limits:** FCS opponents appear in FBS schedules but have thin/absent advanced+PPA data → SoS/opp-adjust needs a "non-FBS opponent" bucket. `possessionTime` is a clock string needing parse. Free-tier rate limits force cached backfill. Talent/recruiting don't exist pre-2010/2015. Neutral-site/bowl venues can lack lat/long → travel/altitude needs a venue geo table. Early-season rows (weeks 1–3) lean heavily on prior-season carryover + preseason ratings.

### Feature ladder: CFB
_Targets: `y_margin = home_pts − away_pts`, `y_total`, `home_pts`, `away_pts`. Discipline: prior-only `shift(1)` + expanding/rolling within `(team, season)`, prior-season as-of-merged with `season+1`, ratings/talent joined as-of publication week; walk-forward, no leakage._

#### CFB-01 · Season-to-date points scored (offense)   (Rung 1 - Basic box stats)
- **Data field / source:** `/games/teams` team `points` (or `/games` scores), expanding mean shifted one game within `(team, season)`.
- **Hypothesis:** Teams that have scored more so far this season score more today.
- **Impact measured:** Establishes the day-1 baseline, walk-forward SU accuracy + margin/total MAE, 2016→present.

#### CFB-02 · Season-to-date points allowed (defense)   (Rung 1 - Basic box stats)
- **Data field / source:** `/games/teams` opponent `points`, prior-only expanding mean.
- **Hypothesis:** Teams allowing fewer points concede fewer today; pairs with CFB-01 to bound total.
- **Impact measured:** Δ margin/total MAE vs CFB-01-only, walk-forward.

#### CFB-03 · Season win pct   (Rung 1 - Basic box stats)
- **Data field / source:** derived `win = points > opp_points`, prior-only expanding mean within `(team, season)`.
- **Hypothesis:** Winning teams keep winning; a coarse quality signal (mirrors NFL `WINPCT`).
- **Impact measured:** Δ SU accuracy / log-loss vs prior model, walk-forward.

#### CFB-04 · Net yards per play differential   (Rung 1 - Basic box stats)
- **Data field / source:** `/games/teams` `totalYards` ÷ plays (or `yardsPerPass`/`yardsPerRushAttempt`), own minus opponent, prior-only expanding.
- **Hypothesis:** Yards-per-play margin is a steadier quality proxy than points.
- **Impact measured:** Δ margin MAE / log-loss vs points-only baseline.

#### CFB-05 · Turnover margin   (Rung 1 - Basic box stats)
- **Data field / source:** `/games/teams` `turnovers` (own giveaways vs forced), prior-only expanding differential.
- **Hypothesis:** Ball security/takeaways swing CFB outcomes; but turnovers are noisy/regressive, so expect a small, possibly fading edge.
- **Impact measured:** Δ SU accuracy + margin MAE; flag stability across folds (turnover luck).

#### CFB-06 · Third-down conversion rate   (Rung 1 - Basic box stats)
- **Data field / source:** `/games/teams` `thirdDownEff` (parse "converted-attempts"), prior-only offense and defense rates.
- **Hypothesis:** Sustaining/stopping drives correlates with scoring and time-of-possession control.
- **Impact measured:** Δ margin/total MAE vs prior model.

#### CFB-07 · Yards-per-rush and yards-per-pass split   (Rung 1 - Basic box stats)
- **Data field / source:** `/games/teams` `yardsPerRushAttempt`, `yardsPerPass` (net), prior-only expanding, offense + defense.
- **Hypothesis:** Separating run vs pass efficiency captures team identity better than blended yards/play.
- **Impact measured:** Δ margin MAE vs CFB-04 (blended).

#### CFB-08 · First downs & possession time   (Rung 1 - Basic box stats)
- **Data field / source:** `/games/teams` `firstDowns`, `possessionTime` (parse mm:ss → seconds), prior-only expanding.
- **Hypothesis:** Sustained drives → more scoring chances and fewer for the opponent; a tempo/control proxy that shapes the total.
- **Impact measured:** Δ total MAE especially; small Δ margin.

#### CFB-09 · Last-3-games scoring margin (form)   (Rung 2 - Rolling windows)
- **Data field / source:** derived `diff = points − opp_points`, prior-only `rolling(3, min_periods=1).mean()`.
- **Hypothesis:** Recent form (injuries, QB settling, momentum) beats a flat season average in a ~12-game season.
- **Impact measured:** Δ margin MAE / SU vs season-to-date-only (CFB-01/02).

#### CFB-10 · Last-3 offensive & defensive yards/play   (Rung 2 - Rolling windows)
- **Data field / source:** `/games/teams` yards/play, prior-only rolling-3 for offense and defense separately.
- **Hypothesis:** Short-window efficiency trends catch a team trending up/down before points reflect it.
- **Impact measured:** Δ margin MAE vs CFB-04 (season) + CFB-09.

#### CFB-11 · Exponentially-weighted team rating   (Rung 2 - Rolling windows)
- **Data field / source:** derived scoring-margin EWMA (half-life ~4 games), prior-only within season with prior-season seed.
- **Hypothesis:** Recency-weighting better tracks a young roster's true level mid-season.
- **Impact measured:** Δ log-loss / margin MAE vs equal-weight expanding baseline.

#### CFB-12 · Prior-season point differential carryover   (Rung 2 - Rolling windows)
- **Data field / source:** `/games` prior-year mean `diff`, as-of merged `season+1`, used mainly for weeks 1–3.
- **Hypothesis:** Program strength persists year-to-year; anchors early-season rows.
- **Impact measured:** Δ SU/MAE on weeks 1–4 subset specifically, walk-forward.

#### CFB-13 · Opponent-adjusted scoring margin (iterative SoS)   (Rung 3 - Opponent adjustment)
- **Data field / source:** `/games` results + `/games/teams`; ridge/iterative adjustment of each team's margin for opponents faced (prior weeks only), FCS bucketed as a single weak level.
- **Hypothesis:** **The single biggest CFB rung**: raw box stats are meaningless without schedule context (a G5 3–0 ≠ an SEC 3–0).
- **Impact measured:** Δ SU accuracy + margin MAE vs all raw/rolling box stats, expected the biggest single-feature gain.

#### CFB-14 · Opponent-adjusted offensive & defensive efficiency   (Rung 3 - Opponent adjustment)
- **Data field / source:** adjust prior-only offensive/defensive yards-per-play (and success rate later) for opponents faced.
- **Hypothesis:** A defense that looks elite only played cupcakes; adjusting each unit sharpens both margin and total.
- **Impact measured:** Δ margin + total MAE vs unadjusted CFB-04/07/10.

#### CFB-15 · Conference-strength tier   (Rung 3 - Opponent adjustment)
- **Data field / source:** `/games` `conference` per team + `conferenceGame`; prior-season conference average opponent-adjusted rating as an as-of feature.
- **Hypothesis:** Conference is a cheap prior on schedule strength (P5 vs G5) that stabilizes early-season SoS.
- **Impact measured:** Δ SU/MAE on weeks 1–5 subset vs CFB-13 alone.

#### CFB-16 · Strength-of-schedule to date   (Rung 3 - Opponent adjustment)
- **Data field / source:** mean opponent-adjusted rating of teams already played (prior-only) + count of FBS vs FCS opponents.
- **Hypothesis:** Explicitly encoding schedule difficulty lets the model discount records built on weak slates.
- **Impact measured:** Δ log-loss vs prior model; interaction check with win pct.

#### CFB-17 · Days of rest since last game   (Rung 4 - Rest / schedule / travel)
- **Data field / source:** `/games` dates, `groupby(team).game_date.diff().dt.days` clipped; captures midweek MACtion short weeks.
- **Hypothesis:** Short rest hurts; extra prep helps, a real but modest edge.
- **Impact measured:** Δ SU/margin MAE vs prior model; `REST_DIFF` coefficient.

#### CFB-18 · Off-a-bye indicator   (Rung 4 - Rest / schedule / travel)
- **Data field / source:** derived from `/calendar` gap → flag when rest ≳ 13 days (open week).
- **Hypothesis:** Extra prep week (esp. for the underdog) is a known CFB edge coaches exploit.
- **Impact measured:** Δ SU accuracy / margin MAE on the off-a-bye subset vs the prior model.

#### CFB-19 · Travel distance   (Rung 4 - Rest / schedule / travel)
- **Data field / source:** `/venues` lat/long joined to `/games` venue → haversine between prior and current site (needs a `geo.py` venue table).
- **Hypothesis:** Cross-country road trips degrade performance.
- **Impact measured:** Δ margin MAE vs prior; isolate long-haul (>1500 mi) away subset.

#### CFB-20 · Altitude / time-zone shift   (Rung 4 - Rest / schedule / travel)
- **Data field / source:** `/venues` `elevation` + derived time-zone delta from lat/long; altitude gap and body-clock hours off.
- **Hypothesis:** Altitude (Air Force, Wyoming, Utah) and body-clock disruption shave points from visitors.
- **Impact measured:** Δ margin MAE on high-altitude-host and ≥2-TZ-shift subsets.

#### CFB-21 · Early-kickoff body-clock flag   (Rung 4 - Rest / schedule / travel)
- **Data field / source:** `/games` `startDate` → local kickoff hour relative to visitor's home time zone.
- **Hypothesis:** West-coast teams in noon-ET (9am body-clock) games underperform, a specific testable folk edge.
- **Impact measured:** Δ SU/margin on that exact subset; likely small.

#### CFB-22 · SP+ overall rating   (Rung 5 - Derived efficiency)
- **Data field / source:** `/ratings/sp` overall, as-of the pre-game week (prior week's rating; prior-season final for weeks 1–3).
- **Hypothesis:** SP+ is a mature tempo-free, opponent-adjusted efficiency rating, a strong single feature that may subsume earlier rungs.
- **Impact measured:** Δ SU accuracy + margin MAE vs full box+opp-adjust stack; feature-importance takeover check.

#### CFB-23 · SP+ offense & defense & special-teams split   (Rung 5 - Derived efficiency)
- **Data field / source:** `/ratings/sp` `offense`/`defense`/`specialTeams`, as-of prior week.
- **Hypothesis:** Unit-level SP+ predicts margin and total better than the composite alone.
- **Impact measured:** Δ margin + total MAE vs CFB-22 composite-only.

#### CFB-24 · Team PPA / EPA per play   (Rung 5 - Derived efficiency)
- **Data field / source:** `/ppa/teams` overall offensive & defensive PPA, prior-only expanding + opponent-adjusted.
- **Hypothesis:** Predicted-Points-Added per play is the EPA-equivalent quality signal, more predictive than raw yards.
- **Impact measured:** Δ margin MAE / log-loss vs yards-based efficiency (CFB-04/14).

#### CFB-25 · Success rate (offense & defense)   (Rung 5 - Derived efficiency)
- **Data field / source:** `/stats/season/advanced` `successRate` (overall + standard/passing downs), prior-only, opponent-adjusted.
- **Hypothesis:** Down-to-down efficiency is the stable, high-floor predictor of drive success.
- **Impact measured:** Δ log-loss vs prior model; stability across folds (expected high).

#### CFB-26 · Explosiveness   (Rung 5 - Derived efficiency)
- **Data field / source:** `/stats/season/advanced` `explosiveness` (PPA on successful plays), prior-only offense/defense.
- **Hypothesis:** Big-play ability explains variance success rate misses, pairs with CFB-25 (the "Five Factors" core).
- **Impact measured:** Δ margin MAE vs CFB-25-only.

#### CFB-27 · Line yards & stuff rate   (Rung 5 - Derived efficiency)
- **Data field / source:** `/stats/season/advanced` `lineYards`, `stuffRate` (rushing), prior-only, both sides.
- **Hypothesis:** Trench control (OL/DL) is a durable, injury-robust signal underlying rushing success.
- **Impact measured:** Δ margin MAE vs prior model; small but stable.

#### CFB-28 · Havoc rate   (Rung 5 - Derived efficiency)
- **Data field / source:** `/stats/season/advanced` `havoc` (TFL+PBU+forced fumbles ÷ plays), prior-only defense (and offense allowed).
- **Hypothesis:** Defensive disruption rate is a more stable takeaway proxy than raw turnovers (CFB-05).
- **Impact measured:** Δ log-loss vs CFB-05; does havoc survive where raw turnovers didn't?

#### CFB-29 · Field position & finishing drives   (Rung 5 - Derived efficiency)
- **Data field / source:** `/stats/season/advanced` avg start field position + points-per-scoring-opportunity; `/drives` start yardlines.
- **Hypothesis:** Field-position edge and red-zone finishing convert efficiency into actual points.
- **Impact measured:** Δ total + `home_pts`/`away_pts` MAE vs efficiency-only stack.

#### CFB-30 · Elo rating   (Rung 5 - Derived efficiency)
- **Data field / source:** `/ratings/elo`, as-of prior week (result-based, self-updating).
- **Hypothesis:** A pure results-Elo gives a complementary, low-variance win-prob signal alongside efficiency ratings.
- **Impact measured:** Δ SU/log-loss vs SP+/PPA stack; ensemble-diversity check.

#### CFB-31 · Pace / plays-per-game   (Rung 6 - Matchup & interaction)
- **Data field / source:** `/stats/game/advanced` or `/plays` counts → prior-only plays/game and seconds/play, both teams.
- **Hypothesis:** Two fast offenses inflate the total; a fast vs ball-control clash sets play volume, a total-shaping term.
- **Impact measured:** Δ total MAE vs additive efficiency features.

#### CFB-32 · Offense-vs-opponent-defense unit matchup   (Rung 6 - Matchup & interaction)
- **Data field / source:** interaction of home offensive PPA/success (CFB-24/25) × away defensive PPA/success (and vice-versa), prior-only, opponent-adjusted.
- **Hypothesis:** What matters is this offense against that defense, not each team's average.
- **Impact measured:** Δ margin MAE vs purely additive team features.

#### CFB-33 · Rush-vs-run-defense & pass-vs-pass-defense style clash   (Rung 6 - Matchup & interaction)
- **Data field / source:** `/ppa/teams` `rushingPPA`/`passingPPA` offense × opponent's rush/pass defense splits, prior-only.
- **Hypothesis:** A run-heavy offense meeting a porous run defense predicts margin beyond blended efficiency.
- **Impact measured:** Δ margin MAE vs CFB-32 (blended matchup).

#### CFB-34 · Explosiveness-vs-havoc interaction   (Rung 6 - Matchup & interaction)
- **Data field / source:** home explosiveness (CFB-26) × away havoc (CFB-28), both directions, prior-only.
- **Hypothesis:** An explosive offense against a high-havoc defense produces high-variance outcomes.
- **Impact measured:** Δ margin MAE + calibration/interval check vs additive terms.

#### CFB-35 · Home / away / neutral-site indicator   (Rung 7 - Situational)
- **Data field / source:** `/games` `neutralSite` flag + home/away → three-way HFA term.
- **Hypothesis:** Home-field is worth ~2–3 pts in CFB; neutral-site bowls/kickoff games zero it out; must be explicit.
- **Impact measured:** Δ margin MAE; HFA coefficient; neutral-site subset check.

#### CFB-36 · Rivalry game flag   (Rung 7 - Situational)
- **Data field / source:** curated rivalry pairs joined to `/games`.
- **Hypothesis:** "Throw out the records" rivalries compress margins (underdog overperforms).
- **Impact measured:** Δ margin MAE on rivalry subset; sign of favorite-margin shrinkage.

#### CFB-37 · Conference vs non-conference game   (Rung 7 - Situational)
- **Data field / source:** `/games` `conferenceGame` (+ `seasonType`).
- **Hypothesis:** Familiarity and stakes differ; non-con early games are noisier, a context flag.
- **Impact measured:** Δ log-loss overall; interaction with SoS (CFB-16).

#### CFB-38 · Look-ahead / letdown spot   (Rung 7 - Situational)
- **Data field / source:** derived schedule lookahead, big favorite the week before a marquee opponent, or after an emotional upset.
- **Hypothesis:** Favorites underperform in trap spots; a flag for the spot should nudge the margin estimate.
- **Impact measured:** Δ margin MAE / Δ accuracy on the flagged subset vs the prior model.

#### CFB-39 · Bowl / postseason motivation flag   (Rung 7 - Situational)
- **Data field / source:** `/games` `seasonType = postseason`; join opt-outs/coaching-change context where available.
- **Hypothesis:** Non-playoff bowls have erratic motivation (opt-outs, interim coaches) → ratings mispredict.
- **Impact measured:** Δ margin MAE + calibration on bowl subset vs regular season.

#### CFB-40 · Returning production   (Rung 8 - Availability & personnel)
- **Data field / source:** `/player/returning`, total/offensive/defensive returning-production %, as-of preseason, decaying through the season.
- **Hypothesis:** **CFB-unique**: continuity predicts year-over-year change, so it should sharpen early-season estimates.
- **Impact measured:** Δ early-season (weeks 1–4) margin/total MAE vs the prior model, walk-forward.

#### CFB-41 · Team talent composite   (Rung 8 - Availability & personnel)
- **Data field / source:** `/talent` (247-style composite) + `/recruiting/teams` (rolling class rankings), as-of season start.
- **Hypothesis:** **CFB-unique**: recruiting/talent explains the huge FBS talent gaps, especially in blowout-prone mismatches.
- **Impact measured:** Δ SU accuracy / margin MAE on blowout-prone mismatches vs the prior model.

#### CFB-42 · QB availability / starter change   (Rung 8 - Availability & personnel)
- **Data field / source:** `/games/players` + `/roster` to detect starting-QB PPA and a starter-change/injury flag.
- **Hypothesis:** A backup QB swings CFB margins more than any other single-player event.
- **Impact measured:** Δ margin MAE / winner log-loss on QB-change games vs the prior model.

#### CFB-43 · Coaching change / interim regime   (Rung 8 - Availability & personnel)
- **Data field / source:** roster/coaching metadata + `/games` (new HC, fired mid-season, interim, bowl opt-out coach).
- **Hypothesis:** Scheme/motivation discontinuity breaks rating-based predictions.
- **Impact measured:** Δ margin MAE on affected games vs the prior model.

---

## NBA 🏀

### Data availability: NBA
- **Source / client:** Primary team-game log is `data/processed/kaggle_team_games.parquet` (built from the Kaggle NBA dataset; consumed by `feature_engine` and `sports/nba/team_features.py`). Player game logs are per-player CSVs under `data/player_data/<Name>/`. Deep box/context in `data/advanced_nba/nba.sqlite` (`game`, `line_score`, `other_stats`, `inactive_players`). Team×season ratings in `data/team_stats/all_team_stats.csv`. Live slate + geo via ESPN scoreboard (`sports/nba/sport.py`) + `sports/nba/geo.py`.
- **History:** `kaggle_team_games.parquet` covers **2006–2025, 23,965 games / 51,170 team-rows**, incl. 3,240 playoff team-rows (`is_playoff`) and `is_overtime`. `inactive_players` spans 1996–2023. ~19 full seasons of team-outcome data.
- **Core fields / tables available:** The parquet carries **73 columns**: box (`pts, fgm/fga, 3pm/3pa, ftm/fta, oreb/dreb/reb, ast, tov, stl, blk, pf, plus_minus`), ratings (`off_rtg, def_rtg, net_rtg, pace, pie`), **four factors both sides** (`efg_pct, tov_pct, oreb_pct, dreb_pct, fta_rate` + opponent versions), scoring mix (`pitp, fbps, 2nd_pts, pts_off_to`, `pct_pts_*`), all 100% non-null 2006–2025. Flags: `is_home_team, is_playoff, is_overtime, is_win`. sqlite adds `largest_lead, lead_changes`, per-quarter `line_score`, and per-game DNP `inactive_players`. Player CSVs carry full box + `MIN, DAYS_SINCE_LAST_GAME, position, height/weight`. Reconstructed availability at `data/auxiliary/team_availability.parquet` (`TM_OUT_MIN, TM_OUT_PTS, TM_OUT_COUNT, TM_TOP_OUT`).
- **Known gaps / limits:** (1) `inactive_players` ends 2023 and is a result-time DNP list, the honest availability feature must reconstruct pre-tip "expected rotation OUT" from prior-game minutes (as `collect_team_availability.py` does). (2) no possessions column, per-possession features use league-provided `off_rtg/def_rtg`. (3) no confirmed-starter feed. (4) the parquets require the Docker 3.10 / betting-venv stack (anaconda pyarrow bug).

### Feature ladder: NBA
_Impact metric throughout: Δ SU accuracy / Δ log-loss on winner, Δ margin-MAE & Δ total-MAE, walk-forward per season 2006→2025 (expanding-train / next-season-test), vs the immediately-prior rung. Every rolling feature is prior-only (`shift(1)` / cumulative-through-previous-game), merged backward-exclusive._

#### NBA-01 · Home-court indicator + league-average score prior   (Rung 1 - Basic box stats)
- **Data field / source:** `is_home_team`; league-mean `pts`/`y_total` as intercept.
- **Hypothesis:** Home teams win ~58–60% and score a few points more; a constant home edge is a real day-1 baseline.
- **Impact measured:** Baseline SU accuracy + margin/total MAE, walk-forward (the reference all later rungs beat).

#### NBA-02 · Season-to-date points scored   (Rung 1 - Basic box stats)
- **Data field / source:** `pts`, cumulative-through-previous-game per `(team, season)`.
- **Hypothesis:** How much a team has scored predicts how much it will score.
- **Impact measured:** Δ total-MAE and Δ margin-MAE vs NBA-01.

#### NBA-03 · Season-to-date points allowed   (Rung 1 - Basic box stats)
- **Data field / source:** opponent `pts` mapped as points-against, cumulative prior-only.
- **Hypothesis:** Points allowed to date is a coarse defense signal improving margin and total.
- **Impact measured:** Δ total-MAE + Δ margin-MAE vs NBA-02.

#### NBA-04 · Season-to-date point differential   (Rung 1 - Basic box stats)
- **Data field / source:** `plus_minus` / (`pts` − opp `pts`), cumulative prior-only.
- **Hypothesis:** Average scoring margin is the best crude team-strength proxy and should move winner accuracy the most of any box feature.
- **Impact measured:** Δ SU accuracy + Δ log-loss vs NBA-03.

#### NBA-05 · Prior-game shooting profile (FG%, 3P%, FT rate)   (Rung 1 - Basic box stats)
- **Data field / source:** `fg_pct`, `3p_pct`, `fta`/`fga`, prior-game team values (`KG_PREV_*`).
- **Hypothesis:** Recent shooting accuracy carries a little scoring signal beyond raw points.
- **Impact measured:** Δ total-MAE vs NBA-04 (expect small).

#### NBA-06 · Prior-game rebound & turnover counts   (Rung 1 - Basic box stats)
- **Data field / source:** `oreb, dreb, reb, tov, stl` prior-game team values.
- **Hypothesis:** Possession-count proxies nudge scoring and margin.
- **Impact measured:** Δ margin-MAE + Δ total-MAE vs NBA-05.

#### NBA-07 · Last-3 / last-5 form (points & margin)   (Rung 2 - Rolling windows)
- **Data field / source:** rolling means of `pts`, opp `pts`, `plus_minus` over last 3 and 5 games (`shift(1).rolling(w)`).
- **Hypothesis:** Short-window form captures streaks the season-to-date mean smooths away.
- **Impact measured:** Δ SU accuracy + Δ margin-MAE vs season-to-date model.

#### NBA-08 · Last-10 / last-20 rolling ratings   (Rung 2 - Rolling windows)
- **Data field / source:** rolling means of `off_rtg, def_rtg, net_rtg` over 10- and 20-game windows.
- **Hypothesis:** A 10–20 game window balances signal vs noise better than either extreme.
- **Impact measured:** Δ log-loss + Δ margin-MAE vs NBA-07; pick the best window empirically.

#### NBA-09 · Recency-weighted (EWMA) net rating   (Rung 2 - Rolling windows)
- **Data field / source:** exponentially-weighted mean of `net_rtg` (prior-only).
- **Hypothesis:** Exponential decay tracks form transitions more smoothly than a hard window.
- **Impact measured:** Δ margin-MAE + Δ SU vs the best fixed window.

#### NBA-10 · Rolling volatility (form consistency)   (Rung 2 - Rolling windows)
- **Data field / source:** rolling `std` of `plus_minus`/`net_rtg` over 10 games.
- **Hypothesis:** Inconsistent teams are harder to predict; volatility should widen margin σ (better-calibrated win probs).
- **Impact measured:** Δ log-loss / calibration vs NBA-09.

#### NBA-11 · Home/away split form   (Rung 2 - Rolling windows)
- **Data field / source:** venue-partitioned rolling means (`HA_HOME_*` / `HA_AWAY_*`, windows 5/10).
- **Hypothesis:** Some teams are far better at home than on the road beyond the league-average edge.
- **Impact measured:** Δ SU accuracy + Δ margin-MAE vs NBA-08, split home vs road.

#### NBA-12 · Elo rating (MOV-adjusted, home-aware)   (Rung 3 - Opponent adjustment)
- **Data field / source:** `_elo_timeline`, sequential MOV-multiplier Elo, home term, 25% preseason regression (`HOME_ELO/AWAY_ELO/ELO_DIFF`).
- **Hypothesis:** Elo implicitly adjusts each result for opponent strength, beating raw net rating.
- **Impact measured:** Δ SU accuracy + Δ margin-MAE vs rolling-ratings model.

#### NBA-13 · Strength-of-schedule to date   (Rung 3 - Opponent adjustment)
- **Data field / source:** mean opponent Elo over each team's prior games.
- **Hypothesis:** Teams with gaudy records vs weak schedules are overrated; SoS corrects crude form.
- **Impact measured:** Δ SU + Δ log-loss vs NBA-12, largest early-season.

#### NBA-14 · Opponent defensive rating (as-of)   (Rung 3 - Opponent adjustment)
- **Data field / source:** opponent `def_rtg` via prior-only as-of merge (`OPP_DEF_RATING`).
- **Hypothesis:** You score less against elite defenses; conditioning offense on opponent defense sharpens total.
- **Impact measured:** Δ total-MAE + per-team points MAE vs NBA-13.

#### NBA-15 · Opponent offensive rating (as-of)   (Rung 3 - Opponent adjustment)
- **Data field / source:** opponent `off_rtg` via backward-exclusive as-of merge.
- **Hypothesis:** Facing a high-powered offense raises points conceded; pairs with NBA-14 to pin the total.
- **Impact measured:** Δ total-MAE + Δ margin-MAE vs NBA-14.

#### NBA-16 · Net-rating differential (opponent-adjusted matchup)   (Rung 3 - Opponent adjustment)
- **Data field / source:** `NET_DIFF = HOME_NET − AWAY_NET` built on opponent-adjusted ratings.
- **Hypothesis:** The adjusted net-rating gap is the cleanest single margin predictor once opponent context is in.
- **Impact measured:** Δ margin-MAE + Δ SU vs NBA-15.

#### NBA-17 · Days of rest (both teams)   (Rung 4 - Rest / schedule / travel)
- **Data field / source:** `team_days_rest` → `HOME_REST`, `AWAY_REST`, `REST_DIFF`.
- **Hypothesis:** More rest lifts performance; the rest differential moves margin.
- **Impact measured:** Δ SU + Δ margin-MAE vs NBA-16, sliced by rest-mismatch.

#### NBA-18 · Back-to-back flag (both teams)   (Rung 4 - Rest / schedule / travel)
- **Data field / source:** `team_is_b2b` (`team_days_rest <= 1`) → `HOME_B2B`, `AWAY_B2B`.
- **Hypothesis:** The second night of a back-to-back is a well-known drag, especially on the road.
- **Impact measured:** Δ SU + Δ margin-MAE vs NBA-17, isolated on B2B games.

#### NBA-19 · Schedule density, games in last 7 days   (Rung 4 - Rest / schedule / travel)
- **Data field / source:** trailing 7-day game count per team.
- **Hypothesis:** 3-in-4 / 4-in-6 congestion fatigues teams beyond a single B2B flag.
- **Impact measured:** Δ margin-MAE + Δ total-MAE vs NBA-18 on high-density spots.

#### NBA-20 · Travel distance since last game   (Rung 4 - Rest / schedule / travel)
- **Data field / source:** `haversine_miles` between previous and current arena via `TEAM_GEO`.
- **Hypothesis:** Long trips (and cumulative road miles) shave a little off performance.
- **Impact measured:** Δ margin-MAE vs NBA-19, long-haul games (expect small).

#### NBA-21 · Time-zone change / body-clock shift   (Rung 4 - Rest / schedule / travel)
- **Data field / source:** Δ `tz_offset_hours` between previous and current arena.
- **Hypothesis:** East↔West body-clock disruption hurts the traveling team beyond raw miles.
- **Impact measured:** Δ margin-MAE vs NBA-20 on multi-zone trips.

#### NBA-22 · Per-possession efficiency (ORtg/DRtg)   (Rung 5 - Derived efficiency)
- **Data field / source:** rolling `off_rtg` / `def_rtg` used directly (replacing raw points), prior-only.
- **Hypothesis:** Points-per-100 normalizes for pace, a strictly better strength signal than raw points.
- **Impact measured:** Δ margin-MAE + Δ SU vs the points-based rungs.

#### NBA-23 · Pace (both teams) + pace sum   (Rung 5 - Derived efficiency)
- **Data field / source:** rolling `pace` → `HOME_PACE`, `AWAY_PACE`, `PACE_SUM`.
- **Hypothesis:** Two fast teams inflate possessions and the total; pace is the dominant lever on the game total.
- **Impact measured:** Δ total-MAE vs NBA-22 (expect the biggest total-MAE gain of the ladder).

#### NBA-24 · Effective FG% (eFG%, off & def)   (Rung 5 - Derived efficiency)
- **Data field / source:** `efg_pct` and `opp_efg_pct`, rolling prior-only.
- **Hypothesis:** Shooting efficiency is the heaviest four-factor; own vs opponent-allowed drives scoring.
- **Impact measured:** Δ total-MAE + per-team points MAE vs NBA-23.

#### NBA-25 · Turnover rate (TOV%, off & def)   (Rung 5 - Derived efficiency)
- **Data field / source:** `tov_pct` and `opp_tov_pct`, rolling prior-only.
- **Hypothesis:** Giving the ball away (and forcing giveaways) swings possession counts and points.
- **Impact measured:** Δ margin-MAE + Δ total-MAE vs NBA-24.

#### NBA-26 · Offensive-rebound rate (OREB%, off & def)   (Rung 5 - Derived efficiency)
- **Data field / source:** `oreb_pct` and `opp_oreb_pct` (and `dreb_pct`), rolling prior-only.
- **Hypothesis:** Second-chance rate adds possessions and points, especially vs poor defensive-rebounding opponents.
- **Impact measured:** Δ total-MAE vs NBA-25.

#### NBA-27 · Free-throw rate (FTA rate, off & def)   (Rung 5 - Derived efficiency)
- **Data field / source:** `fta_rate` and `opp_fta_rate`, rolling prior-only.
- **Hypothesis:** Getting to the line (the fourth factor) is efficient scoring and a modest total lift.
- **Impact measured:** Δ total-MAE vs NBA-26 (completes the four-factors block).

#### NBA-28 · Three-point reliance (shot & scoring mix)   (Rung 5 - Derived efficiency)
- **Data field / source:** `pct_fga_3pt`, `pct_pts_3pt`, rolling prior-only.
- **Hypothesis:** Three-heavy teams have wider outcomes; reliance should widen margin σ and slightly move totals.
- **Impact measured:** Δ log-loss / margin-σ calibration + Δ total-MAE vs NBA-27.

#### NBA-29 · Pace-interaction expected-possessions term   (Rung 6 - Matchup & interaction)
- **Data field / source:** interaction of both teams' rolling `pace` (product/harmonic) vs the additive `PACE_SUM`.
- **Hypothesis:** Realized possessions are jointly determined; a proper interaction predicts totals better than the sum.
- **Impact measured:** Δ total-MAE vs the additive `PACE_SUM` model.

#### NBA-30 · Offense-vs-defense style cross terms   (Rung 6 - Matchup & interaction)
- **Data field / source:** interactions of own `off_rtg`/`efg_pct` with opponent `def_rtg`/`opp_efg_pct`.
- **Hypothesis:** A great offense vs a great defense isn't the average, the cross term captures matchup-specific scoring.
- **Impact measured:** Δ margin-MAE + per-team points MAE vs NBA-16.

#### NBA-31 · Transition / paint-scoring style match   (Rung 6 - Matchup & interaction)
- **Data field / source:** own `pct_pts_fbps`, `pct_pts_pitp` vs opponent `opp_fbps`/`opp_pitp` allowed.
- **Hypothesis:** Fast-break-heavy offenses feast on teams that concede transition/paint points.
- **Impact measured:** Δ total-MAE + Δ margin-MAE vs NBA-30.

#### NBA-32 · Assist-dependence (shot-creation) interaction   (Rung 6 - Matchup & interaction)
- **Data field / source:** `ast_pct` / `fgm_pct_ast` vs opponent defense, rolling prior-only.
- **Hypothesis:** Heavily assist-dependent offenses degrade more vs strong defenses than iso-heavy ones.
- **Impact measured:** Δ log-loss + Δ margin-MAE vs NBA-31 (expect small).

#### NBA-33 · Explicit home/road effect by team   (Rung 7 - Situational)
- **Data field / source:** `is_home_team` × team identity, informed by NBA-11 splits.
- **Hypothesis:** Per-team home advantage varies materially beyond the league-average constant.
- **Impact measured:** Δ SU + Δ margin-MAE vs NBA-01/16, per-team.

#### NBA-34 · Altitude (Denver / Utah)   (Rung 7 - Situational)
- **Data field / source:** `altitude_ft` from `TEAM_GEO` (threshold 3000 ft).
- **Hypothesis:** Visitors tire faster at altitude, a small, geographically-concentrated home edge.
- **Impact measured:** Δ margin-MAE vs NBA-33, restricted to DEN/UTA home games.

#### NBA-35 · Playoff-vs-regular-season context   (Rung 7 - Situational)
- **Data field / source:** `is_playoff` flag (3,240 playoff team-rows).
- **Hypothesis:** Playoff basketball is tighter and lower-scoring, a total/margin regime shift.
- **Impact measured:** Δ total-MAE + Δ margin-MAE vs NBA-16, sliced to playoff games.

#### NBA-36 · Late-season motivation / tanking proxy   (Rung 7 - Situational)
- **Data field / source:** games-remaining + season-to-date win% (from schedule sequence and `is_win`).
- **Hypothesis:** Eliminated/tanking teams (and contenders resting starters) underperform ratings down the stretch.
- **Impact measured:** Δ SU + Δ margin-MAE vs NBA-35 on late-season games.

#### NBA-37 · Schedule-spot / trap-game context   (Rung 7 - Situational)
- **Data field / source:** derived flags, road end of a long trip, both-on-B2B, big rest-mismatch (combines rest/travel).
- **Hypothesis:** Named "letdown/trap" spots carry residual signal once individual rest/travel mains are in.
- **Impact measured:** Δ margin-MAE vs NBA-19 on flagged spots (expect small).

#### NBA-38 · Rotation-minutes OUT (reconstructed availability)   (Rung 8 - Availability & personnel)
- **Data field / source:** `TM_OUT_MIN`, `TM_OUT_COUNT` from `team_availability.parquet` (expected rotation from prior 3 games, OUT set is same-day roster) → `HOME/AWAY_OUT_MIN`, `OUT_MIN_DIFF`.
- **Hypothesis:** Vacated rotation minutes is the single biggest thing the ratings-only model is blind to.
- **Impact measured:** Δ SU accuracy + Δ margin-MAE vs the prior model, walk-forward.

#### NBA-39 · Star-player-out points weighting   (Rung 8 - Availability & personnel)
- **Data field / source:** `TM_OUT_PTS`, `TM_TOP_OUT` → `HOME/AWAY_OUT_PTS`, `OUT_PTS_DIFF`.
- **Hypothesis:** Losing your leading scorer hurts far more than an equal quantity of bench minutes.
- **Impact measured:** Δ margin-MAE + Δ SU accuracy vs NBA-38 (minutes-only), on star-out games.

#### NBA-40 · Injury-adjusted team rating   (Rung 8 - Availability & personnel)
- **Data field / source:** Elo/net-rating discounted by `TM_OUT_MIN`/`TM_OUT_PTS` share (combines NBA-12/16 with NBA-38/39).
- **Hypothesis:** Folding availability into the strength prior predicts better than the rating or the availability term alone.
- **Impact measured:** Δ SU accuracy + Δ margin-MAE vs NBA-39, walk-forward.

---

## NHL 🏒

### Data availability: NHL
- **Source / client:** (1) **NHL public API** (`https://api-web.nhle.com/v1/`, no key), plugin already pulls `club-schedule-season`, `score/{date}`, `roster`, and skater `game-log`. Available-not-wired: `gamecenter/{id}/boxscore`, `play-by-play`, `right-rail`, `shiftcharts`. (2) **MoneyPuck** free shot-level CSVs, 1.7M+ shots since 2007-08, 124 attributes/shot incl. **xGoals**, plus team/goalie CSVs. MoneyPuck is **not yet cached on disk** → Rungs 5+ need a one-time backfill.
- **History:** schedules cached `data/nhl/schedule_{2015..2024}.parquet`; skater logs `2023,2024`. MoneyPuck shot-quality history back to **2007-08** (the constraint on Rung-5+ walk-forward).
- **Core fields / tables available:** per team-game (`load_team_games`): `game_id, season, game_date, home, away, home_goals, away_goals, status, is_home, goals, opp_goals`. Engineered: `OFF, DEF, WINPCT, FORM (L10 goal-diff), REST, PRIOR_DIFF`, + diffs. Skater logs: `points (G+A), shots, toi, is_home, opp`. MoneyPuck (per game×team, situation 5on5/5on4/4on5/all): `xGoalsFor/Against`, `shotAttemptsFor/Against` (Corsi), `unblockedShotAttemptsFor/Against` (Fenwick), `highDangerShotsFor/Against`, `highDangerxGoalsFor/Against`, `savedShotsOnGoalAgainst`; per-goalie: `xGoals, goals, savePctg`. Boxscore/right-rail exposes **confirmed starting goaltenders**, PP `powerPlayConversion`, and `lastPeriodType` (REG/OT/SO).
- **Known gaps / limits:** (a) cached schedule has only `status ∈ {OFF, FINAL}` + goals, **no OT/SO flag yet**, so regulation-result target needs a boxscore backfill of `lastPeriodType`. (b) A **pre-game** starting goalie isn't in any cached table, boxscore has confirmed starters ~30–60 min pre-puck → the goalie feature needs live scraping and is a same-day signal. (c) MoneyPuck + NHL API are unofficial → retries/graceful-skip. (d) shootout-decided games attribute the winner in goals → handle so `y_margin`/winner don't over-credit shot-quality.

### Feature ladder: NHL

#### NHL-01 · Season-to-date goals for (OFF)   (Rung 1 - Basic box stats)
- **Data field / source:** `goals` → `OFF` expanding mean, `shift(1)`.
- **Hypothesis:** Teams scoring more per game so far will score more tonight.
- **Impact measured:** Δ score MAE vs a league-mean (3.1 g/g) constant, walk-forward 2015–2024.

#### NHL-02 · Season-to-date goals against (DEF)   (Rung 1 - Basic box stats)
- **Data field / source:** `opp_goals` → `DEF` expanding mean, `shift(1)`.
- **Hypothesis:** Teams allowing fewer goals will allow fewer tonight.
- **Impact measured:** Δ total MAE + Δ margin MAE vs NHL-01-only.

#### NHL-03 · Win% to date (WINPCT)   (Rung 1 - Basic box stats)
- **Data field / source:** `win = goals > opp_goals` → `WINPCT` expanding, `shift(1)`.
- **Hypothesis:** A higher season win rate predicts a higher win probability tonight.
- **Impact measured:** Δ winner accuracy + Δ log-loss vs a 55% home prior.

#### NHL-04 · Net goal differential (NET_DIFF)   (Rung 1 - Basic box stats)
- **Data field / source:** `(HOME_OFF − HOME_DEF) − (AWAY_OFF − AWAY_DEF)`.
- **Hypothesis:** The gap in goal differentials is the best day-1 margin signal.
- **Impact measured:** Δ margin MAE + Δ winner log-loss vs OFF/DEF separately.

#### NHL-05 · Home-ice indicator   (Rung 1 - Basic box stats)
- **Data field / source:** `is_home` → intercept/last-change advantage.
- **Hypothesis:** The home team wins ≈ 54–55%.
- **Impact measured:** Δ winner accuracy vs a no-home-term model; report the fitted home-goal bump.

#### NHL-06 · Prior-season goal differential (PRIOR_DIFF)   (Rung 1 - Basic box stats)
- **Data field / source:** prior-season mean `diff` merged on `season+1` (leakage-safe carryover).
- **Hypothesis:** Last year's goal diff is a useful cold-start prior for the first ~15 games.
- **Impact measured:** Δ margin MAE on each team's first 15 games, walk-forward.

#### NHL-07 · Last-10 goal-differential form (FORM)   (Rung 2 - Rolling windows)
- **Data field / source:** `diff` → `FORM` = `shift(1).rolling(10).mean()`.
- **Hypothesis:** Recent 10-game goal differential captures current form better than season mean.
- **Impact measured:** Δ margin MAE + Δ winner log-loss vs NET_DIFF-only.

#### NHL-08 · Rolling goals for/against, last-10   (Rung 2 - Rolling windows)
- **Data field / source:** `goals`/`opp_goals` → `shift(1).rolling(10).mean()`.
- **Hypothesis:** A recent-form scoring/defense rate beats the season mean once ~10 games exist.
- **Impact measured:** Δ score MAE vs expanding OFF/DEF; report the L10-vs-STD crossover count.

#### NHL-09 · Rolling win% (L10 / L20 points pace)   (Rung 2 - Rolling windows)
- **Data field / source:** `win` → `shift(1).rolling({10,20}).mean()`; points pace once OT flag backfilled.
- **Hypothesis:** A short-window points pace tracks true strength faster than season win%.
- **Impact measured:** Δ winner log-loss vs WINPCT-only across windows; pick the min-log-loss window.

#### NHL-10 · Rolling goal-diff volatility (L10 std)   (Rung 2 - Rolling windows)
- **Data field / source:** `diff` → `shift(1).rolling(10).std()`.
- **Hypothesis:** High goal-diff variance should widen predicted score intervals and soften win probability.
- **Impact measured:** Δ winner log-loss + interval calibration (coverage) vs mean-only form.

#### NHL-11 · Opponent-adjusted goals for/against (SoS)   (Rung 3 - Opponent adjustment)
- **Data field / source:** `opponent` + all opponents' `DEF`/`OFF` → SoS adjustment of NHL-01/02 (as-of).
- **Hypothesis:** Goals scored/allowed mean more once adjusted for defenses/offenses faced.
- **Impact measured:** Δ margin MAE + Δ total MAE vs raw OFF/DEF.

#### NHL-12 · Opponent defensive rating faced   (Rung 3 - Opponent adjustment)
- **Data field / source:** tonight's `opponent` → their `DEF`, as-of merge.
- **Hypothesis:** A team facing a leaky defense will out-score its baseline.
- **Impact measured:** Δ home/away-goals MAE vs own-OFF-only.

#### NHL-13 · Opponent goaltending faced (save-rate proxy)   (Rung 3 - Opponent adjustment)
- **Data field / source:** opponent team save rate from boxscore `saveShotsAgainst` (or MoneyPuck `savedShotsOnGoalAgainst/shotsOnGoalAgainst`), `shift(1)` rolling.
- **Hypothesis:** Team-level goaltending quality faced predicts scoring suppression independent of skater defense.
- **Impact measured:** Δ total MAE vs opponent-DEF-only; the team-level precursor to the goalie feature.

#### NHL-14 · Elo / iterative strength rating   (Rung 3 - Opponent adjustment)
- **Data field / source:** derived from `home/away` + `win` + `y_margin` (goal-margin-weighted Elo), chronological, `shift(1)`.
- **Hypothesis:** A single opponent-adjusted rating summarizes strength more cleanly than raw win%/diff.
- **Impact measured:** Δ winner accuracy + Δ log-loss vs NET_DIFF + FORM stack.

#### NHL-15 · Days rest   (Rung 4 - Rest / schedule / travel)
- **Data field / source:** `game_date.diff()` per team → `REST` (clipped 0–7).
- **Hypothesis:** More days of rest → sharper, higher-scoring, more-likely-to-win team.
- **Impact measured:** Δ winner log-loss + Δ margin MAE vs no-rest model.

#### NHL-16 · Rest differential (REST_DIFF)   (Rung 4 - Rest / schedule / travel)
- **Data field / source:** `HOME_REST − AWAY_REST`.
- **Hypothesis:** The rest edge between the two teams predicts margin better than either alone.
- **Impact measured:** Δ margin MAE + Δ winner accuracy vs rest-levels-only.

#### NHL-17 · Back-to-back flag (2nd of B2B)   (Rung 4 - Rest / schedule / travel)
- **Data field / source:** `REST == 0` (played yesterday) per team.
- **Hypothesis:** Teams on the 2nd night of a B2B win less and allow more (tired legs, backup goalie likely).
- **Impact measured:** Δ winner log-loss on the B2B subset; report the fitted penalty.

#### NHL-18 · Opponent rest / B2B (rest mismatch)   (Rung 4 - Rest / schedule / travel)
- **Data field / source:** opponent's `REST`/B2B via `opponent` as-of merge.
- **Hypothesis:** Facing a tired (B2B) opponent boosts your win prob and scoring more than your own rest helps.
- **Impact measured:** Δ winner accuracy on rested-vs-tired mismatch games vs symmetric REST_DIFF.

#### NHL-19 · Games in last 7 days (density/fatigue)   (Rung 4 - Rest / schedule / travel)
- **Data field / source:** rolling count of `game_date` within 7 days per team.
- **Hypothesis:** A congested week (3–4 games) drags down scoring and win rate late in the stretch.
- **Impact measured:** Δ margin MAE vs days-rest-only.

#### NHL-20 · Travel distance / time-zone change   (Rung 4 - Rest / schedule / travel)
- **Data field / source:** home-arena lat/long/tz table keyed by canonical `home` → great-circle + `Δtz` vs previous city.
- **Hypothesis:** Long west↔east and multi-zone jumps degrade the visitor (circadian penalty).
- **Impact measured:** Δ winner log-loss on high-travel road games vs no-travel model.

#### NHL-21 · xG for / against, rolling (MoneyPuck)   (Rung 5 - Derived efficiency)
- **Data field / source:** MoneyPuck `xGoalsFor` / `xGoalsAgainst` (situation `all`), `shift(1).rolling(10)`; backfill required.
- **Hypothesis:** Shot-quality xG is more stable and predictive than raw goals, the central NHL thesis.
- **Impact measured:** Δ total MAE + Δ margin MAE + Δ winner log-loss vs the goals-based stack, walk-forward from 2007-08.

#### NHL-22 · 5-on-5 xG differential   (Rung 5 - Derived efficiency)
- **Data field / source:** MoneyPuck `xGoalsFor − xGoalsAgainst` at `5on5`, rolling `shift(1)`.
- **Hypothesis:** Even-strength xG differential is the cleanest measure of underlying team quality.
- **Impact measured:** Δ winner log-loss vs all-situations xG-diff (NHL-21).

#### NHL-23 · Corsi / shot-attempt share (CF%)   (Rung 5 - Derived efficiency)
- **Data field / source:** MoneyPuck `shotAttemptsFor/(For+Against)` at `5on5`, rolling `shift(1)`.
- **Hypothesis:** Territorial shot-attempt share predicts future goal share better than past goals.
- **Impact measured:** Δ margin MAE vs goals-diff form; incremental value once xG is in.

#### NHL-24 · Fenwick / unblocked-attempt share (FF%)   (Rung 5 - Derived efficiency)
- **Data field / source:** MoneyPuck `unblockedShotAttemptsFor/Against` at `5on5`, rolling `shift(1)`.
- **Hypothesis:** Unblocked-attempt share adds marginal signal over raw Corsi.
- **Impact measured:** Δ log-loss vs CF%-only; expected small/near-zero (collinearity), publish either way.

#### NHL-25 · High-danger chance share   (Rung 5 - Derived efficiency)
- **Data field / source:** MoneyPuck `highDangerShotsFor/Against` and `highDangerxGoalsFor/Against`, rolling `shift(1)`.
- **Hypothesis:** Slot/high-danger chance share predicts goals better than total shot volume.
- **Impact measured:** Δ total MAE + Δ margin MAE vs Corsi/Fenwick-only.

#### NHL-26 · PDO (shooting% + save%)   (Rung 5 - Derived efficiency)
- **Data field / source:** MoneyPuck-derived `goalsFor/shotsOnGoalFor` + `1 − goalsAgainst/shotsOnGoalAgainst`, rolling `shift(1)`.
- **Hypothesis:** PDO far from 100 flags unsustainable luck; regressing it should improve forward margin prediction.
- **Impact measured:** Δ margin MAE when PDO enters as a mean-reversion term vs xG-only; a null/negative result is itself the story.

#### NHL-27 · Power-play % (PP)   (Rung 5 - Derived efficiency)
- **Data field / source:** boxscore `powerPlayConversion` or MoneyPuck `5on4 goalsFor / opportunities`, rolling `shift(1)`.
- **Hypothesis:** A hotter power play scores more and wins tight, penalty-filled games.
- **Impact measured:** Δ total MAE + Δ home/away-goals MAE vs even-strength-only model.

#### NHL-28 · Penalty kill % (PK)   (Rung 5 - Derived efficiency)
- **Data field / source:** boxscore PK / MoneyPuck `4on5 goalsAgainst / timesShorthanded`, rolling `shift(1)`.
- **Hypothesis:** A strong penalty kill suppresses opponent goals independent of even-strength defense.
- **Impact measured:** Δ opponent-goals MAE vs PP-only + even-strength stack.

#### NHL-29 · Special-teams net (PP% − opp PK%) interaction   (Rung 6 - Matchup & interaction)
- **Data field / source:** interaction of this team's `PP%` (NHL-27) with opponent's `PK%` (NHL-28), as-of.
- **Hypothesis:** A top power play vs a weak penalty kill is worth more than either rating alone.
- **Impact measured:** Δ total MAE vs PP% and PK% entered additively.

#### NHL-30 · xG-offense × opponent-xG-defense matchup   (Rung 6 - Matchup & interaction)
- **Data field / source:** interaction of team `xGoalsFor` rate (NHL-21) with opponent `xGoalsAgainst` rate, as-of.
- **Hypothesis:** The product of one team's shot-quality offense and the other's shot-quality defense beats a linear sum.
- **Impact measured:** Δ home/away-goals MAE vs additive xG features.

#### NHL-31 · Pace / combined shot-volume interaction (total)   (Rung 6 - Matchup & interaction)
- **Data field / source:** sum of both teams' `shotAttemptsFor` rates (Corsi pace) → total-goals predictor.
- **Hypothesis:** Two high-event teams produce higher totals than their individual rates suggest.
- **Impact measured:** Δ total MAE vs OFF+DEF-sum baseline.

#### NHL-32 · Style clash: high-danger interaction   (Rung 6 - Matchup & interaction)
- **Data field / source:** team `highDangerxGoalsFor` (NHL-25) × opponent `highDangerxGoalsAgainst`.
- **Hypothesis:** A high-danger-heavy attack against a team that bleeds slot chances over-performs its base rate.
- **Impact measured:** Δ margin MAE vs additive high-danger features; expected thin, publish the delta.

#### NHL-33 · Divisional / rivalry game   (Rung 7 - Situational)
- **Data field / source:** division lookup from canonical `home`/`away` (32-team → 4-division map).
- **Hypothesis:** Divisional games are tighter and lower-scoring, compressing margins.
- **Impact measured:** Δ margin MAE + interval calibration on divisional subset.

#### NHL-34 · Home/road split (as-of home & road form)   (Rung 7 - Situational)
- **Data field / source:** `is_home`-conditioned rolling `OFF`/`DEF`/`win` per team, `shift(1)`.
- **Hypothesis:** Some teams are meaningfully better at home vs on the road beyond the league constant.
- **Impact measured:** Δ winner log-loss vs a single home-ice term (NHL-05).

#### NHL-35 · Schedule spot: long homestand / road trip   (Rung 7 - Situational)
- **Data field / source:** consecutive `is_home` run-length per team.
- **Hypothesis:** Deep into a long road trip teams fade; early in a homestand they surge.
- **Impact measured:** Δ winner accuracy on trip-game≥4 subset vs the rest/travel stack.

#### NHL-36 · Regulation-result target (OT/SO handling)   (Rung 7 - Situational)
- **Data field / source:** boxscore `lastPeriodType` (REG/OT/SO) backfill → separate regulation winner from final; down-weight SO margins in `y_margin`.
- **Hypothesis:** Modeling regulation outcome (shootouts ≈ coin-flips) yields a better-calibrated winner probability than the raw final.
- **Impact measured:** Δ winner log-loss + calibration vs final-result-only target; report the SO-game accuracy ceiling.

#### NHL-37 · Confirmed starting goaltender   (Rung 8 - Availability & personnel)
- **Data field / source:** boxscore/`right-rail` confirmed starter + that goalie's MoneyPuck save-quality (`goals` vs `xGoals`, `savePctg`), as-of game-day.
- **Hypothesis:** The single biggest same-day NHL swing, a backup vs a Vezina starter reshapes win prob and total.
- **Impact measured:** Δ winner log-loss + Δ total MAE vs the team-only model, walk-forward.

#### NHL-38 · Backup / tandem / tired-starter flag   (Rung 8 - Availability & personnel)
- **Data field / source:** starter identity (NHL-37) cross-referenced with B2B (NHL-17) and starts-in-last-N from game logs.
- **Hypothesis:** A backup or a starter on his 3rd game in 4 nights underperforms.
- **Impact measured:** Δ total MAE + Δ winner log-loss on flagged games vs team-only.

#### NHL-39 · Key-skater injury / lineup availability   (Rung 8 - Availability & personnel)
- **Data field / source:** roster/scratch deltas from `roster` vs game-day lineup (top-line/PP-unit absences); optional injury feed.
- **Hypothesis:** Losing a top-line forward or #1 D-man measurably lowers a team's xG and win prob.
- **Impact measured:** Δ winner log-loss on games with a top-6 F or top-pair D out vs the prior model; expect a small residual after xG, publish it.

---

## MLB ⚾

### Data availability: MLB
- **Source / client:** Free **MLB StatsAPI** (`statsapi.mlb.com`, no key) is the plugin's spine, `sports/mlb/data.py` (schedules/results/probables), `pitcher_data.py`, `batter_data.py`. The ladder additionally taps **pybaseball → Statcast** (pitch physics), **FanGraphs** (wOBA/wRC+/FIP/xFIP), **Baseball-Reference**, and **Retrosheet**: wrapped behind the data adapter with retries + graceful skips.
- **History:** StatsAPI schedule + logs cached **2015–2025** (`schedule_{year}.parquet`, `pitcher_starts_{year}`, `batter_games_{year}`). **Statcast is pitch-level since 2015** (binding constraint for xwOBA/barrel%/spin). Retrosheet PBP ~a century for classic stats. Walk-forward trains 2015→N-1, tests year N.
- **Core fields / tables available:** *Schedule:* `game_id, season, game_date, home, away, home_score, away_score, home_sp, away_sp, status` (`home_sp`/`away_sp` = probable-pitcher ids). *Team-games:* `team, opponent, is_home, runs, opp_runs, sp, opp_sp`. *Pitcher starts:* `pitcher_id, date, K, IP, ER, BF, opp, is_home`. *Batter games:* `batter_id, date, hits, totalBases, homeRuns, atBats, is_home, team, name`. *Engineered team features:* `OFF, DEF, WINPCT, FORM (L10 run diff), REST, PRIOR_DIFF, SP_RA, SP_ERA` + diffs. *Statcast (to ingest):* `launch_speed`, `launch_angle`, `release_spin_rate`, `pfx_x/pfx_z`, `plate_x/plate_z`, `estimated_woba_using_speedangle` (xwOBA), `pitch_type`, `p_throws`, `stand`, `events`.
- **Known gaps / limits:** (1) **probable ≠ confirmed** starter, early rungs use rolling starter identity; the confirmed card is a later, lock-time feature. (2) no free park-factor/weather/umpire feed yet, new ingests (static park table, scraped weather, Retrosheet umpires). (3) Statcast pre-2015 doesn't exist. (4) StatsAPI/Savant unofficial-ish → rate-limit/skip. (5) historical lineup cards/bullpen availability scarce → forward-collection. (6) baseball is high-variance → single-feature deltas small over a large sample (reported honestly).

### Feature ladder: MLB

#### MLB-01 · Season-to-date runs scored per game (OFF)   (Rung 1 - Basic box stats)
- **Data field / source:** `runs` (StatsAPI scores), expanding mean `shift(1)` per team-season → `OFF`.
- **Hypothesis:** Teams scoring more runs to date score more tonight.
- **Impact measured:** Δ score-MAE (home/away runs) + Δ log-loss on winner, walk-forward 2016→2025.

#### MLB-02 · Season-to-date runs allowed per game (DEF)   (Rung 1 - Basic box stats)
- **Data field / source:** `opp_runs` expanding mean `shift(1)` → `DEF`.
- **Hypothesis:** Teams allowing fewer runs suppress the opponent tonight.
- **Impact measured:** Δ total-MAE + Δ margin-MAE vs MLB-01-only.

#### MLB-03 · Season-to-date win% (WINPCT)   (Rung 1 - Basic box stats)
- **Data field / source:** `win = runs>opp_runs`, expanding mean `shift(1)` → `WINPCT`.
- **Hypothesis:** Higher win% maps to a higher win probability (coarse prior).
- **Impact measured:** Δ winner accuracy + Δ log-loss vs OFF/DEF baseline.

#### MLB-04 · Net run differential per game (NET_DIFF)   (Rung 1 - Basic box stats)
- **Data field / source:** `(HOME_OFF − HOME_DEF) − (AWAY_OFF − AWAY_DEF)` (Pythagorean-style).
- **Hypothesis:** Run differential predicts future wins better than raw win% (regresses out record luck).
- **Impact measured:** Δ log-loss vs WINPCT-only; expect small positive.

#### MLB-05 · Prior-season run differential (PRIOR_DIFF)   (Rung 1 - Basic box stats)
- **Data field / source:** prior season's mean `diff` merged on `(team, season+1)` → cold-start prior for April.
- **Hypothesis:** Last year's run diff carries roster-strength signal into early games.
- **Impact measured:** Δ log-loss on first-30-games subset vs no-prior baseline.

#### MLB-06 · Last-10-game run-differential form (FORM)   (Rung 2 - Rolling windows)
- **Data field / source:** `diff` rolling(10) `shift(1)` → `FORM`.
- **Hypothesis:** Recent 10-game run diff captures current hot/cold state beyond the season mean.
- **Impact measured:** Δ margin-MAE + Δ log-loss vs expanding-only (MLB-01..05).

#### MLB-07 · Rolling runs scored/allowed, last-15 & last-30   (Rung 2 - Rolling windows)
- **Data field / source:** `runs` / `opp_runs` rolling(15) and rolling(30) `shift(1)`.
- **Hypothesis:** A medium window (≈2–4 weeks) balances signal vs noise better than season mean or last-10.
- **Impact measured:** Δ total-MAE across window choices; keep the min-holdout-MAE window.

#### MLB-08 · Home vs road split form (venue-conditioned)   (Rung 2 - Rolling windows)
- **Data field / source:** `runs`/`opp_runs` rolling within `is_home==1` vs `==0`, `shift(1)`.
- **Hypothesis:** Some teams' recent scoring is venue-dependent; splitting sharpens the run estimate.
- **Impact measured:** Δ score-MAE vs unsplit FORM (MLB-06/07).

#### MLB-09 · Rolling win% variants (last-10 / last-20)   (Rung 2 - Rolling windows)
- **Data field / source:** `win` rolling(10)/rolling(20) `shift(1)`.
- **Hypothesis:** Short-window win% adds a small momentum signal over season WINPCT.
- **Impact measured:** Δ winner log-loss vs expanding WINPCT; likely near-zero (weak MLB momentum, reported honestly).

#### MLB-10 · Opponent-adjusted offense/defense (SoS run rates)   (Rung 3 - Opponent adjustment)
- **Data field / source:** adjust `OFF`/`DEF` by mean `DEF`/`OFF` of opponents faced (season-to-date SoS, `shift(1)`).
- **Hypothesis:** Run rates padded vs weak pitching overstate strength; opponent-adjusting improves margin and total.
- **Impact measured:** Δ margin-MAE + Δ log-loss vs raw OFF/DEF.

#### MLB-11 · Opponent quality of pitching faced   (Rung 3 - Opponent adjustment)
- **Data field / source:** mean opposing-starter `SP_ERA`/team `DEF` faced in the rolling window, `shift(1)`.
- **Hypothesis:** A hot bat streak vs soft arms should be discounted.
- **Impact measured:** Δ total-MAE vs unadjusted rolling offense (MLB-07).

#### MLB-12 · Division / repeat-opponent familiarity   (Rung 3 - Opponent adjustment)
- **Data field / source:** flag from `opponent` + games-vs-opponent count (division opponents play ~13x).
- **Hypothesis:** Frequently-faced opponents produce lower-variance, slightly lower-scoring games.
- **Impact measured:** Δ total-MAE + margin calibration on division vs non-division; expect tiny.

#### MLB-13 · Days of rest / days since last game (REST)   (Rung 4 - Rest / schedule / travel)
- **Data field / source:** `game_date.diff().days` clipped 0–10 → `REST` / `REST_DIFF`.
- **Hypothesis:** Rest matters far less than other sports, but extremes still move output slightly.
- **Impact measured:** Δ score-MAE vs no-rest baseline; expect near-zero (deliberate honest null).

#### MLB-14 · Series game number & getaway-day flag   (Rung 4 - Rest / schedule / travel)
- **Data field / source:** position within series (consecutive same-opponent runs); getaway-day = final before travel.
- **Hypothesis:** Series openers and getaway finales differ subtly in run environment (bullpen state, lineup rest).
- **Impact measured:** Δ total-MAE by series-spot bucket.

#### MLB-15 · Day-after-night & doubleheader flags   (Rung 4 - Rest / schedule / travel)
- **Data field / source:** game start hour vs prior game's hour (StatsAPI `gameDate`); two `game_id`s same team/date → doubleheader.
- **Hypothesis:** Day-after-night and (esp. game 2 of) doubleheaders depress offense via fatigue/spot starters.
- **Impact measured:** Δ total-MAE on flagged games vs baseline.

#### MLB-16 · Travel distance & time-zone change   (Rung 4 - Rest / schedule / travel)
- **Data field / source:** great-circle between consecutive home-park lat/long (static table) + TZ delta.
- **Hypothesis:** Long west↔east jumps produce a small road-team run penalty.
- **Impact measured:** Δ margin-MAE vs no-travel baseline on high-distance subset; expect small.

#### MLB-17 · Team wOBA   (Rung 5 - Derived efficiency)
- **Data field / source:** FanGraphs team `wOBA` (or reconstructed from `hits/totalBases/BB/HBP` linear weights), rolling `shift(1)`.
- **Hypothesis:** wOBA weights each event by run value, predicting production better than raw runs/hits.
- **Impact measured:** Δ total-MAE + Δ margin-MAE vs OFF (MLB-01).

#### MLB-18 · Team wRC+ (park- & league-adjusted offense)   (Rung 5 - Derived efficiency)
- **Data field / source:** FanGraphs team `wRC+`, rolling `shift(1)` (100 = avg, park-neutral).
- **Hypothesis:** wRC+ isolates true hitting from park/league run environment, esp. for extreme parks.
- **Impact measured:** Δ margin-MAE vs wOBA-only (MLB-17).

#### MLB-19 · Team Statcast xwOBA (expected wOBA on contact)   (Rung 5 - Derived efficiency)
- **Data field / source:** Statcast `estimated_woba_using_speedangle` aggregated to team, rolling `shift(1)`.
- **Hypothesis:** xwOBA strips batted-ball luck from wOBA, giving a more stable, predictive estimate.
- **Impact measured:** Δ total-MAE vs wOBA (MLB-17); expect a real de-luck gain.

#### MLB-20 · Team barrel% and hard-hit%   (Rung 5 - Derived efficiency)
- **Data field / source:** Statcast `launch_speed` + `launch_angle` → barrel; hard-hit = `launch_speed ≥ 95`. Team rolling rate, `shift(1)`.
- **Hypothesis:** Quality-of-contact predicts future extra-base/run production earlier than results-based stats stabilize.
- **Impact measured:** Δ margin-MAE + Δ total-MAE vs xwOBA-only (MLB-19).

#### MLB-21 · Starting-pitcher rolling ERA (SP_ERA) & runs-allowed (SP_RA)   (Rung 5 - Derived efficiency)
- **Data field / source:** existing `SP_ERA` (ΣER·9/ΣIP over prior starts, keyed by `home_sp`/`away_sp`+date), `SP_RA`, + diffs.
- **Hypothesis:** *Who starts tonight* is the single biggest per-game MLB signal; recent ERA sharply improves winner and total.
- **Impact measured:** Δ winner log-loss + Δ total-MAE vs team-only run model; expect the largest single-rung gain so far.

#### MLB-22 · Starting-pitcher FIP / xFIP   (Rung 5 - Derived efficiency)
- **Data field / source:** FanGraphs starter `FIP`/`xFIP` (or from `K`, `BB`, `HR`, `IP`), rolling `shift(1)` over prior starts.
- **Hypothesis:** FIP/xFIP isolate the pitcher's controllables, predicting run prevention better than ERA.
- **Impact measured:** Δ total-MAE + Δ margin-MAE vs SP_ERA (MLB-21).

#### MLB-23 · Starting-pitcher K-BB%   (Rung 5 - Derived efficiency)
- **Data field / source:** `(K − BB)/BF` from pitcher-starts, rolling `shift(1)`.
- **Hypothesis:** K-BB% is the most stable, predictive single pitcher skill metric.
- **Impact measured:** Δ log-loss + Δ total-MAE vs FIP/xFIP (MLB-22).

#### MLB-24 · Starting-pitcher Statcast stuff (velo / spin / movement)   (Rung 5 - Derived efficiency)
- **Data field / source:** Statcast `release_speed`, `release_spin_rate`, `pfx_x`/`pfx_z` per starter, rolling `shift(1)`; velo-trend flag.
- **Hypothesis:** Declining velocity/spin foreshadows worse outcomes before ERA reacts.
- **Impact measured:** Δ total-MAE vs K-BB% (MLB-23); small but real on velo-drop subset.

#### MLB-25 · Bullpen quality (rolling reliever ERA/FIP)   (Rung 5 - Derived efficiency)
- **Data field / source:** team reliever runs/FIP (team `opp_runs` minus starter `ER`, or FanGraphs bullpen FIP), rolling `shift(1)`.
- **Hypothesis:** Since starters rarely finish games, bullpen quality is a large distinct run-prevention term.
- **Impact measured:** Δ margin-MAE + Δ total-MAE vs starter-only (MLB-21..24).

#### MLB-26 · Bullpen fatigue / recent usage   (Rung 5 - Derived efficiency)
- **Data field / source:** relief innings/pitches over the prior 2–3 days (StatsAPI game logs), `shift(1)`.
- **Hypothesis:** A gassed bullpen allows more late runs, nudging total up and win prob down.
- **Impact measured:** Δ total-MAE on high-recent-usage subset vs bullpen-quality-only (MLB-25).

#### MLB-27 · Starter × opposing-lineup platoon matchup   (Rung 6 - Matchup & interaction)
- **Data field / source:** starter handedness `p_throws` vs opposing lineup L/R composition (`stand`); starter's rolling xwOBA-allowed by batter hand.
- **Hypothesis:** A LHP vs a lefty-heavy lineup shifts expected runs beyond the starter's overall rate.
- **Impact measured:** Δ total-MAE + Δ margin-MAE vs handedness-blind starter model.

#### MLB-28 · Starter-quality × opponent-offense interaction   (Rung 6 - Matchup & interaction)
- **Data field / source:** `starter_xwOBA_allowed × opponent_team_xwOBA` (MLB-19 × MLB-24 inputs).
- **Hypothesis:** Elite-arm-vs-elite-bat games behave non-additively; an explicit interaction beats independent terms.
- **Impact measured:** Δ margin-MAE vs additive starter+offense model.

#### MLB-29 · Park run/HR factor   (Rung 6 - Matchup & interaction)
- **Data field / source:** static park run-factor & HR-factor table (Savant/FanGraphs) keyed by `home` venue.
- **Hypothesis:** Park effects materially move totals (Coors vs Petco).
- **Impact measured:** Δ total-MAE vs park-blind model; expect one of the larger total-MAE gains.

#### MLB-30 · Park × batted-ball-profile interaction   (Rung 6 - Matchup & interaction)
- **Data field / source:** park HR-factor × team `barrel%`/fly-ball rate (MLB-20 inputs).
- **Hypothesis:** A fly-ball/high-barrel offense gains more in a hitter's park than a groundball team.
- **Impact measured:** Δ total-MAE vs flat park factor (MLB-29).

#### MLB-31 · Batter-vs-pitcher handedness team aggregate (platoon edge)   (Rung 6 - Matchup & interaction)
- **Data field / source:** team's rolling `wOBA` vs LHP and vs RHP (`stand`×`p_throws` splits) matched to tonight's starter hand.
- **Hypothesis:** The lineup's platoon-specific offense is the right input given the announced starter's hand.
- **Impact measured:** Δ margin-MAE vs overall-wOBA offense (MLB-17).

#### MLB-32 · Home / road indicator (baseline home edge)   (Rung 7 - Situational)
- **Data field / source:** existing `is_home`; league home-scoring baseline.
- **Hypothesis:** Home teams win ~54%; last-at-bat/familiarity gives a small stable edge.
- **Impact measured:** Δ winner log-loss vs no-HFA baseline.

#### MLB-33 · Temperature effect on run environment   (Rung 7 - Situational)
- **Data field / source:** game-time temperature (StatsAPI game context / scraped weather) by `game_id`.
- **Hypothesis:** Warmer air carries the ball farther → more runs/HRs.
- **Impact measured:** Δ total-MAE vs weather-blind model on outdoor games.

#### MLB-34 · Wind speed & direction (out-to-CF vs in)   (Rung 7 - Situational)
- **Data field / source:** wind vector (scraped) × park orientation (static table).
- **Hypothesis:** Wind out (esp. Wrigley) sharply raises HR/run totals; wind in suppresses them.
- **Impact measured:** Δ total-MAE on strong-wind outdoor subset vs temperature-only (MLB-33).

#### MLB-35 · Roof / dome & precipitation state   (Rung 7 - Situational)
- **Data field / source:** roof-open/closed + dome flag (StatsAPI venue/`weather`), rain flag.
- **Hypothesis:** Closed roofs/domes create a neutral, slightly hitter-friendly, low-variance run environment.
- **Impact measured:** Δ total-MAE + total calibration on dome/closed subset.

#### MLB-36 · Home-plate umpire strike-zone tendency   (Rung 7 - Situational)
- **Data field / source:** umpire id (Retrosheet/StatsAPI officials) → rolling called-strike-rate / runs-per-game vs Statcast zone, `shift(1)`.
- **Hypothesis:** Pitcher-friendly umpires expand the zone, boosting Ks and suppressing runs.
- **Impact measured:** Δ total-MAE vs umpire-blind model; expect small.

#### MLB-37 · Confirmed starting pitcher (lineup-lock)   (Rung 8 - Availability & personnel)
- **Data field / source:** StatsAPI confirmed probable at/after lineup lock, replaces day-ahead `home_sp`/`away_sp`; re-key SP features.
- **Hypothesis:** Locking the true starter (catching scratches/bullpen games) is the highest-value pre-game info.
- **Impact measured:** Δ winner log-loss + Δ total-MAE at confirmed-time vs probable-time.

#### MLB-38 · Posted lineup card (regulars in/out, DH, order)   (Rung 8 - Availability & personnel)
- **Data field / source:** StatsAPI boxscore/lineup at lock, recompute team offense from present hitters' rolling wOBA/xwOBA (MLB-19/31).
- **Hypothesis:** Knowing who's actually playing refines the offensive input.
- **Impact measured:** Δ margin-MAE + Δ total-MAE vs roster-aggregate offense.

#### MLB-39 · Bullpen availability (rested/unavailable tonight)   (Rung 8 - Availability & personnel)
- **Data field / source:** prior-days relief usage (MLB-26) → per-reliever available/unavailable flag; available-bullpen-quality aggregate.
- **Hypothesis:** Explicit unavailability of top relievers raises late-game run risk beyond generic fatigue.
- **Impact measured:** Δ total-MAE on games with ≥2 top relievers down vs the fatigue proxy (MLB-26).

---

## Soccer ⚽

### Data availability: Soccer
- **Source / client:** `soccerdata` (wraps Club Elo, Understat, FBref, football-data.co.uk, ESPN, FotMob, Sofascore, WhoScored) + **StatsBomb Open** (`statsbombpy`). The live plugin (`backend/sports/soccer/team_features.py`) already fetches **football-data.co.uk** season CSVs and caches per-season parquet in `backend/data/soccer/`.
- **History:** football-data.co.uk back to **1993/94** for England (E0–E3 + Conference) and ~2000s for ~22 European leagues; deep results. Understat covers the **top-5 leagues from 2014/15**. Club Elo daily ratings back to 1939. StatsBomb Open is a curated non-contiguous set (World Cups, Euros, Messi's La Liga, select WSL/NWSL, Serie A 2015/16). Repo cache holds EPL 2021/22–2024/25.
- **Core fields / tables available:** football-data.co.uk (the model's real base, many leagues, shallow): `FTHG`/`FTAG` (→ `fthg`/`ftag`), `FTR` (H/D/A), `HTHG`/`HTAG`/`HTR`, and for bigger leagues `HS`/`AS` (shots), `HST`/`AST` (on target), `HC`/`AC` (corners), `HF`/`AF` (fouls), `HY`/`AY`/`HR`/`AR` (cards), `Referee`. *Understat* (top-5): team & per-shot **xG**, `xG`/`xGA`, `npxG`, `xpts`, shot `x`/`y`, `situation`, `shotType`. *Club Elo:* daily `Elo`. *StatsBomb Open:* full events + StatsBomb xG + 360 (select comps).
- **Known gaps / limits:**
  - **3-way outcome.** The target is **win / draw / loss** → the model must emit a real **P(draw)** (Poisson goals summed over a scoreline grid via `three_way_from_lambdas`). Draws are ~25% of matches and the **hardest class**; a picked side that draws counts as a **LOSS** (matches `seed_writer` grading).
  - **Per-league data-depth variance is severe.** xG (Understat) and events (StatsBomb) exist for a handful of comps; football-data gives results + basic match stats for ~22 leagues but **no xG, no lineups**. So Rungs 1–4 + 7 are league-wide; **Rung 5 (xG) is top-5-only**; deep event features are StatsBomb-comp-only. Each feature states its scope.
  - **FBref/Opta Jan-2026 caveat.** FBref lost its Opta licence in Jan 2026 and no longer updates advanced stats going forward; the historical archive is usable but frozen. Prefer Understat + StatsBomb for live advanced/xG.
  - **The hardest sport.** Soccer is CHALK's lowest-signal target: the 3-way outcome with a large irreducible draw class caps how far the ladder climbs, and early sweeps showed the Poisson base model gains little from thinner lower leagues. Deltas here are expected to be small, and are reported as such.

### Feature ladder: Soccer

#### SOC-01 · Home-field base rate (H/D/A prior)   (Rung 1 - Basic box stats)
- **Data field / source:** `FTR` (all leagues); repo's `_BASE = {p_home:0.45, p_draw:0.27, p_away:0.28}`.
- **Hypothesis:** A static league-average H/D/A split beats a uniform 1/3 prior because home advantage is real and stable.
- **Impact measured:** Walk-forward 3-way log-loss vs a uniform-third baseline, per season, pooled across leagues.

#### SOC-02 · Season goals-for / goals-against rate   (Rung 1 - Basic box stats)
- **Data field / source:** `FTHG`/`FTAG` season-to-date per team (all leagues).
- **Hypothesis:** Cumulative scoring/conceding rates separate strong from weak sides before opponent adjustment.
- **Impact measured:** Δ log-loss / Δ accuracy vs SOC-01; prior-only cumulative (`shift(1)`).

#### SOC-03 · Simple Poisson on goals (independent λ)   (Rung 1 - Basic box stats)
- **Data field / source:** `FTHG`/`FTAG` → per-team goal means → `three_way_from_lambdas` over a 0–10 grid (`MAX_GOALS`, all leagues). The repo's day-1 engine minus opponent strength.
- **Hypothesis:** Turning two goal-rate estimates into a full scoreline distribution yields a principled P(draw) and total.
- **Impact measured:** 3-way log-loss + **goals MAE** (predicted vs `FTHG+FTAG`) vs SOC-02.

#### SOC-04 · Win/draw/loss rate features   (Rung 1 - Basic box stats)
- **Data field / source:** derived from `FTR`, season W%, D%, L% per team (all leagues).
- **Hypothesis:** Result-outcome frequencies capture "draw-prone" clubs a pure goals model misses.
- **Impact measured:** Δ log-loss with a focus on **draw-class log-loss / Brier**.

#### SOC-05 · Rolling last-6 goals form (venue-split)   (Rung 2 - Rolling windows)
- **Data field / source:** `fthg`/`ftag` rolling `_prior_mean(s, ROLL=6)` split home/away, the repo's attack/defense.
- **Hypothesis:** Recent form (last 6) tracks the current squad/manager better than season-to-date.
- **Impact measured:** Δ log-loss / goals MAE vs SOC-03; sweep `ROLL ∈ {4,6,8,10}`.

#### SOC-06 · Rolling points-per-game form   (Rung 2 - Rolling windows)
- **Data field / source:** points from `FTR` (3/1/0), rolling last-N, prior-only (all leagues).
- **Hypothesis:** Recent PPG is a cleaner "are they winning right now" signal than goal difference.
- **Impact measured:** Δ accuracy / log-loss vs SOC-05.

#### SOC-07 · Rolling shots & shots-on-target form   (Rung 2 - Rolling windows)
- **Data field / source:** `HS`/`AS`, `HST`/`AST` rolling last-N (football-data **big leagues only**).
- **Hypothesis:** Shot volume/quality is more stable game-to-game than goals and pre-figures scoring regression.
- **Impact measured:** Δ log-loss vs SOC-05, reported **split by league-has-shots vs not**.

#### SOC-08 · Rolling goals-conceded / clean-sheet form   (Rung 2 - Rolling windows)
- **Data field / source:** `ftag` (conceded), clean-sheet indicator from `FTR`/goals, rolling last-N (all leagues).
- **Hypothesis:** Defensive form is more persistent than attacking form and sharpens λ_away and P(draw).
- **Impact measured:** Δ log-loss + **λ_away goals MAE**.

#### SOC-09 · Weighted recency (exponential decay)   (Rung 2 - Rolling windows)
- **Data field / source:** same `fthg`/`ftag` stream, exponential-decay weights vs flat window (all leagues).
- **Hypothesis:** Recency-weighting beats an equal-weight last-6.
- **Impact measured:** Δ log-loss vs SOC-05 across a half-life sweep.

#### SOC-10 · Club Elo rating (pre-match)   (Rung 3 - Opponent adjustment)
- **Data field / source:** Club Elo daily `Elo` via `soccerdata.ClubElo`, as-of match date, backward-exclusive (many leagues).
- **Hypothesis:** A single opponent-adjusted rating (Elo discounts schedule) beats raw form, which ignores who you played.
- **Impact measured:** Δ log-loss / Δ accuracy vs SOC-05; the first big expected jump.

#### SOC-11 · Elo difference → 1X2 mapping (with draw band)   (Rung 3 - Opponent adjustment)
- **Data field / source:** home `Elo` − away `Elo` + home-field bump, mapped to P(H/D/A) via a fitted ordinal link.
- **Hypothesis:** Elo gap plus an explicit draw band predicts draws better than a Poisson diagonal.
- **Impact measured:** Δ **draw-class** log-loss + overall log-loss vs SOC-10; calibration curve.

#### SOC-12 · Dixon-Coles attack/defense strengths   (Rung 3 - Opponent adjustment)
- **Data field / source:** `fthg`/`ftag` → per-team attack & defense + home-field (the repo's `home_attackaway_defenseHOME_FIELD*league_avg` λ), upgraded to jointly-fit **Dixon-Coles** ρ (all leagues).
- **Hypothesis:** Jointly estimating attack/defense and the low-score correlation ρ fixes the independent-Poisson under-prediction of 0–0/1–1 draws.
- **Impact measured:** Δ log-loss + **P(draw) calibration** vs SOC-03/SOC-10; goals MAE.

#### SOC-13 · Dixon-Coles time-decay weighting   (Rung 3 - Opponent adjustment)
- **Data field / source:** the SOC-12 fit with the Dixon-Coles exponential time-decay ξ on match age (all leagues).
- **Hypothesis:** Down-weighting old matches tracks squad changes and beats an unweighted fit.
- **Impact measured:** Δ log-loss vs SOC-12 over a ξ half-life sweep.

#### SOC-14 · Promoted / relegated cold-start prior   (Rung 3 - Opponent adjustment)
- **Data field / source:** cross-season club continuity from football-data; seed newly-promoted teams from prior-division Elo/finish (all leagues with promotion).
- **Hypothesis:** Shrinking a promoted side toward a "newly-promoted" prior beats the neutral 1.0 rating pre-`MIN_PRIOR`.
- **Impact measured:** Δ log-loss on **August/September fixtures only** (the cold-start window).

#### SOC-15 · Days of rest (home & away)   (Rung 4 - Rest / schedule / congestion)
- **Data field / source:** days since each team's previous `date` (all leagues).
- **Hypothesis:** A rested side outperforms one on short rest; small but real in congested stretches.
- **Impact measured:** Δ log-loss / goals MAE vs SOC-12.

#### SOC-16 · Rest-differential (home − away)   (Rung 4 - Rest / schedule / congestion)
- **Data field / source:** signed difference of SOC-15 (all leagues).
- **Hypothesis:** The gap in rest predicts better than each side's absolute rest.
- **Impact measured:** Δ accuracy on the subset where |rest gap| ≥ 2 days.

#### SOC-17 · Midweek European-fixture fatigue   (Rung 4 - Rest / schedule / congestion)
- **Data field / source:** UCL/UEL match dates flagged onto each club's next-weekend league match; weekday-of-match (all leagues, richest for top-5 European clubs).
- **Hypothesis:** Clubs playing a midweek European tie underperform their strength on the following matchday.
- **Impact measured:** Δ log-loss on the flagged subset vs SOC-12.

#### SOC-18 · Fixture congestion (matches in last 10/14 days)   (Rung 4 - Rest / schedule / congestion)
- **Data field / source:** count of each club's matches in trailing 10/14-day windows from `date` (all leagues).
- **Hypothesis:** Rolling match density degrades performance beyond single-game rest.
- **Impact measured:** Δ log-loss vs SOC-15/16.

#### SOC-19 · Travel distance / cross-country trips   (Rung 4 - Rest / schedule / congestion)
- **Data field / source:** stadium lat/long (static club-geo table) → haversine for the away side (NBA `geo.py` pattern; all leagues once geo filled).
- **Hypothesis:** Long away trips cost the traveling team; mostly a totals/λ_away nudge.
- **Impact measured:** Δ log-loss on the long-trip tail.

#### SOC-20 · Understat team xG / xGA form   (Rung 5 - Derived efficiency)
- **Data field / source:** Understat `xG`/`xGA` rolling last-N (**top-5 leagues only, 2014/15+**).
- **Hypothesis:** Rolling xG estimates true scoring rate better than rolling goals (less finishing noise).
- **Impact measured:** Δ log-loss / goals MAE vs SOC-05 on **top-5 matches only**.

#### SOC-21 · Poisson driven by xG instead of goals   (Rung 5 - Derived efficiency)
- **Data field / source:** Understat team `xG`/`xGA` fed into the Dixon-Coles λ in place of `fthg`/`ftag` (top-5 leagues).
- **Hypothesis:** Strengths built on xG regress less and predict better than strengths built on realized goals.
- **Impact measured:** Δ log-loss vs SOC-12 head-to-head on top-5 matches; calibration.

#### SOC-22 · xG-difference form vs raw goal-difference form   (Rung 5 - Derived efficiency)
- **Data field / source:** rolling (xG − xGA) vs rolling (GF − GA) as competing features (top-5 leagues).
- **Hypothesis:** A team over/under-performing its xG will regress; xG-diff carries info the scoreboard already spent.
- **Impact measured:** Δ log-loss from adding xG-diff on top of goal-diff (ablation).

#### SOC-23 · Non-penalty xG (npxG) form   (Rung 5 - Derived efficiency)
- **Data field / source:** Understat `npxG`/`npxGA` (top-5 leagues).
- **Hypothesis:** Stripping penalties (noisy, low-frequency) gives a more stable underlying-quality estimate.
- **Impact measured:** Δ log-loss vs SOC-20/21.

#### SOC-24 · Shot quality (xG per shot) & shot volume   (Rung 5 - Derived efficiency)
- **Data field / source:** Understat shot-level `xG` → xG/shot + shot count (top-5); StatsBomb shot xG for open-data comps.
- **Hypothesis:** Separating chance volume from chance quality explains variance a single xG hides.
- **Impact measured:** Δ log-loss vs SOC-20.

#### SOC-25 · Expected points (xPts) form   (Rung 5 - Derived efficiency)
- **Data field / source:** Understat `xpts` rolling (top-5 leagues).
- **Hypothesis:** Expected-points trend is a compact, draw-aware efficiency summary that improves the 1X2 head.
- **Impact measured:** Δ log-loss incl. **draw class**.

#### SOC-26 · Home/away performance split (team-specific HFA)   (Rung 6 - Matchup & interaction)
- **Data field / source:** already venue-split in the repo; make the home-advantage term **team-specific** rather than the global `HOME_FIELD=1.19` (all leagues).
- **Hypothesis:** Home advantage varies by club (fortress vs poor travelers); a per-team term beats one constant.
- **Impact measured:** Δ log-loss vs the single-constant model (SOC-12).

#### SOC-27 · Style mismatch: possession vs direct   (Rung 6 - Matchup & interaction)
- **Data field / source:** possession / pass-completion / pace proxies from Understat + StatsBomb events (top-5 + StatsBomb comps); shot-shape from football-data big leagues.
- **Hypothesis:** Certain style pairings (low-block vs possession) shift outcome/draw probability beyond raw strength.
- **Impact measured:** Δ log-loss from style-interaction terms vs SOC-12; top-5 subset.

#### SOC-28 · Favorite-vs-underdog interaction (Elo gap × home)   (Rung 6 - Matchup & interaction)
- **Data field / source:** interaction of Elo gap (SOC-11) with home/away and with rest (all leagues).
- **Hypothesis:** Home advantage matters more for evenly-matched games than lopsided ones.
- **Impact measured:** Δ log-loss vs additive model.

#### SOC-29 · Head-to-head history   (Rung 6 - Matchup & interaction)
- **Data field / source:** prior meetings of the exact pair from football-data history (all leagues, deep archive).
- **Hypothesis:** Some pairings have persistent stylistic outcomes beyond current strength (weak signal, test honestly).
- **Impact measured:** Δ log-loss from H2H term (expected near-zero). Report even if null.

#### SOC-30 · League-specific home advantage & draw rate   (Rung 7 - Situational)
- **Data field / source:** per-league home-win% and draw% from `FTR` (all leagues).
- **Hypothesis:** Home edge and draw frequency vary by league/country; a per-league prior beats a global one, important as we widen past the EPL.
- **Impact measured:** Δ log-loss pooled across leagues vs a global constant.

#### SOC-31 · Derby / local-rivalry flag   (Rung 7 - Situational)
- **Data field / source:** static rivalry table keyed by club pair (all leagues).
- **Hypothesis:** Derbies compress favorites and raise draw/card variance; a derby flag shifts P(draw) up.
- **Impact measured:** Δ **draw-class** log-loss on the derby subset.

#### SOC-32 · Title / relegation / European stakes (late season)   (Rung 7 - Situational)
- **Data field / source:** league-position + points-gap context from standings built off `FTR`, plus matchday number (all leagues).
- **Hypothesis:** Motivation asymmetry late in the season moves outcomes beyond strength.
- **Impact measured:** Δ log-loss on final-quarter-of-season fixtures.

#### SOC-33 · Dead-rubber / rotation risk   (Rung 7 - Situational)
- **Data field / source:** standings context (nothing to play for) + upcoming cup/European fixture proximity (all leagues; congestion from SOC-17/18).
- **Hypothesis:** Safe teams with a big midweek fixture rotate and underperform their rating.
- **Impact measured:** Δ log-loss on flagged dead-rubber/rotation subset.

#### SOC-34 · Confirmed starting XI strength   (Rung 8 - Availability & personnel)
- **Data field / source:** confirmed lineups (~1h pre-kickoff) via Sofascore/FotMob (`soccerdata`); rate the XI by players' Understat xG/xA (top leagues where lineups + player xG exist).
- **Hypothesis:** Knowing the actual XI (rotation, rested stars) refines each side's strength. Needs pre-match timing the model shouldn't "know" at build time.
- **Impact measured:** Δ 3-way log-loss vs SOC-21 on matches with confirmed XI.

#### SOC-35 · Key-player / injury availability   (Rung 8 - Availability & personnel)
- **Data field / source:** injury/suspension lists (FotMob/Sofascore) mapped to player xG/xA weight; suspensions inferable from `HR`/second-yellow history (top leagues).
- **Hypothesis:** A missing high-xG creator or first-choice keeper degrades a side more than a uniform rating implies.
- **Impact measured:** Δ 3-way log-loss on matches with a flagged absence vs the prior model; expect a small effect (the NBA analog found availability explained little), publish it.

---

## How this becomes the content calendar

Each rung is one "feature of the day/week" post: *tested X → here's the walk-forward delta → here's what's next.* Cadence per `CHALK_MASTER_PLAN.md` §7 (NFL/CFB ~twice a week, NBA/NHL daily, MLB/soccer a few per week). Every rung reports its honest result against real outcomes, whether the feature helped, did nothing, or hurt, and the later availability rungs (Rung 8) are where the biggest single-game swings get tested.

**Buildable today (cached data, zero new ingests):** NFL/NBA/NHL/MLB/soccer Rungs 1–4. **Needs a one-time free backfill first:** NFL PBP (Rung 5+), MLB Statcast/FanGraphs (Rung 5+), NHL MoneyPuck (Rung 5+), CFB the whole CFBD plugin. **Sequencing suggestion:** stand up the day-1 baseline + eval harness on NFL, prove the loop end-to-end on Rungs 1–3, then fan out.
