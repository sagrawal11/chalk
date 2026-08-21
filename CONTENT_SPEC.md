# CHALK — Content Spec (the design + content system)

> **Status:** Draft v0.1 for owner review. Phase-A doc #3 (companion to `CHALK_MASTER_PLAN.md`, `FEATURE_ROADMAP.md`, `ARCHITECTURE.md`). Captures the **locked visual identity**, the **copy laws**, the **per-type templates**, the **reel spec**, and the **🟡 guardrail-check spec** that the content generators + the autonomy agent execute against.
>
> **Design source of truth (rendered + HTML):** `~/.gstack/projects/sagrawal11-chalk/designs/chalk-content-20260820/` — the locked cards are `locked-score.html`, `locked-feature.html`, `locked-results.html`, `locked-carousel-cover.html`, `locked-carousel-slide2.html`, the pinned `triptych-panorama.html`, and `locked-reel-1..5.html`, each with a matching retina PNG. Port these into `backend/content/templates/` as the production templates.

---

## 1. Voice & the copy laws (binding)

**The persona = the algorithm.** The account is faceless; the *model* is the character — rigorous, self-aware, dry, quietly confident, allergic to hype. It is proud of the method and honest about the result. It is the one non-tout in a feed of touts.

**The copy laws** (these are enforced by the guardrail checks in §5 — treat as binding):

1. **Say "a research project."** Never "for entertainment." The footer disclaimer is "A research project. Not betting advice." (game/pick cards) or "A research project." (non-pick cards).
2. **No redundant methodology taglines.** Do **not** stamp cards with "market-blind," "build in public," "every test logged," or "measured on historical walk-forward." The method is shown by *what we do*, not by slogans. (Exception: the manifesto and the pipeline graphic may *explain* the method in plain words — e.g. a node captioned "no odds in" — because there the method is the content, not a repeated stamp.)
3. **NEXT always explains the stat.** In the experiment-log post, the NEXT beat names the next feature *and* gives a one-line plain-English explanation of what it is (e.g. "Expected Points Added per play — roughly, how many points each play is worth on average. A cleaner read on a team's efficiency than raw yards.").
4. **No self-deprecating market lines.** Do not write "it matches the market's accuracy," "it doesn't beat it," or any comparison that frames the model as losing. State the numbers straight — no spin, and no *implied edge* either. The honest thesis ("how close a machine gets") lives in the manifesto, framed forward, not as an apology.
5. **Never tout language.** Denylist (hard fail): "lock," "guaranteed," "guarantee," "sure thing," "easy money," "hammer," "🔒," "💰," "free money," "can't lose," "bankroll," "print." Bold is fine; touting is not.
6. **Attribute predictions to "the model."** The standard attribution line is *"The model's call — graded tomorrow, win or lose."* Predictions are the model's output, presented neutrally.
7. **Honesty is structural, not a per-post disclaimer.** We never nag "we'll probably lose to the market" on individual picks. The honesty is that every call is graded in public — that's carried by the results card and the track record, not by hedging on each prediction.
8. **Charts are honest.** Y-axis chosen so a small delta looks small. Never truncate an axis to inflate a gain.
9. **Never post around tragedy or serious injury.** Hard rule (also a Red-tier escalation in ops).

**Retired phrasings** (were in early drafts, now removed): "for entertainment," "market-blind" as a stamp, "build in public / every test logged," "measured on historical walk-forward," "it matches but doesn't beat the market."

---

## 2. The design system (locked — "Editorial Terminal")

### Palette
| Token | Hex | Use |
|---|---|---|
| Paper | `#F4F1EA` | card background |
| Page | `#DEDACF` | behind the card (grid gutter) |
| Ink | `#141210` | primary text, icon outlines |
| Red (accent) | `#D6482B` | the signature — period, winner, key numbers, accents |
| Muted / grey | greys derived in-file | secondary text, the projected loser, hairlines |

A **6px red top edge** runs across the top of every card (full width on the triptych panorama). Subtle paper vignette.

### Type system (strict roles — this is the legibility rule)
- **Fraunces** (serif) — **display only**: the `CHALK.` wordmark and the one big post title. Never body, never numbers.
- **Archivo** (800, tabular lining `font-feature-settings:"tnum" 1`) — **all numbers**: scores, confidence %, stat deltas, record.
- **Inter** — all body / sentence / matchup / attribution text.
- **IBM Plex Mono** — tiny UPPERCASE kicker + section labels only.

### Wordmark
`CHALK.` in Fraunces with a **red trailing period** — the signature element, reused as an accent (winner name period, title period).

### Iconography (in-house, per sport)
Line-art, ink outline (`#141210`, ~5px) + a single red (`#D6482B`) accent. **Drawn in-house — no trademarked league/team marks.** Placed top-right of the masthead on sport-specific cards; **omitted on general/model cards** (the pinned triptych has no icon). The locked set:

- **Football:** `<svg viewBox="0 0 120 90">` pointed oval (ink) + red cross-laces.
- **Basketball:** `<svg viewBox="0 0 90 90">` ink circle + equator + red vertical seam + two curved side seams.
- **Baseball:** ink circle + two curved red stitch seams.
- **To draw (same style) as sports launch:** NHL (puck), soccer (ball), CFB (reuse the football).

### Charts
Honest y-axis (small deltas look small); ink bars with the "after"/positive bar in red; a dashed 50% coin-flip reference on accuracy/record charts.

### Canvas & layout primitives
- **Feed post:** 1080×1350. **Reel keyframe:** 1080×1920. **Pinned triptych:** one 3240×1350 panorama sliced into 3× 1080×1350.
- **Masthead:** `CHALK.` wordmark left + sport icon right (omit on general cards) + hairline rule beneath.
- **Footer:** `@playthechalk` + the research-project disclaimer, small, mono/inter.
- Generous margins (~84–92px), hairline rules, lots of cream space.

---

## 3. Content types (templates)

### 3.1 Score-prediction card
- **Purpose:** the model's daily call for one game. **Canvas:** 1080×1350. **Cadence:** game days. **Platform:** carousel interior on IG; standalone on X/Reddit.
- **Slots:** masthead (wordmark + sport icon) · kicker `LEAGUE · WEEK/DATE · TIME` · matchup `[Away] at [Home]` (Inter) · **hero predicted score** (Archivo, winner in red, loser dimmed grey) · `PREDICTED WINNER / [Team].` · `MODEL CONFIDENCE / NN%` with the honest bar + 50% coin-flip tick · attribution "The model's call — graded tomorrow, win or lose." · footer "@playthechalk · A research project. Not betting advice."
- **Rules:** 3-digit scores (NBA/CFB) scale numerals down to fit; no tout; neutral.

### 3.2 Experiment-log post (the signature type)
- **Purpose:** the daily "tested X → what it did → what's next" engine. **Canvas:** 1080×1350. **Cadence:** per-sport per §7. **Platform:** per-sport depth on X/Reddit; the day's best one (or a combined carousel) on IG.
- **Layout (locked = A style + C layout):** big Fraunces title top; then **TESTED / RESULT / NEXT** as left-column Plex-Mono labels with content to the right.
- **Slots:** `EXPERIMENT LOG · [ID]` · title `[Feature name].` · **TESTED** = the hypothesis as a question ("…help predict the result?") · **RESULT** = honest before/after chart + `X% → Y%` (Archivo) + `+Δ pp` + `over N seasons` + verdict pill (`marginal — kept` / `no lift — dropped` / `kept`) · **NEXT** = `[ID] · [stat name]` + **one-line explanation of the stat** · footer "@playthechalk · A research project."
- **Rules:** duds are posted honestly (verdict = dropped/no-lift is valid content); NEXT must explain; honest chart.

### 3.3 Results / graded card
- **Purpose:** yesterday's calls, graded, wins *and* misses. **Canvas:** 1080×1350. **Cadence:** daily (also a quick story version). **Platform:** IG story + feed; X/Reddit.
- **Slots:** `RESULTS · [DAY]` · title "How the calls landed." · a scannable list of games, each = HIT (red check) / MISS (muted ✗) + called team + `called X · final Y` (Archivo) · record block `TODAY N–N` / `SEASON N–N` · honest line "We grade every call — the misses too." · footer.
- **Rules:** show the misses (name who actually won); no spin.

### 3.4 Multi-sport carousel (the combined IG post)
- **Purpose:** the day's slate as one swipeable IG post (keeps IG volume sane vs. per-sport posts). **Canvas:** 1080×1350 per slide.
- **Cover (slide 1):** `TODAY · [DATE] · THE SLATE` · title "Today's calls." · compact rows `[sport icon] [Away] @ [Home] → [Winner] [Score] · NN%` (Archivo numbers) · "SWIPE FOR EACH →" · footer.
- **Interior slides (2…N):** one score-prediction card (§3.1) per game, with that sport's icon.
- **Platform rule:** IG gets this curated carousel; **X/Reddit get the full per-sport depth** (individual posts).

### 3.5 Pinned triptych (three posts, one continuous graphic)
- **Purpose:** the profile top row — why + how + status in one panorama. **Canvas:** one **3240×1350** composition sliced into three **1080×1350** tiles. **No sport icon** (general model piece).
- **Composition:** `CHALK.` wordmark + thesis headline ("A market-blind model, learning in the open.") top-left; the **pipeline** (DATA → FEATURES → MODEL "no odds in" → PREDICTION → LOCKED → GRADED → PUBLISHED) as a horizontal spine spanning all three tiles with the two honesty guarantees (G1 "no market data ever enters"; G2 "locked before the game / graded after the result"); the big **model-performance number** (61.5% straight-up · games graded) as the hero, wholly inside tile 3; per-sport metrics + an honest accuracy sparkline placed throughout; footer spans the bottom.
- **Rules:** nothing critical straddles the seams at x=1080 / x=2160; **posting order = right tile first** (IG fills newest-first) so the row reads left→right; no self-deprecating market line.
- **Related:** a fuller standalone **manifesto** post (non-pinned) exists as `locked-pin-manifesto` if wanted.

### 3.6 Reel (daily predictions)
- **Purpose:** the widest-reach daily piece — one combined reel across the slate. **Canvas:** 1080×1920 (9:16). **Engine:** Remotion (`reel/`), wired into the pipeline (see `ARCHITECTURE.md` §8 — currently unwired).
- **Beats (locked storyboard):** (1) **Intro** — big `CHALK.` wordmark, "Today's calls," date; (2) **Matchup** — teams slide in; (3) **The call** — Archivo score counts up, winner underlines in red, confidence; (4) **Next game** — quick cut, same layout (other sports use their icon); (5) **Outro** — season record ticks up, "We grade every call — win or lose.", `@playthechalk`, "a research project."
- **Rules:** editorial skin adapted to 9:16 (lots of cream, big type, red accent); keep the slate tight as it grows (highlight, don't enumerate 40 games); reuse the Remotion theme tokens from §2.

---

## 4. Platform & cadence mapping
Per `CHALK_MASTER_PLAN.md` §7–§8:
- **Feature posts** = the daily engine (per-sport). **Predictions** = one combined **reel** + the carousel. **Results** = story + the track record.
- **Cadence:** NFL/CFB ~twice weekly · NBA/NHL daily · MLB/soccer few per week (feature-experiment cadence). Predictions/results are game-day-driven.
- **Volume/platform split:** per-sport depth (individual feature + score posts) → **X / Reddit**; **Instagram** gets the curated multi-sport **carousel** + the **reel** + results, to avoid feed fatigue/throttle.
- **Pinned:** the triptych (post right→middle→left).

---

## 5. The 🟡 Yellow guardrail-check spec (automated, pre-publish)
Every LLM-drafted caption/post is gated by these before it can auto-post or enter the batch queue (see `ARCHITECTURE.md` §5h/§9.1):

1. **Tout denylist** (§1.5) — hard fail on any match.
2. **Retired-phrasing check** — flag "for entertainment," "market-blind"/"build in public"/"every test logged"/"measured on historical walk-forward" as stamps, and any self-deprecating market comparison.
3. **Numbers reconcile with source data** — every stat/score/percentage in the copy must match the underlying prediction/result/experiment record (no hallucinated numbers).
4. **Disclaimer present** — the correct footer ("A research project. …") is on the card.
5. **NEXT-explains-the-stat check** (experiment posts only) — the NEXT beat contains an explanation, not just a stat name.
6. **On-voice check** — LLM check against this §1 voice.
7. **Tragedy/serious-injury screen** — keyword + LLM; any hit → route to 🔴 (hold + escalate), never auto-post.
8. **Idempotency** — one post per item; store the returned post URL.

---

## 6. Implementation notes
- **Renderer:** HTML/CSS → PNG (the `content/html_render.py` path + a rasterizer). The locked `*.html` in the design dir are the reference templates → port to `backend/content/templates/` with data slots.
- **Fonts:** Fraunces · Archivo · Inter · IBM Plex Mono (Google Fonts; vendor them for offline/CI rendering).
- **Icons:** ship the in-house SVG set (§2) in the templates; add per sport as they launch.
- **Reel:** Remotion theme = these tokens; wire `daily_content` to write the slate JSON + invoke `render-reel.mjs`.

## 7. Open items / TBD
- Approval UX: **Telegram/Slack bot** (recommended) vs. dashboard — carry from `ARCHITECTURE.md` §5h/§9.
- Full per-sport **icon set** (NHL puck, soccer ball, CFB) in the locked line-art style.
- Story formats + the **weekly "report card" reel**.
- Optional nudge: move the triptych footer tagline so "RESEARCH" doesn't split across the tile-2/3 seam when a tile is viewed alone.
- Voice guide will grow during the cautious calibration weeks (ops runbook).

---

Next Phase-A docs: **`OPS_RUNBOOK.md`** (Green/Yellow/Red workflows, escalation, calibration, recovery, the tighten switch) → **`BUILD_PLAN.md`** (ordered milestones with acceptance criteria).
