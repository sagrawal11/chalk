# Live track record (local)

The honest out-of-sample record: lock tonight's predictions **before** tip-off, grade
them against the finals the next day, and aggregate a running win% / streak / score-MAE.
No betting lines anywhere — just "did the favored side win" and "how far off was the
predicted score."

This is the runnable local loop. (`OPS_RUNBOOK.md` describes an aspirational CI version;
this is the thing that actually exists and that you run.) It is driven by
`backend/pipeline/track_record.py` on top of the existing primitives
(`track_record/lock.py`, `grade.py`, `aggregate.py`, `predictions/schema.py`).

## The three commands

Run from `backend/`:

```bash
# Pre-game: predict + immutably lock tonight's slate (default date = today)
python -m pipeline.track_record lock   --sport nhl [--date YYYY-MM-DD]

# Post-game: grade a locked slate against the finals (default date = yesterday)
python -m pipeline.track_record grade  --sport nhl [--date YYYY-MM-DD]

# Anytime: print the live record
python -m pipeline.track_record report [--sport nhl] [--all-sources]
```

`--sport all` runs every wired sport. `report` shows only genuinely live, forward-locked
rows by default; `--all-sources` also folds in the backtest-seed rows
(`pipeline/seed_track_record.py`).

Example (one NHL slate, end to end):

```
$ python -m pipeline.track_record lock  --sport nhl --date 2026-01-15
[nhl] locked 10 games for 2026-01-15 -> data/predictions/locked/nhl/2026-01-15.json
$ python -m pipeline.track_record grade --sport nhl --date 2026-01-15
[nhl] graded 10 games for 2026-01-15: 5-5 (50.0% SU) | +10 ledger rows
$ python -m pipeline.track_record report --sport nhl
RECORD 5-5 | win% 50.0% | streak +1 | n=10 | score MAE 1.495
```

## The nightly rhythm (you schedule it — no cron is installed)

1. **Before tip-off**, once the slate is set: `lock`. The lock is immutable and
   SHA-256-hashed, so a pick is honest by construction — it cannot be back-dated or edited
   after the result is known (re-running `lock` on a locked date refuses; `--force` exists
   only to correct a same-day error before tip).
2. **The next morning**, after games finish: `grade`. Idempotent (re-running adds nothing),
   so a retry is safe.

Wire it to launchd/cron yourself. Example crontab (adjust times to your slate / timezone):

```cron
# lock tonight's slate at 17:30 local, grade yesterday's at 09:00 local
30 17 * * *  cd /path/to/chalk/backend && python -m pipeline.track_record lock  --sport all
0  9  * * *  cd /path/to/chalk/backend && python -m pipeline.track_record grade --sport all
```

A `pipeline/com.user.nba-nightly.plist.example` is in the repo if you prefer launchd; copy
and point it at these commands. (Deliberately not installed — that's your call.)

## What's wired, and adding a sport

| Sport | Slate + finals source | Mode |
|---|---|---|
| `nhl` | `sports/nhl/data.load_schedules` (refetches the current season live, caches past ones) | **live** — `lock --date today` gets tonight's real slate |
| `soccer` | cached `data/soccer/epl_matches_*.parquet` (no free live fixtures feed) | replay only |

The only per-sport glue is `_games_on(sport, date)` in `pipeline/track_record.py`, which
returns each game as `home / away / home_pts / away_pts / final`. Add a sport by adding one
branch that reads its dated games (NFL/MLB/CFB all have a `load_schedules`/`load_games` that
exposes date + teams + score + status), then add its key to `WIRED_SPORTS`. Sports without a
branch are skipped gracefully.

## Where the data lands

- Locks: `backend/data/predictions/locked/{sport}/{date}.json` (immutable, hashed).
- Graded ledger: `backend/data/predictions/results_ledger.parquet` (live rows tagged
  `source="live"`; props, if any, in `prop_results_ledger.parquet`).

All of `backend/data/` is gitignored — the record is local runtime state, never committed.
The NHL model is trained through 2024, so grading 2025-26 (or later) NHL games is a genuine
out-of-sample record.
