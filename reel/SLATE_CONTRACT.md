# Reel slate — data contract

`reel/render-reel.mjs` is the single source of truth for this contract (it validates
every field and fails fast). The daily pipeline writes a slate JSON in this shape,
then invokes the renderer:

```
node render-reel.mjs <slate.json> [out.mp4]     # render to a 1080×1920 MP4
node render-reel.mjs --check <slate.json>        # validate only (CI gate / seam smoke-test)
```

`backend/content/reel_slate.py` is the Python seam that writes this file. The real
per-day assembly from market-blind predictions + the graded track record is wired
into `pipeline/daily_content` in **M3** (ARCHITECTURE.md §5g, BUILD_PLAN M3). M0 lands
the seam (contract + writer + invoker) and pins it in CI.

## Shape

```jsonc
{
  "date": "SAT · FEB 8, 2026",          // non-empty string (display date)
  "trackRecord": {
    "winPct": 61.5,                      // number — straight-up win %
    "nPicks": 43583                      // number — graded picks to date
  },
  "yesterday": {
    "correct": 6,                        // number — yesterday's hits
    "total": 8                           // number — yesterday's graded games
  },
  "slate": [                             // non-empty array of games
    {
      "homeName":  "Lakers",             // strings, all non-empty:
      "homeShort": "Lakers",
      "homeCity":  "Los Angeles",
      "awayName":  "Warriors",
      "awayShort": "Warriors",
      "awayCity":  "Golden State",
      "homeScore": 112,                  // number (predicted)
      "awayScore": 108,                  // number (predicted)
      "confidence": 64,                  // number — model confidence %
      "winnerSide": "home",              // "home" | "away"
      "reasoning": "…"                   // non-empty string
    }
  ]
}
```

See `sample-slate.json` for a complete, valid example (rendered by CI).

## Copy discipline

`reasoning` is model-attributed, neutral copy — no tout language, no market
comparison (CONTENT_SPEC §1). The renderer applies the locked Editorial-Terminal
theme (`reel/src/theme.ts`).
