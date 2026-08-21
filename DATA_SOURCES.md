# Free, deep data sources for the big-5 (multi-sport roadmap)

Each new sport plugs into the existing sport-agnostic core (`backend/sports/<sport>/`
implementing the `Sport` ABC). A sport needs five things, all of which the free
sources below cover:

1. **Canonical teams** (a `teams.py` like NBA's)
2. **Schedule** (today's / historical games)
3. **Team game logs** (for the score/margin/total model)
4. **Player game logs + advanced/event data** (for player-prop models)
5. **Free historical odds** (for the walk-forward backtest: ATS / O-U / ROI / CLV)

The same engine carries over per sport: leakage-safe features → honest holdout +
calibration → hybrid global+per-player residuals → walk-forward backtest → cards.
The deep data is the fuel; our pipeline is the engine.

---

## 🏈 NFL — `nflverse` (gold standard, free, elite depth)

- **Python:** `pip install nfl_data_py` · **R:** `nflfastR` / `nflreadr`
- **Play-by-play** back to **1999** (EPA, CPOE, win probability, air yards, xYAC) —
  every play, every game. Repo: https://github.com/nflverse/nfl_data_py
- **Also free via nflverse:** weekly & seasonal player stats, rosters, depth charts,
  **snap counts**, schedules, **scoring lines (spreads/totals) and win totals built in**
  (so NFL backtesting needs *no external odds source*), officials, combine, draft, and
  a **Next Gen Stats** subset (speed/separation/air-yards).
- **FTN charting** (manual play charting) free from **2022+**.
- **Player tracking (x,y,speed):** Kaggle **NFL Big Data Bowl** datasets (select seasons) — pure gold for prop/route models.
- **Targets:** game margin/total/ML; player passing/rushing/receiving yards, TDs, receptions, attempts.

## ⚾ MLB — `pybaseball` + Statcast (deepest free sports data anywhere)

- **Python:** `pip install pybaseball` · repo: https://github.com/jldbc/pybaseball
- **Statcast pitch-by-pitch** (Baseball Savant) since **2015**: exit velocity, launch angle,
  **spin rate**, release point, pitch x/y/z location, perceived velocity — physics-level per pitch.
  https://baseballsavant.mlb.com/statcast_search
- **Retrosheet**: historical play-by-play + game logs back ~a century.
- **FanGraphs** advanced metrics + **Baseball-Reference** + the Chadwick player-id bureau (all wrapped by pybaseball).
- **MLB StatsAPI** (`statsapi.mlb.com`) — free official schedules/boxscores/live.
- **Targets:** run line/total/ML; pitcher strikeouts/outs/ER; batter hits/TB/HR/RBI. (Pitcher K props are extremely modelable with Statcast.)

## 🏒 NHL — NHL public API + MoneyPuck

- **NHL API** (unofficial but public): `https://api-web.nhle.com/v1/` — play-by-play, boxscores,
  schedules, standings, shifts. Endpoint reference: https://github.com/Zmalski/NHL-API-Reference
- **MoneyPuck** — free **shot-level CSVs**: **1.7M+ shots since 2007-08**, **124 attributes per shot**
  including their **xGoals (xG)** model score, updated nightly. https://moneypuck.com/data.htm
- **Python:** `pip install nhldata` (wraps NHL API + MoneyPuck).
- **Targets:** puck line/total/ML; skater points/shots/goals; **goalie saves** (very modelable with shot-quality/xG faced).

## ⚽ Soccer — StatsBomb Open + Understat + FBref + football-data.co.uk

- **Python:** `pip install soccerdata` (wraps Club Elo, ESPN, FBref, football-data.co.uk, FotMob,
  Sofascore, Understat, WhoScored) · **R:** `worldfootballR`
- **StatsBomb Open Data** — free **event-level** data (every pass/shot/carry) + **360 freeze-frames**
  for select competitions (World Cups, women's, Messi's La Liga career). Deepest free event data.
  https://github.com/statsbomb/open-data
- **Understat** — **xG + shot data** for the top-5 European leagues (clean, league-wide).
- **football-data.co.uk** — free CSVs of results **and historical bookmaker odds** for many leagues (ideal for soccer backtesting).
- **Targets:** 1X2 (win/draw/loss — needs a 3-way model), over/under goals, both-teams-to-score; player shots/goals/assists.
- ⚠️ **2026 caveat:** FBref **lost its Opta licence in Jan 2026** → it no longer updates advanced stats going forward; its historical archive is still useful. Prefer StatsBomb/Understat for live advanced data.

---

## Free historical odds for backtesting (per sport)

- **NFL:** built into `nfl_data_py` (scoring lines + win totals) — no external source needed.
- **Soccer:** **football-data.co.uk** (opening/closing odds, many leagues, free CSV).
- **MLB / NHL / cross-sport:** **Scottfree Analytics** free sample CSVs (MLB/NBA/NFL/NHL), **OddsPapi** free `/historical-odds` (all sports, CSV export), Kaggle sportsbookreview-derived datasets.
- These feed the `csv_backfill` `OddsProvider` we already built → the walk-forward backtest grades ATS/O-U/ROI/CLV.

## Recommended build order (by data quality × audience × cadence)

1. **NFL** — richest free data (odds built in), huge US audience, weekly cadence (gentle ops). Best first expansion.
2. **MLB** — Statcast depth is unmatched; pitcher-K and batter props are highly modelable; long season = lots of content.
3. **NHL** — MoneyPuck xG makes goalie-saves and totals very tractable.
4. **Soccer** — biggest global audience but hardest (3-way outcomes, many leagues, event data limited to select comps); do last.

## Caveats (same discipline as NBA)
- Several APIs are **unofficial** (NHL, Baseball Savant scraping) — wrap them behind the sport plugin's data adapter with retries + graceful skips (like our nightly steps), and respect rate limits.
- **Historical player-prop lines are scarce/absent for free** in every sport (same as NBA) → prop backtesting stays forward-collection + calibration; team-market backtesting is fully feasible.
- Deeper data ⇒ more predictive features, but the **same leakage discipline + overfitting guards** (prior-only construction, whitelist, honest holdout must improve) apply.
