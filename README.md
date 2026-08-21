# CHALK.

**A fully-algorithmic sports-prediction engine — and an honest, public test of whether a machine can actually beat the betting market. (Spoiler: it can't. Here are the receipts.)**

CHALK predicts a winner and a final score for **every game** across the NBA, NFL, MLB, NHL, and major soccer leagues — from its own models, **without ever looking at a betting line**. Every prediction is locked before tip-off, graded against the real result, and reported in public: wins *and* losses.

Most sports-prediction accounts sell you a system that "beats Vegas." CHALK does the opposite — it rigorously measures itself against the market and tells you the honest truth.

## The honest headline

A market-blind model, stress-tested every way we could think of:

- **It matches the market; it doesn't beat it.** In the NBA it calls **66.0%** of games correctly straight-up — essentially tied with the closing-line favorite's **68.3%** — and agrees with the market **~86%** of the time.
- **On the games where it disagrees with the market, it's right only 41.7%.** The market usually wins the disagreements.
- **It has negative closing-line value (CLV).** The line moves *away* from our picks ~59% of the time — the professional signature of having *no* edge.
- **Betting it loses money.** $100 on every soccer pick since Jan 2025, settled at real closing odds across 20 leagues: **−$21,937 on $613k staked (−3.6%)**.
- **Softer leagues don't rescue it.** The market beat us in all 10 soccer leagues tested, down to England's 4th tier — because of a catch-22: a league only *has* a line to beat if it's liquid enough to already be efficient.

That's the whole point. **CHALK is the honest one:** ~66% straight-up, well-calibrated, graded in the open, no fabricated edge.

## How it works

- **Market-blind by design.** Models never receive the betting line as an input. The market is used *only* to grade our honesty (accuracy + CLV).
- **Sport-plugin architecture** (`backend/sports/`): each sport implements one interface (`schedule`, `predict_game`, `predict_player`, `canonical_team`); everything downstream — predictions, pick selection, track record, content — is sport-agnostic.
- **Leakage-safe throughout:** prior-only rolling features (`shift(1)`), walk-forward training and backtests, backward-exclusive as-of merges.
- **Tamper-evident track record:** each daily slate is locked with a SHA-256 content hash *before* tip-off, then auto-graded against final scores (`backend/track_record/`).

## What's in here

| Path | What |
|---|---|
| `backend/` | The engine — data adapters, features, LightGBM models, Flask API, and the lock → grade → aggregate track record. |
| `design/chalk/` | The brand & design system ("Editorial Terminal"): concept explorations, the locked cards, and the design journey (see the READMEs). |
| `reel/` | A [Remotion](https://remotion.dev) project that renders the daily prediction reel to a 1080×1920 MP4. |
| `lovable/` | React + Vite + TypeScript frontend (game views, prediction history). |

## What I learned (the genuinely interesting part)

Beating an efficient betting market as a solo, market-blind modeler is — per both our own tests and the literature (Levitt 2004 on why gambling markets differ from financial ones; FiveThirtyEight's Elo models; Dixon–Coles; Constantinou's Bayesian networks) — essentially not achievable. The best public models *match* the market; they don't beat it. So the defensible product was never a fake edge. It's **radical transparency**: showing exactly how close a machine gets, measured with the professionals' own yardstick (closing-line value), and grading every single call in public.

## Run it locally

Hybrid setup: Docker runs the backing services (Redis + MinIO, a local S3-compatible stand-in for Cloudflare R2) and the Flask backend (Python 3.10). The Vite frontend runs natively.

```bash
cp .env.example .env     # placeholders are fine for local dev (no keys required)
make setup               # build image, start redis + minio + backend, health-check
make cache               # warm baseline predictions
make frontend            # Vite on http://localhost:8080  (API on :5001)
```

Backend tests: `cd backend && ../betting_venv/bin/python -m pytest tests/ -q`. See [`PLANNING.md`](PLANNING.md) and [`DATA_SOURCES.md`](DATA_SOURCES.md) for the data layout and the free data sources used.

## Disclaimer

CHALK is a personal machine-learning project and a transparency experiment. Its predictions are **for entertainment and educational purposes only — not betting advice.** As documented above, the model does **not** beat the market, and betting its picks loses money. 21+. If you or someone you know has a gambling problem, call 1-800-GAMBLER.

## Tech

Python · LightGBM · pandas · Flask · React / Vite / TypeScript · Remotion · Docker

---

MIT licensed — see [`LICENSE`](LICENSE). Built as an honest showcase of algorithmic modeling.
