# CHALK Feature Menu

The full inventory of what each model can be fed, so we can decide together what goes into the "use all the good features, maximize accuracy" build. This replaces the public one-feature-at-a-time ladder: we still add features deliberately and measure each, but we batch them and aim for the best model, not a story.

## The one rule we keep

Every feature earns its place by **lowering out-of-sample error** on the untouched walk-forward holdout (margin/total MAE, winner log-loss, or per-stat MAE for props). Not by sounding good. This is the instrument panel: it's how you see, for each decision, whether a feature helped, did nothing, or hurt. Without it, "accurate" is just training error lying to us.

Legend: **[IN]** = fed to the model today · **[OFF]** = built, sits in the frame, not fed (a switch-on) · **[BUILD]** = does not exist yet, needs new data and/or code. Resolution markers: **✓ KEPT** (measured, served) · **✗ DROPPED** (measured, did not beat baseline) · **⏸ PARKED** (external source down) · **⛔ BLOCKED** (needs data/credentials).

## Status as of 2026-11-16: the feed roadmap is mostly RESOLVED

When this menu was written almost every high-value gain was a [BUILD]. Most are now built and measured. All 6 sports have served team models; 5 of 6 serve player props (all but NBA). What's left is a short list of unresolved levers, below the snapshot.

**Resolved this cycle (✓ KEPT + served):** NFL opp-adj offense + EPA/play · NBA team interaction terms · MLB real SP_ERA + Statcast prior-season xwOBA · NHL MoneyPuck xG · soccer cross-season prior + home-field recalibration (1.19→0.90) · the entire CFB plugin (team + player) · player props for NFL, CFB, NHL (skater shots), MLB (pitcher K, batter hits/TB).

**Measured + DROPPED (✗, the referee said no):** NFL opp-adj defense (hurts winner acc) · MLB park factors (OFF/DEF already absorb it) · MLB Statcast within-season *rolling* xwOBA (worse than the season prior; per-game xwOBA is noisy) · NHL starting goalie save% (no winner signal; DEF/xG already encode goaltending) · soccer Dixon-Coles rho · low-count props served naive on purpose (NHL points, MLB home runs).

**Not resolved (the next-step candidates):** ⏸ soccer Club Elo / Understat xG (sources down since 2026-11-09) · ⛔ NBA player props (needs the R2 player-log bundle or a scrape) · the deeper feature clusters within already-wired feeds (NFL EPA sub-features, CFB efficiency ratings, NHL special teams), and systematic tuning of the prop models.

---

## Cross-sport snapshot

| Sport | Models served | Resolved (✓/✗) | Remaining levers |
|---|---|---|---|
| **NFL** | team + player props | ✓ opp-adj OFF, ✓ EPA off/def; ✗ opp-adj DEF | EPA sub-features (success rate, CPOE, QB-adjusted, pass/rush split), injuries/snaps |
| **NBA** | team (player props ⛔) | ✓ interaction terms | ⛔ player props (R2 data); confirmed-starter feed |
| **MLB** | team + pitcher K + batter | ✓ real SP_ERA, ✓ xwOBA prior; ✗ park factors, ✗ rolling xwOBA | confirmed starter/lineup at lock, bullpen fatigue, FIP/xFIP, weather |
| **NHL** | team + skater | ✓ MoneyPuck xG; ✗ starting goalie | special teams (PP/PK), regulation-result target, goalie GSAx (heavier) |
| **Soccer** | 3-way Poisson | ✓ cross-season, ✓ home-field; ✗ Dixon-Coles | ⏸ Club Elo, ⏸ Understat xG (both sources down) |
| **CFB** | team + player props | ✓ full plugin, ✓ opp-adj OFF+DEF | SP+/PPA efficiency ratings, team talent composite |

---

## NFL (team + player props)

**[IN] now (team):** box OFF/DEF/WINPCT, FORM, REST, weather (dome/wind/temp), DIV_GAME, **opp-adj OFF (✓)**, **OFF/DEF EPA/play (✓, the biggest NFL gain)**. Player props served (anchored residual, curated).

**✗ dropped:** opp-adj DEFENSE (hurt su_acc at both the NFL and re-test).

**[BUILD] remaining (all on the already-wired nflverse PBP feed, so incremental, cheap, measurable):**
- Success rate, CPOE, pass-vs-rush EPA split, pace/plays (NFL-21..25).
- QB-adjusted efficiency (NFL-43) - attribute EPA to the actual starter (the sharpest remaining EPA refinement).
- Pass-off x pass-def / rush-mismatch interactions (NFL-31..35).
- Injury/snap load (NFL-42) - needs `import_injuries` + `import_snap_counts`.

**Top remaining:** QB-adjusted EPA (43), success rate (21), pass mismatch (32). All ride the existing EPA pipeline (no new feed).

## NBA (team + player props blocked)

**[IN] now (team):** OFF/DEF/NET/PACE/REST/B2B + diffs + **availability** (TM_OUT_MIN/PTS/COUNT/TOP_OUT) + **Elo** + **interaction terms (✓)**. The deepest team model already.

**⛔ player props:** the v3 stack (trainer/predictor/features/backtest) exists but needs per-player game-log CSVs (`data/player_data/{slug}/`) that aren't local. Sources: the R2 training bundle (no creds in this env) or a Basketball-Reference scrape (slow/ToS-risky). This is the ONE player-prop gap (5/6 sports serve props). Unblock = provide R2 creds.

**[BUILD] remaining:** a live confirmed-starter / official-inactives feed (today availability is reconstructed pre-tip - good, but a live feed is the ceiling).

## MLB (team + pitcher K + batter) - Statcast RESOLVED

**[IN] now (team):** OFF/DEF/WINPCT/FORM/REST/PRIOR_DIFF, **SP_RA**, **real SP_ERA (✓, per-pitcher backfill)**.

**[IN] now (props):** pitcher **K (✓)**, batter **hits + totalBases (✓)**, each anchored-residual + **prior-season Statcast xwOBA (✓)**; home runs served naive (too low-count to model).

**✗ dropped (measured):** park factors (team OFF/DEF already absorb the park) · Statcast within-season *rolling* xwOBA (worse than the season-constant prior).

**[BUILD] remaining:**
- Confirmed starter + posted lineup at lock (MLB-37/38) - highest-value pre-game info, but a forward-collection problem (not a historical backfill).
- Bullpen quality + fatigue (relief IP prior days).
- FanGraphs FIP/xFIP, wRC+ (another quality layer beyond xwOBA).
- Weather (temp/wind) - needs a scraped feed.

**Note:** the heavy Statcast pitch feed is already pulled + cached (`data/mlb/game_xwoba_*`); a future variant (e.g. batter-vs-pitcher matchup xwOBA, or a different aggregation) could reuse it without re-pulling.

## NHL (team + skater)

**[IN] now (team):** OFF/DEF/WINPCT/FORM/REST/PRIOR_DIFF + **MoneyPuck xG off/def (✓, the strongest NHL winner signal added)**.

**[IN] now (props):** skater **shots (✓)**; points served naive (too noisy to model).

**✗ dropped:** starting-goalie rolling save% - NO winner signal (the DEF + xG ratings already encode goaltending; NHL winners sit near the ~0.58 SU ceiling).

**[BUILD] remaining:**
- Special teams (PP%/PK%).
- Regulation-result target for cleaner winner calibration (NHL-36, needs the boxscore OT/SO flag).
- Goalie **GSAx** (goals saved above expected) - a heavier metric than raw save% (needs per-goalie expected-goals-faced); the only untried goalie angle after save% failed.

## Soccer (3-way Poisson)

**[IN] now:** venue-split attack/defense ratings + **cross-season prior (✓)** + **recalibrated home-field 0.90 (✓, was a double-counted 1.19)**.

**✗ dropped:** Dixon-Coles rho (fixes draw calibration but costs log-loss + acc).

**⏸ PARKED [BUILD] (both blocked on external source outages since 2026-11-09):**
- **Club Elo** (SOC-10/11) - opponent-adjusted rating; `api.clubelo.com` returns 502.
- **Understat xG** (SOC-20..25) - true scoring rate; understat.com serves a maintenance page (no `teamsData`). FBref free xG is gated by the 2024 Opta licensing change (do not retry).

Resume when either source recovers: the design + join plan are in the worklog (`feed/soccer-xg` branch). Caveat: soccer is the lowest-signal target (~25% irreducible draw rate), so expect smaller deltas.

## CFB (team + player props) - fully built

**[IN] now (team):** box-score + **opp-adj OFF + DEF (✓, both help CFB winners)** + neutral-site / conference context.

**[IN] now (props):** passing/rushing/receiving yards + receptions (✓, all beat naive +5-8%).

**[BUILD] remaining (CFB-unique high-value):** SP+/PPA efficiency ratings (22/24), team talent composite (41), opponent-adjusted SoS (13). All on the existing CFBD key.

---

## How we'll work it

Per sport/model, a tight loop you drive:
1. I lay out the candidate set (from this menu) + the data each needs.
2. **You pick** what's in scope (and whether a [BUILD] feed is worth standing up).
3. I wire + train + show you **before/after OOS error**.
4. You see the real impact; we keep what moves the number.

## The next-step question

The data-feed roadmap is largely done, so the remaining improvement comes in three flavors:

1. **Deepen an already-wired feed (cheapest, no new data/creds, immediately measurable).** The NFL EPA pipeline is the best candidate: QB-adjusted EPA, success rate, and pass/rush split are all computable from the PBP we already pull. CFB efficiency ratings (SP+/PPA) are the analog on the CFBD key.
2. **Fill the one coverage gap: NBA player props.** Needs you to provide R2 credentials (or accept a slow scrape). Completes player-prop coverage across all 6 sports.
3. **Revisit the parked soccer xG** if Club Elo / Understat have recovered (a 2-minute re-check tells us), or **tune the existing prop models** (their LightGBM params are fixed defaults; a measured sweep may squeeze a little more).
