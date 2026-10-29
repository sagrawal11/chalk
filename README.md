# CHALK.

CHALK is a market-blind sports-prediction project, built in public, one honest experiment at a time.

It predicts a winner and a final score for every game across six leagues (NFL, college football, NBA, NHL, MLB, and major soccer) entirely from its own models, without ever looking at the betting line. Every prediction gets locked before tip-off with a SHA-256 hash, graded against the real result, and reported out in the open, the hits and the misses both. The account is [@playthechalk](https://instagram.com/playthechalk), and it's faceless on purpose, because the algorithm is the character.

## The idea

The betting market is the most efficient public forecaster in sports, so CHALK stays blind to it on purpose, which turns the model into a clean experimental control. Because the model never sees the line, anything the market knows that the model doesn't will show up as a measurable, attributable gap, and that gap is the whole point.

The method is simple: start from a deliberately simple model, add one feature at a time, measure exactly what each one is worth on historical walk-forward data, and publish the result whether it helped, did nothing, or actively hurt. The features that close the gap show what the market was quietly pricing in, and the ones that don't are just as interesting, and just as public.

## How it works

- Market-blind by design. The models never receive the betting line as an input, and the market is used only to grade the model and measure the gap, never to make a prediction.
- One honest experiment at a time. A champion model climbs a pre-committed feature roadmap, each candidate feature runs as a challenger measured walk-forward and out-of-sample, and every result gets written to a public experiment ledger (`backend/experiments/`).
- Leakage-safe throughout. Prior-only rolling features, walk-forward training and backtests, and backward-exclusive as-of merges, so no feature ever sees the game it's predicting.
- Tamper-evident track record. Each daily slate is locked with a SHA-256 hash before tip-off, then auto-graded against the final scores (`backend/track_record/`).
- Sport-plugin architecture. Each sport implements one interface, and everything downstream (predictions, picks, track record, content) stays sport-agnostic (`backend/sports/`).

## What's in here

| Path | What |
|---|---|
| `backend/` | The engine: data adapters, leakage-safe features, LightGBM models, the walk-forward eval and experiment harness, the track record that locks, grades, and aggregates, and the Flask API. |
| `reel/` | A [Remotion](https://remotion.dev) project that renders the daily predictions reel to a 1080×1920 MP4. |
| `lovable/` | The React + Vite + TypeScript frontend (predictions plus the public track record and changelog). |
| `design/chalk/` | The "Editorial Terminal" design system, from the early explorations to the locked cards. |

The full plan lives in `docs/`: `CHALK_MASTER_PLAN.md`, `FEATURE_ROADMAP.md`, `ARCHITECTURE.md`, `CONTENT_SPEC.md`, `OPS_RUNBOOK.md`, and `BUILD_PLAN.md`.

## Run it locally

It's a hybrid setup: Docker runs the backing services (Redis and MinIO, a local S3-compatible stand-in for Cloudflare R2) plus the pinned Python 3.10 backend, and the Vite frontend runs natively.

```bash
cp .env.example .env     # placeholders are fine for local dev (no keys required)
make setup               # build the image, start redis + minio + backend, health-check
make test                # run the backend suite in the pinned Python 3.10 image
make frontend            # Vite on http://localhost:8080  (API on :5001)
```

## Disclaimer

It's a research project, not betting advice.

## Tech

Python · LightGBM · pandas · Flask · React / Vite / TypeScript · Remotion · Docker

---

MIT licensed, see [`LICENSE`](LICENSE).
