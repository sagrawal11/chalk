# CHALK daily reel — structure

One vertical reel (1080×1920) posted every morning before games start. It's a
sequence of static frames (rendered as PNGs) stitched into an MP4. Same "Editorial
Terminal" system as the feed card.

## Frame sequence

1. **Intro** (`editorial/reel-1-intro.png`) — ~2.5s
   "8 games. 8 predictions. 0 odds." + today's date + the season track-record line.
   Sets up the slate and leads with independence from the books.

2. **Per-game** (`editorial/reel-2-game.png`) — ~2.5s each, one per game on the slate
   Pager ("Game k / N" + dots), matchup with team chips, predicted winner + final
   score, confidence bar, one-line plain-English reason. This frame repeats N times;
   only the data changes.

3. **Outro / receipts** (`editorial/reel-3-outro.png`) — ~3s
   Dark frame. Yesterday's result ("We went 6 for 8"), season accuracy, and the
   follow CTA (@playthechalk + playthechalk.com). Turns proof into a subscribe hook.

Total for an 8-game slate ≈ 2.5 + 8×2.5 + 3 ≈ 26s. Cap the per-game dwell (or split
into two reels) when a slate is very large.

## Production notes (later phase)

- **Assembly:** render each frame to PNG via `backend/content/html_render.py`
  (same template family as the card), then stitch with `ffmpeg` at 30fps with hard
  cuts or a fast 150ms wipe. No motion graphics needed for v1.
- **Audio:** optional licensed/royalty-free bed; text-only reads fine muted (most IG
  viewing is muted), so captions carry the message.
- **Data:** intro + per-game come from the day's `select_best_bets` winner picks;
  the outro's "yesterday" line comes from grading yesterday's locked slate; season
  numbers from `track_record.aggregate.headline`.
- **Cadence:** one reel every morning before first tip. Fully automated in the
  autonomy phase (render → host → publish), with a one-tap approve interim.

## 9-post grid (`editorial/grid.png`)

The pinned profile mural: one billboard sliced into 9 feed tiles (3×3, 1080×1350
each). Shows the headline accuracy, per-sport breakdown, and the "no odds used"
promise. Posting mechanic: upload all 9 at once (newest-first fill) so the mural
lands intact, and refresh weekly as the live track record moves. Do not post singles
between grid refreshes or the mural shifts.
