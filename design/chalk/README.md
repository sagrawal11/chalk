# CHALK — content design system

Locked visual direction for the CHALK (@playthechalk) prediction brand: **"Editorial
Terminal"** — warm bone paper, ink black, one signal-red accent, a serif wordmark
(Fraunces) with precise mono numerals (IBM Plex Mono). Premium, credible, "the data
people." Every artifact is honest by construction: `100% algorithmic · no odds used`.

Open any `.png` to view; the matching `.html` is the exact source (fonts load from
Google Fonts, so view online).

## Grade these

### 1. Concept directions (the spectrum you chose from)
- `concepts/01-broadcast.png` — sports-network authority (not chosen)
- `concepts/02-editorial-terminal.png` — **chosen direction**
- `concepts/03-court-print.png` — bold street/hype (not chosen)

### 2. Locked "Editorial Terminal" system
- `editorial/card.png` — the daily game card (1080×1350), with the track-record credibility line
- `editorial/reel-1-intro.png` — reel opening frame (1080×1920)
- `editorial/reel-2-game.png` — reel per-game frame (repeats once per game)
- `editorial/reel-3-outro.png` — reel "receipts" outro (yesterday + season + follow)
- `editorial/grid.png` — the 9-post profile mural (3×3)
- `REEL-STRUCTURE.md` — how the daily reel assembles

### 3. Production proof (renderer wired to real data)
- `real-card.png` — a card **rendered from live market-blind model output** (LAL vs BOS →
  the model calls Boston 120–116, 61% confidence) with the track line pulled from the
  real results ledger. Proves the design generates from actual predictions, not mockup text.

## Production renderer
- Template: `backend/content/templates/card_editorial.html` (tokens filled by string replace)
- Renderer: `backend/content/html_render.py`
  - `render_card_html(game)` / `render_card_png(game, out)` — fill + rasterize
  - `game_from_prediction(gp, ...)` — adapt a `GamePrediction` into the card
  - Rasterizer is pluggable: `$CHALK_RASTERIZER` command, else Playwright, else writes HTML only
- Mockups were rendered with the gstack browse headless browser at 1080×1350 / 1080×1920.

## Status & next
- **Done:** direction locked (Editorial Terminal); card + reel frames + grid designed; card wired to the renderer and proven on real data.
- **Next (needs your grade first):** apply the design to reel-frame + grid templates too; build the reel MP4 assembler (ffmpeg); the 9-tile grid slicer; then hosting + IG publishing (autonomy phase). None committed to git yet — pending your review.
