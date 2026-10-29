# CHALK.

CHALK is a sports-prediction project, built in public, one honest experiment at a time.

It predicts players and teams across six leagues (NFL, college football, NBA, NHL, MLB, and major soccer) from its own models: a winner and a final score for every game, plus player stat projections. Every prediction is locked before the game with a SHA-256 hash, graded against the real result, and reported out in the open, the hits and the misses both. The account is [@playthechalk](https://instagram.com/playthechalk), and it's faceless on purpose, because the algorithm is the character.

## The idea

Start from a deliberately simple model, add one feature at a time, measure exactly what each one is worth on historical walk-forward data, and publish the result whether it helped, did nothing, or actively hurt. An honest, attributable record of what actually moves a model is the whole point.

## How it works

- One honest experiment at a time. A champion model climbs a pre-committed feature roadmap, each candidate feature runs as a challenger measured walk-forward and out-of-sample, and every result gets written to a public experiment ledger (`backend/experiments/`).
- Leakage-safe throughout. Prior-only rolling features, walk-forward training and backtests, and backward-exclusive as-of merges, so no feature ever sees the game it's predicting.
- Tamper-evident track record. Each daily slate is locked with a SHA-256 hash before the game, then auto-graded against the final scores (`backend/track_record/`).
- Sport-plugin architecture. Each sport implements one interface, and everything downstream (predictions, models, track record) stays sport-agnostic (`backend/sports/`).

## What's in here

The repo is the backend modeling core: data adapters, leakage-safe features, LightGBM models (soccer uses a Poisson/Dixon-Coles team-strength model), the walk-forward eval and experiment harness, and the track record that locks, grades, and aggregates.

| Path | What |
|---|---|
| `backend/sports/` | Per-sport data adapters + team/player feature engines, behind one `Sport` interface. |
| `backend/models/`, `backend/model_training/` | The LightGBM and Poisson predictors and their trainers. |
| `backend/experiments/` | The champion/challenger harness and the public experiment ledger. |
| `backend/backtest/`, `backend/track_record/` | Walk-forward evaluation, and the lock/grade/aggregate track record. |

The outward-facing surfaces (the React frontend, the Remotion reel, and the design system) are deferred while the models get good; they live on the `archive/outward-facing` branch.

The plan lives in `docs/`: `FEATURE_ROADMAP.md` (the per-sport feature ladder), `ARCHITECTURE.md` (the engineering map), `DATA_SOURCES.md` (the free data feeds), and `OPS_RUNBOOK.md`. The original full-scope vision is kept under `docs/archive/`.

## Run it locally

Docker runs the pinned Python 3.10 backend plus the backing services (Redis and MinIO, a local S3-compatible stand-in for Cloudflare R2).

```bash
cp .env.example .env     # placeholders are fine for local dev (no keys required)
make setup               # build the image, start redis + minio + backend, health-check
make test                # run the backend suite in the pinned Python 3.10 image
```

## Disclaimer

It's a research project, not betting advice.

## Tech

Python · LightGBM · pandas · Docker

---

MIT licensed, see [`LICENSE`](LICENSE).
