# CHALK.

**A market-blind sports-prediction research project, built in public — one honest experiment at a time.**

CHALK predicts a winner and a final score for every game across six leagues — NFL, college
football, NBA, NHL, MLB, and major soccer — from its own models, **without ever looking at the
betting line**. Every prediction is locked before tip-off (SHA-256), graded against the real
result, and reported in the open: the hits and the misses. The account is
[@playthechalk](https://instagram.com/playthechalk) — faceless on purpose, because the
*algorithm* is the character.

## The idea

The betting market is the most efficient public forecaster in sports. CHALK is blind to it **on
purpose** — which turns the model into a clean experimental **control**. Because the model never
sees the line, anything the market knows that the model doesn't shows up as a measurable,
attributable gap.

> The market is the most efficient forecaster in sports. CHALK refuses to look at it — so the
> distance between them is a map of everything the crowd knows. We're charting that map, one
> feature at a time, in the open.

Start from a deliberately simple model, add **one feature at a time**, measure exactly what each
one is worth on historical walk-forward data, and publish the result — whether it helped, did
nothing, or hurt. The features that close the gap show what the market was pricing; the ones that
don't are just as interesting, and just as public.

## How it works

- **Market-blind by design.** Models never receive the betting line as an input. The market is
  used *only* to grade the model and measure the gap — never to make a prediction.
- **One honest experiment at a time.** A champion model climbs a pre-committed feature roadmap;
  each candidate runs as a challenger, measured **walk-forward, out-of-sample**, and every result
  is written to a public experiment ledger. (`backend/experiments/`)
- **Leakage-safe throughout.** Prior-only rolling features, walk-forward training and backtests,
  backward-exclusive as-of merges. No feature ever sees the game it predicts.
- **Tamper-evident track record.** Each daily slate is locked with a SHA-256 hash *before*
  tip-off, then auto-graded against final scores. (`backend/track_record/`)
- **Sport-plugin architecture.** Each sport implements one interface; everything downstream —
  predictions, picks, track record, content — is sport-agnostic. (`backend/sports/`)

## What's in here

| Path | What |
|---|---|
| `backend/` | The engine — data adapters, leakage-safe features, LightGBM models, the walk-forward eval + experiment harness, the lock → grade → aggregate track record, and the Flask API. |
| `reel/` | A [Remotion](https://remotion.dev) project rendering the daily predictions reel to a 1080×1920 MP4. |
| `lovable/` | React + Vite + TypeScript frontend (predictions + the public track record / changelog). |
| `design/chalk/` | The "Editorial Terminal" design system — explorations and the locked cards. |

The full plan lives in the repo: `CHALK_MASTER_PLAN.md`, `FEATURE_ROADMAP.md`, `ARCHITECTURE.md`,
`CONTENT_SPEC.md`, `OPS_RUNBOOK.md`, `BUILD_PLAN.md`.

## Run it locally

Hybrid setup: Docker runs the backing services (Redis + MinIO, a local S3-compatible stand-in for
Cloudflare R2) and the pinned Python 3.10 backend; the Vite frontend runs natively.

```bash
cp .env.example .env     # placeholders are fine for local dev (no keys required)
make setup               # build the image, start redis + minio + backend, health-check
make test                # run the backend suite in the pinned Python 3.10 image
make frontend            # Vite on http://localhost:8080  (API on :5001)
```

## Disclaimer

A research project. Not betting advice.

## Tech

Python · LightGBM · pandas · Flask · React / Vite / TypeScript · Remotion · Docker

---

MIT licensed — see [`LICENSE`](LICENSE).
