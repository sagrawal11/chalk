# CHALK Feature Menu

The full inventory of what each model can be fed, so we can decide together what goes into the "use all the good features, maximize accuracy" build. This replaces the public one-feature-at-a-time ladder: we still add features deliberately and measure each, but we batch them and aim for the best model, not a story.

## The one rule we keep

Every feature earns its place by **lowering out-of-sample error** on the untouched walk-forward holdout (margin/total MAE, winner log-loss, or per-stat MAE for props). Not by sounding good. This is the instrument panel: it's how you see, for each decision, whether a feature helped, did nothing, or hurt. Without it, "accurate" is just training error lying to us.

Legend: **[IN]** = fed to the model today · **[OFF]** = built, sits in the frame, not fed to the model (a switch-on) · **[BUILD]** = does not exist yet, needs new data and/or code.

## The uncomfortable truth up front

The genuine quick wins are small: the shipped trainers already use most of the base features. **Almost all the high-value gains are [BUILD]** - they need new data pipelines (play-by-play, Statcast, MoneyPuck xG, Club Elo, park factors) that aren't wired yet. So "use all features" is mostly a **data-engineering** roadmap, decided by "which feed do we stand up next," not a config flag. And one sport (CFB) has no model at all yet.

A caveat proven in your own code (`player_degeneracy_probe.py`): the NBA **player props** already tried the ~336-feature kitchen-sink and it was *degenerate*; v3 went to a curated ~15-feature set on purpose. More features reliably help **team** models (low variance); they can hurt **per-game player** props (noise). We measure per target.

---

## Cross-sport snapshot

| Sport | Model today | In the model now | Switch-on [OFF] | Biggest locked-up gains ([BUILD] -> data needed) |
|---|---|---|---|---|
| **NFL** | team margin/total | box + form + rest + weather + division | opponent-adjustment | **EPA/play** (wire play-by-play) |
| **NBA** | team + player | box + ratings + **availability** + Elo | (deepest already) | confirmed-starter feed; richer tracking |
| **MLB** | team + batter + pitcher | box + form + **SP_RA** + SP_ERA(filled) | **real SP_ERA** (run backfill) | park factors, Statcast xwOBA, FIP, bullpen |
| **NHL** | team + skater | box + form + rest | - | **xG/Corsi** (MoneyPuck), **starting goalie** (boxscore) |
| **Soccer** | 3-way Poisson | venue-split attack/def + home-field | Dixon-Coles rho, cross-season prior | **Club Elo**, **Understat xG** |
| **CFB** | **none** | - | - | **the entire CFBD plugin** (data + features + model) |

---

## NFL (team margin and total) - ~44 candidate features

**[IN] now:** HOME/AWAY OFF, DEF, WINPCT, FORM (last-3), REST, PRIOR_DIFF + NET_DIFF, REST_DIFF + IS_DOME, WIND, TEMP, DIV_GAME.

**[OFF] switch-on:** opponent-adjusted OFF/DEF (`OPP_ADJ_COLS`) - computed in the frame, not in the trainer's columns. The experiment champion found it helped; the nightly model still doesn't use it. One-line win.

**[BUILD] (the real gains, all need `nfl_data_py import_pbp_data` wired - installed, not hooked up):**
- **Offensive and defensive EPA/play** (NFL-19/20) - the single most predictive team-efficiency metric. Top priority.
- Success rate, CPOE, pass-vs-rush EPA split, pace/plays (NFL-21..25).
- Matchup interactions: pass-off x pass-def, rush mismatch, pace x pace (NFL-31..35).
- QB-adjusted efficiency (NFL-43) - attribute EPA to the actual starter.
- Injury/snap load (NFL-42) - needs `import_injuries` + `import_snap_counts`.

**Top 3 to build:** EPA off/def (19/20), QB-adjusted EPA (43), pass mismatch (32).

## NBA (team + player) - ~40 candidate features - deepest build

**[IN] now (team):** OFF, DEF, NET, PACE, REST, B2B (+ diffs) + **availability** (TM_OUT_MIN/PTS/COUNT/TOP_OUT) + **Elo**. The richest set already: ratings, pace, availability, travel/altitude, Elo, all via the 73-column Kaggle parquet.

**[OFF]:** little left - the one sport where "all features" is largely already true for the team model. Interaction terms (pace x pace, style cross-terms) are cheap to add and measure.

**[BUILD]:** a confirmed-starter / official-inactives feed (today availability is reconstructed pre-tip from prior minutes - good, but a live feed is the ceiling); richer tracking data is not free.

**Player props:** the degeneracy caveat lives here. v3 is curated on purpose; the lever that matters is **minutes** (driven by availability), already in v3. "Add all features" here = re-run the probe honestly, expect to keep it curated.

**Top 3:** verify pace and availability are maxed in the team model; measure interaction terms; leave props curated unless the OOS says otherwise.

## MLB (team + pitcher K + batter) - ~39 candidate features

**[IN] now (team):** OFF, DEF, WINPCT, FORM (last-10), REST, PRIOR_DIFF, **SP_RA** (starter rolling runs-allowed), SP_ERA columns (+ diffs).

**[OFF] switch-on:** **real SP_ERA** - the column exists but is league-average-filled unless the per-pitcher backfill runs (`fetch_sp_era=True`, ~100 cached calls/season). The sharpest already-designed pitcher signal.

**[BUILD] (biggest total/accuracy gains):**
- **Park factors** (MLB-29) - Coors vs Petco; one of the largest total-MAE gains. Needs a static park table.
- **Statcast** (pybaseball): team xwOBA, barrel%/hard-hit%, pitcher stuff (velo/spin).
- **FanGraphs**: wOBA, wRC+, FIP/xFIP.
- Bullpen quality + fatigue (relief IP prior days).
- Confirmed starter + posted lineup at lock (MLB-37/38) - highest-value pre-game info; forward-collected.
- Weather (temp/wind) - needs a scraped feed.

**Top 3 to build:** park factors (29), SP FIP/xFIP + team xwOBA (22/19), confirmed starter at lock (37). Plus the free switch-on: real SP_ERA.

## NHL (team + skater) - ~39 candidate features

**[IN] now (team):** OFF, DEF, WINPCT, FORM (last-10), REST, PRIOR_DIFF. The simplest team model; goals-based only.

**[OFF]:** none meaningful - the high-signal stuff isn't built.

**[BUILD] (this is where NHL accuracy actually lives):**
- **xG / Corsi / high-danger share** (NHL-21..25) - shot quality beats goals; the central NHL thesis. Needs a **MoneyPuck** CSV backfill (free, since 2007-08).
- **Starting goalie** (NHL-37) - the dominant same-day swing. Needs the **boxscore endpoint** (the schedule only exposes the post-game winning goalie). Highest-value, same-day.
- Special teams (PP%/PK%), regulation-result target for cleaner winner calibration (NHL-36, needs boxscore OT/SO flag).

**Top 3 to build:** xG + 5v5 xG-diff (21/22), confirmed goalie (37), regulation-result target (36).

## Soccer (3-way Poisson) - ~35 candidate features

**[IN] now:** venue-split attack/defense ratings + the 1.19 home-field multiplier.

**[OFF] switch-on:** Dixon-Coles rho (draw correction) and the cross-season prior - these exist as model knobs; the champion `soccer-v2` found cross-season helps, but the serving default may not use it. Reconcile and turn on.

**[BUILD]:**
- **Club Elo** (SOC-10/11) - the first big jump, opponent-adjusted, buildable league-wide via `soccerdata`.
- **Understat xG** (SOC-20..25) - true scoring rate, but top-5 leagues only, 2014/15+.

**Caveat:** soccer is the lowest-signal target (~25% irreducible draw rate); expect smaller deltas everywhere.

**Top 3:** Club Elo + Elo->1X2 (10/11), xG-driven Dixon-Coles (21), confirm rho/cross-season are on.

## CFB - nothing built yet

There is **no `sports/cfb/` plugin**. The whole sport is a [BUILD]: a CFBD API client + caching, a teams map, team/player features, and a model. Once the base `/games` client exists, the internal ladder mirrors the others. Highest-value once built: opponent-adjusted SoS (CFB-13), SP+/PPA efficiency ratings (22/24), team talent composite (41, CFB-unique).

---

## How we'll work it

Per sport/model, a tight loop you drive:
1. I lay out the candidate set (from this menu) + the data each needs.
2. **You pick** what's in scope (and whether a [BUILD] feed is worth standing up).
3. I wire + train + show you **before/after OOS error**.
4. You see the real impact; we keep what moves the number.

The old `roadmap.yaml` + `docs/FEATURE_ROADMAP.md` stay as the detailed backlog (every rung, hypothesis, exact data field). The champion/challenger/ledger "public climb" machinery is now optional; we can retire it whenever you like.

## The sequencing question for you

Two orthogonal axes to prioritize:
- **Breadth vs depth:** make all six sports solid at their current data depth first, or go deep on one sport's [BUILD] pipeline (e.g. NFL EPA) to prove the ceiling?
- **Which data feed first:** the highest-value [BUILD] feeds are NFL play-by-play, MLB Statcast + park factors, NHL MoneyPuck xG. Each is a one-time ingestion that unlocks a cluster of features.
