# CHALK: LOCKED design system

Motif locked from explore variant 01 (`rows · Fraunces · bone+red · serif numerals`):
warm bone paper `#F4F1EA`, ink `#16130F`, one signal-red accent `#C1272D`, Fraunces
serif throughout (names AND score numerals), IBM Plex Mono for labels/handle, the
red period in `CHALK.`, dot markers (red = winner), no team-color chips. Honest tag:
`100% algorithmic · no odds used`.

## The system (all 1080×1350 unless noted)
- `card.png`: daily game card (sample data)
- `real-card.png`: rendered from the live market-blind model (it calls Boston over the Lakers here) via `backend/content/html_render.py` + `templates/card_editorial.html`. Shows the design generates from real predictions.
- `reel-1-intro.png` / `reel-2-game.png` / `reel-3-outro.png`: 1080×1920 reel frames (intro → per-game → track-record outro)
- `grid.png`: the 9-post profile mural

Supersedes the earlier `../editorial/` mockups (which had team-color chips + mono numerals). This folder is canonical.

## Notes / easy tweaks
- The card verdict currently prints the full winner name ("…the Los Angeles Lakers…"); reels use the short name ("…the Lakers"). Can unify either way.
- The track-record box is kept from the real card you liked; trivial to drop for a barer variant-01 look.
- Logo: the `CHALK.` wordmark is Fraunces bold + red period, that's the logo direction.
