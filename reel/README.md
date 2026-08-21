# CHALK — Daily Prediction Reel (Remotion)

Programmatic React video that renders CHALK's daily sports-prediction REEL as a
**1080×1920, 30fps MP4** in the locked **"Editorial Terminal"** design, fully
automatable from a single JSON slate.

Self-contained under `reel/`. Does not touch the Python backend or `lovable/`.

---

## What it renders

A single composition, `Reel`, sequenced as **Intro → Game×N → Outro**:

1. **Intro** (~75f, light) — wordmark + date, "TODAY'S CALLS" kicker, a big
   three-line headline (`N games. / N predictions. / 0 odds.`), a subhead, and a
   track-record block.
2. **Game** (~75f each, light) — pager dots, `{HOME CITY} · {AWAY CITY}` lead, a
   two-row game block with **scores that count up from 0**, a verdict, a
   **confidence bar that fills**, an italic reason, and a **wipe** between games.
3. **Outro** (~105f, **dark**) — "YESTERDAY" kicker, `We went {correct} for
   {total}.` with the number counting up, a season line, and a `@playthechalk`
   CTA.

Total duration scales to the slate via `calculateMetadata` — a 3-game slate and a
12-game slate both render correctly with no config change.

---

## Install

```bash
cd reel
npm install
```

> **Fonts need network on the first render.** Fraunces / IBM Plex Mono / Inter
> are pulled via `@remotion/google-fonts` at build/render time and cached
> thereafter. An offline first render will fail at font fetch.

---

## Preview (Remotion Studio)

```bash
cd reel
npx remotion studio
```

Opens the interactive studio at http://localhost:3000. The `Reel` composition
loads with `sample-slate.json` as its default props; edit props live in the
right-hand panel.

---

## Render an MP4

Using the bundled sample slate:

```bash
cd reel
npx remotion render Reel out/reel.mp4 --props=./sample-slate.json
```

Using any slate JSON (validates the data contract first, auto-names the output):

```bash
cd reel
node render-reel.mjs path/to/slate.json            # -> out/reel-<date>.mp4
node render-reel.mjs path/to/slate.json out/x.mp4  # explicit output
```

### Stills (quick visual check without encoding a full MP4)

```bash
cd reel
npx remotion still Reel out/intro.png  --props=./sample-slate.json --frame=40
npx remotion still Reel out/game.png   --props=./sample-slate.json --frame=140
npx remotion still Reel out/outro.png  --props=./sample-slate.json --frame=620
```

---

## Data contract (the JSON slate)

`getInputProps` / `defaultProps` shape — see `sample-slate.json` for a full
8-game NBA example:

```jsonc
{
  "date": "SAT · FEB 8, 2026",
  "trackRecord": { "winPct": 61.5, "nPicks": 43583 },
  "yesterday":   { "correct": 6, "total": 8 },
  "slate": [
    {
      "homeName": "Lakers", "homeShort": "Lakers", "homeCity": "Los Angeles",
      "awayName": "Warriors", "awayShort": "Warriors", "awayCity": "Golden State",
      "homeScore": 112, "awayScore": 108,
      "winnerSide": "home",          // "home" | "away"
      "confidence": 64,              // 0–100
      "reasoning": "L.A. grades out ahead at home…"
    }
    // …one object per game
  ]
}
```

Notes:
- `winPct` is a **percentage** (e.g. `61.5`), not a fraction.
- `date` is a pre-formatted display string; the reel prints it verbatim (mono,
  uppercase). Keep it short (e.g. `SAT · FEB 8, 2026`).
- `homeShort` / `awayShort` feed the verdict ("Our model calls the **{winnerShort}**.").

---

## How the Python pipeline feeds this

The backend already computes everything needed. Wiring (backend stays untouched;
this is the glue the daily job runs):

1. **Winner picks (market-blind)** — the day's odds-free winner + predicted final
   score per game come from `backend/pipeline/daily_content.py` (the
   `game_preds` / market-blind winner picks). Map each game to a slate entry:
   `homeName/awayName`, `homeCity/awayCity`, predicted `homeScore/awayScore`,
   `winnerSide`, model `confidence` (0–100), and a one-line `reasoning`.

2. **Track record** — call `track_record.aggregate.headline(ledger)`
   (`backend/track_record/aggregate.py`). It returns `win_pct` (a **fraction**,
   e.g. `0.615`) and `n_picks`. Convert to the slate:
   `trackRecord.winPct = round(win_pct * 100, 1)`, `trackRecord.nPicks = n_picks`.

3. **Yesterday** — grade the prior day's locked slate
   (`grade_previous_day`) and count correct winner calls vs. total games →
   `yesterday = { correct, total }`.

4. **Write the slate + render:**

   ```python
   import json, subprocess
   from track_record.aggregate import headline

   rec = headline(ledger)                       # {"win_pct": 0.615, "n_picks": 43583, ...}
   slate = {
       "date": "SAT · FEB 8, 2026",
       "trackRecord": {"winPct": round((rec["win_pct"] or 0) * 100, 1),
                       "nPicks": rec["n_picks"]},
       "yesterday": {"correct": correct, "total": total},
       "slate": games,                          # list of game dicts (contract above)
   }
   with open("reel/slate.json", "w") as fh:
       json.dump(slate, fh)

   subprocess.run(["node", "render-reel.mjs", "slate.json"], cwd="reel", check=True)
   # -> reel/out/reel-<date>.mp4, ready to post
   ```

Output MP4 lands in `reel/out/` for manual posting to IG/TikTok/Shorts.

---

## Project layout

```
reel/
├── package.json          remotion + @remotion/cli + @remotion/google-fonts + react/react-dom
├── remotion.config.ts    codec/format/entry-point config (H.264 MP4, yuv420p)
├── tsconfig.json
├── render-reel.mjs       thin wrapper: validate slate JSON → run the render
├── sample-slate.json     realistic 8-game NBA sample (Lakers 112–108, etc.)
├── README.md
└── src/
    ├── index.ts          registerRoot entry point
    ├── Root.tsx          <Composition id="Reel"> + calculateMetadata (duration scales to slate)
    ├── Reel.tsx          <Series> Intro → Game×N → Outro + the wipe transition
    ├── theme.ts          LOCKED tokens: colour, fonts, spacing, motion, data contract
    ├── components.tsx     shared brand primitives (Wordmark w/ red period, Mono, Hairline, Footer)
    └── frames/
        ├── Intro.tsx
        ├── Game.tsx
        └── Outro.tsx
```

---

## Design tokens (locked)

See `src/theme.ts`. Summary:

- **Light** — bg `#F4F1EA`, ink `#16130F`, muted `#6B6459`, accent `#C1272D`,
  hairline `rgba(22,19,15,.09)`.
- **Dark (outro)** — bg `#15130E`, text `#F1ECE0`, muted `#9A9184`, accent
  `#E7473C`, hairline `rgba(255,255,255,.12)`.
- **Type** — Fraunces (serif; team names, scores, headlines, verdicts), IBM Plex
  Mono (labels/kickers/date/handle, UPPERCASE + tracked + muted), Inter (utility).
- **Wordmark** — `CHALK` in Fraunces 700 (~54px, letter-spacing -1px) with a
  **red period** in the accent colour (locked brand element).
- **Frame padding** — ~110px top/bottom, 80px sides.
