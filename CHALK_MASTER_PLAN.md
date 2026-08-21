# CHALK — Master Plan / North Star

> **Status:** Draft v0.1 for owner review. This is the reference document the whole
> (semi-)autonomous system executes against. Everything in **The Constitution** and
> **Tiered Autonomy** is meant to be binding once approved. Read thoroughly; we iterate.
>
> **Account:** `@playthechalk` (Instagram-first; also Reddit + X). Faceless brand — the
> *algorithm itself* is the character. The owner's face/identity is not attached.

---

## 1. What this is (in one paragraph)

CHALK is a fully-algorithmic sports-prediction system built **in public, one honest
experiment at a time.** It starts from a deliberately simple model and improves by adding
one feature at a time — publishing, every step, exactly what that feature did: whether it
helped, did nothing, or hurt, and what we try next. It predicts a winner and score for
games across six leagues — NFL, college football, NBA, NHL, MLB, and major soccer —
**without ever looking at the betting line.** And the whole roadmap is **dictated by the
data we actually have** (the most expansive *free* dataset per sport) — never by
aspiration. It never
claims to beat the market — because it can't, and neither can anyone else solo. Instead it
turns that fact into the entire point: the gap between a market-blind model and the market
is a *measurement of what the market knows that we don't*, and this project decomposes that
gap in the open, honestly graded, forever.

---

## 2. The thesis (the spine of everything)

The betting market is the most efficient public forecaster in sports. CHALK is **blind to
it, on purpose.** That blindness is not a handicap — it's a **clean experimental control.**
Because the model never sees the line, anything the market knows that the model doesn't
shows up as a *measurable, attributable gap*.

> **The market is the most efficient forecaster in sports. CHALK refuses to look at it — so
> the distance between them is a map of everything the crowd knows. We're charting that map,
> one feature at a time, in the open.**

- The **blind model** = the control / null hypothesis.
- The **market (closing line)** = the benchmark we measure against (never an input).
- The **gap** = the object of study: "what does the market know that we don't?"
- Each **feature experiment** = a treatment. We measure how much of the gap it closes. That
  quantity *is* the answer to "how much of what the market knows is factor X."

This reframes "I can't beat the market" from a confession into an instrument. We built the
control group for the betting market, and we're reverse-engineering its knowledge in public.

---

## 3. The Constitution (binding decision-principles)

These govern every automated and semi-automated action. When the system is unsure, these win.
When they conflict, **honesty and "do no harm" outrank engagement, always.**

1. **Honesty about results is non-negotiable — and always paired with the next move.**
   When a feature does nothing or hurts, we post it honestly *and* state the next plan of
   action to fix/improve. Duds are content, not shame. We never quietly skip a dud to
   manufacture a winning streak.
2. **Never tout language.** No "lock," "guaranteed," "easy money," 🔒, 💰, "hammer this,"
   or any confidence-for-hype framing — including in auto-drafted copy. Non-negotiable.
3. **Honesty is structural, not a per-post disclaimer.** We do **not** caveat every
   prediction with "we'll probably lose to the market" — that's a given, established once in
   the manifesto and proven continuously by the public track record. The honesty lives in
   *grading every call in the open*, not in repetitive hedging.
4. **When in doubt, hold for the human.** If content isn't clearly post-worthy, on-voice, or
   factually clean, it waits in the review queue. Never auto-post uncertain content.
5. **Never post about real-world tragedies or serious injuries.** Absolute hard rule. No
   flippancy, no engagement-farming around human harm. If a slate is dominated by such an
   event, the safe default is to hold and escalate.
6. **Corrections are public and prompt.** If we post something wrong, we fix it in the open —
   edit the reel and/or add a pinned correction comment. We never quiet-delete-and-pretend.
   Visible mistakes are on-brand; hidden ones are the opposite of the brand.

---

## 4. The narrative arc (built to stay honest AND stay interesting)

The model does **not** improve monotonically forever — real feature engineering hits
diminishing returns. We turn that physics into structure, a two-act story *per sport*:

- **Act 1 — "Watch it climb."** The early features genuinely stack up. Accuracy on
  historical walk-forward rises. Real, honest, satisfying.
- **Act 2 — "Watch it hit the wall."** Improvements flatten. The plateau is the *payoff*,
  not a failure to hide: "We've added everything obvious and we're still X% behind the
  market. That residual gap is the whole point — let's decompose what lives inside it."

Because each sport has its own ladder depth and cadence (see §6–7), **different sports sit in
different acts at the same time** — one is climbing while another is decomposing the wall.
That staggering keeps the account fresh and gives us a permanent supply of stories.

---

## 5. The build model: progressive, one honest experiment at a time

**The daily unit of content = one experiment:** `tested X → here's what it did → here's
what's next.`

- **Start simple.** Day 1 of each sport = the most basic model (team strength / win% + a
  couple of basic box stats). People watch it grow from nothing.
- **Climb the ladder** (see §6), one feature per improvement-slot.
- **Pre-committed research plan, held loosely.** We plan the full backlog up front (so we're
  never scrambling for "what's next"), but results are allowed to reorder the queue — "that
  did nothing, so next we try…" is only honest if the next pick can actually respond to the
  last result. **Prioritized queue, not an immutable script.**

### Evaluation rules (the methodological backbone)

- **Feature impact is measured on historical walk-forward backtests** (thousands of past
  games) — leakage-safe, prior-only rolling features, backward-exclusive as-of merges. This
  is what we *claim* about a feature ("+1.2% accuracy / −0.004 log-loss over 8 seasons").
- **The live season is the public scoreboard** — drama and accountability, but statistically
  noisy (especially NFL). We never confuse "this feature helped" (backtest, big N) with "we
  went 6–4 this week" (live, small N, entertainment).
- **Guard against the multiple-comparisons trap.** Testing hundreds of features against the
  same holdout is p-hacking waiting to happen. Mitigations: (a) the pre-registered roadmap,
  (b) a **final untouched test set** never used for selection, (c) report honest effect sizes
  with the eval window stated, (d) prefer walk-forward out-of-sample over in-sample deltas.
- **Prior experience is disclosed, not hidden.** We've built these models before (that's the
  playground repo). The honest framing is: *"I've done this — now I'm rebuilding it properly,
  in public, one documented feature at a time, so you can see exactly what each piece is
  worth."* Never fake a naïve-beginner arc.

---

## 6. The feature ladder (one ladder, six instantiations)

The progression is essentially the same conceptual ladder for every sport; each sport fills
in the rungs with its own specifics.

1. **Basic box stats** — the deliberately-simple day-1 baseline.
2. **Rolling windows** — last-N form, recency-weighted.
3. **Opponent adjustment** — strength of schedule, opponent-allowed.
4. **Rest / schedule / travel** — back-to-backs, days off, distance, time zones.
5. **Derived efficiency stats** — per-possession / pace-adjusted / sport-specific advanced.
6. **Matchup & interaction features** — style-vs-style, pace interactions.
7. **Situational** — home/road splits, motivation, rest/tanking spots.
8. **Market-adjacent probes** (the decomposition rungs) — injuries, confirmed lineups,
   line-movement/sharp-money signals. These are where Act 2 lives: we measure the residual
   gap directly.

### Worked example — NFL first-cut order (to unblock day 1)

> Illustrative; the exhaustive per-sport backlog is the companion `FEATURE_ROADMAP.md`
> (next deliverable). Held loosely per §5.

1. Team win% / Elo baseline
2. Points for / against (season)
3. Rolling last-4 form
4. Home field
5. Rest days / bye-week
6. Opponent-adjusted scoring
7. Travel distance / time zone
8. Pass/rush efficiency splits
9. Turnover differential (regressed)
10. Pace / plays-per-game
11. Down-weighting for garbage-time
12. QB availability (→ opens the injuries decomposition thread)
13. Weather (outdoor games)
14. Line-movement probe (Act 2 begins)

---

## 7. Per-sport cadence & rollout

**Improvement cadence is a content-rhythm choice** matched to each sport's game frequency —
*not* a technical limit (we can evaluate any sport any day on historical data). Match cadence
to **ladder depth** so nothing runs dry by accident (and so plateaus land intentionally). The
**free data source** column is load-bearing: it's what makes each sport's ladder *realistic*
(see §6 and the roadmap's data-availability audit).

| Sport | Launch | Cadence | Free data source | Notes |
|---|---|---|---|---|
| **NFL** | Fall wave (now) | ~twice a week | `nflverse` (odds built in) | Best reach; weak live signal (small N) — lean on backtests for impact claims. |
| **CFB** | Fall wave (now) | ~twice a week | **CFBD** free API (`cfbd` / `cfbfastR`; betting lines included) | Huge audience; 130+ FBS teams + big talent gaps → very predictable SU (but the market prices it too). Free-tier rate limits → maybe ~$10/mo Patreon at live scale. |
| **MLB** | Soon after | ~few per week | `pybaseball` + Statcast | Ongoing now, huge sample (stable signal); ~6 weeks of regular season left. |
| **NBA** | ~late October | ~daily | NBA data (existing) + Kaggle backfill | Games most days; daily cadence reaches the wall fast → early Act-2 showcase. |
| **NHL** | ~October | ~daily | NHL API + MoneyPuck (xG) | Games most days; similar profile to NBA. |
| **Soccer** | Later | ~few per week (once seasons underway) | StatsBomb / Understat / football-data.co.uk | Biggest global audience but hardest (3-way outcomes, many leagues). |

Staggering is a feature: NFL/CFB climbing while NBA decomposes the wall = always something to say.

---

## 8. The content system

Three content types, mapped to formats that fit each job:

- **Feature posts — one PER SPORT (the daily engine).** `tested X → what it did → what's
  next.` Each sport getting an improvement that day gets its *own* focused post — so a peak
  fall day can be 3–4 feature posts. Carousel or short reel; the money shot is a before/after
  walk-forward accuracy chart. This is what carries the daily cadence even on no-game days.
- **Predictions — ONE combined reel per day (all sports).** Reels travel furthest, so the
  daily slate stays a single, curated, high-production reel spanning sports (highlight the
  slate as it grows — don't enumerate 40 games). Framed as *the model's call*, attributed to
  the algorithm, neutral and hype-free: "CHALK's call: [team] to win, [score]. Graded
  tomorrow." No tout, no nag — the honesty is that we always post the result.
- **Results — story + track record.** Quick daily grade in the story; the running track
  record stays always-visible (pinned/site); a weekly "report card" reel is the in-feed
  accountability anchor. Results are *prominent*, never buried — visible grading is the brand.

**Volume & platform split (important consequence of per-sport feature posts).** On a peak fall
day that's 3–4 feature posts + 1 predictions reel + results. That volume is *fine and normal
on X and Reddit* (high-volume, technical, per-sport granularity is welcome there). On
**Instagram**, 5–6 posts/day risks feed fatigue and algorithmic throttling. **Recommendation:
per-sport depth lives on X/Reddit; Instagram gets a curated subset** — always the single
predictions reel, plus either the day's single most interesting feature post or a combined
multi-sport carousel. One brand voice, platform-appropriate volume. *(Owner call — see §13.)*

**Cadence realism:** feature posts are daily (per active sport); predictions/results are
**game-day-driven**. Early on (NFL twice-weekly) volume is modest; as MLB→NBA→NHL stack
through the fall it ramps to several posts/day. The multi-sport rollout is what builds the
rhythm.

**Pinned 3 (newcomer's why → how → status):**
1. **Manifesto** — the thesis; why a market-blind model; the honesty promise.
2. **System diagram** — the end-to-end pipeline as one graphic.
3. **Current track record** — where the model is now.

**Voice (the algorithm-as-character):** rigorous, self-aware, dry, anti-hype — the one honest
machine in a feed of touts. *(A full voice/style guide is a TBD, calibrated during the
cautious phase — §10.)*

---

## 9. Tiered Autonomy ("Claude runs it, within guardrails")

**The reconciliation:** the owner is the creative director who sets the rules **once, up
front** (voice, Constitution, roadmap, what's post-worthy). The system then executes daily
*within* those rules and escalates only edge cases. Heavy human involvement now; automated
ops after. The direction is **locked**, not on autopilot — only execution is automated.

Every daily action falls into one bucket:

- 🟢 **Green — full auto, zero human.** Data pull; scheduled feature-add per the roadmap;
  retrain; walk-forward eval; generate predictions; render cards/reels; auto-grade yesterday's
  results; update the track record. Deterministic — no judgment needed.
- 🟡 **Yellow — auto-drafted → guardrail-checked → post or batch-approve.** Feature writeups,
  prediction captions, results copy. LLM-drafted from the actual numbers, then run through the
  automated checks (§9.1). Then either auto-posted or held for a batch the owner clears.
- 🔴 **Red — halt + escalate, never auto-post.** Anomalies: pipeline break, data source down,
  a feature that regresses the model unexpectedly, a factual edge case, an odd/implausible
  pick, or any slate touching tragedy/serious injury. These wait for the human.

### 9.1 Automated pre-publish guardrail checks (gate on all 🟡 content)

- No tout/hype language (denylist + LLM check).
- Every stated number matches the underlying data (no hallucinated stats).
- Required disclaimer present (entertainment/education; 21+; not betting advice).
- On-voice (style check against the voice guide).
- Not about a tragedy/serious injury (keyword + LLM screen → route to 🔴 if hit).
- Idempotency: never double-post the same item (track posted IDs/URLs).

### 9.2 How "Claude runs it" actually works (honest mechanics)

Claude is not a 24/7 daemon. The setup is two layers:

- **Deterministic pipeline** on **GitHub Actions** (owner has GitHub Pro — cron-triggered
  workflows, generous minutes, private-repo support); builds on the existing `nightly.py` +
  nightly CI split; does all 🟢 work and *drafts* 🟡 artifacts. Rendered assets → R2; all keys
  in GitHub Actions encrypted secrets.
- **A scheduled Claude agent** fires on cadence to do the 🟡 judgment work (finalize copy,
  sanity-check the reel, decide post-worthiness) and to detect/route 🔴s to the owner.

**Honest caveat:** an agent posting to a public account *can* err. The guardrails (§9.1), the
cautious rollout (§10), and a lightweight periodic human check are therefore mandatory — they
protect the one asset (trust) the whole brand is built on.

---

## 10. Rollout posture: cautious → loosen

- **Weeks ~1–4 (calibration):** most 🟡 content batches to the owner for quick approval, so we
  tune the voice and guardrails on real output. 🟢 runs free; 🔴 always escalates.
- **After calibration:** as the automated checks prove out, progressively loosen toward more
  auto-posting of 🟡. Ship careful, loosen deliberately — much easier than clawing back trust.
- The owner can tighten back to full-approval mode at any time (a single switch).

---

## 11. Repo plan

- **Playground → private.** Rename the current `basketball_betting` repo to
  `betting_testingground` and make it private. It stays the scratch/experimentation space and
  the source of ported infrastructure. (GitHub auto-redirects the old URL — low-risk.)
- **`chalk` → new, public, pristine.** The public face; clean history people can follow.
- **Port the infra, start the model simple.** Data adapters, leakage-safe feature patterns,
  eval harness, `content/render` + `review`, Remotion reel engine, SHA-256 track-record
  locking — all come over mature. The *model* is what starts simple and grows in public. No
  rebuilding plumbing on camera.

---

## 12. Monetization (someday, not a driver)

The honest brand doesn't kill monetization — it *redirects* it off the scammy path.
- **Foreclosed (correctly):** selling picks / "a system that beats Vegas."
- **Open, all compounding off credibility + reach:** ML/data-tooling sponsorships; a premium
  tier for the underlying predictions/data/research; an honest forecasting API/dataset;
  eventually newsletter/merch/a book. Slower than touting, far more durable.
- **Handle with care if ever pursued:** sportsbook affiliate links — classic sports money, but
  in tension with the anti-tout voice; only with disclosure, and it can muddy the brand.

---

## 13. What's locked vs. still open

**Locked (this doc):** the thesis; the Constitution; the two-act arc; progressive
one-experiment-a-day build; walk-forward eval discipline; the feature-ladder framework;
per-sport cadence & rollout order; the three-part content loop & formats; single combined
predictions reel + per-sport feature posts; tiered autonomy; cautious→loosen rollout; repo
plan; **GitHub Actions (Pro) as the CI/CD backbone.**

**Still open (TBD — need owner input or a calibration period):**
- Full per-sport feature backlogs → companion `FEATURE_ROADMAP.md` (next deliverable).
- **Posting volume / platform split** (§8): confirm per-sport depth on X/Reddit + a curated
  subset on IG, vs. full per-sport everywhere.
- The voice/style guide (calibrate during weeks 1–4).
- Approval-queue mechanism: **Telegram/Slack bot** (approve from phone, lowest friction) vs.
  a **web dashboard** (extend `content/review.py` or the lovable app). Recommendation: bot.
- Instagram Graph API app-review timing (interim: approve → post manually, per §10).
- Exact posting times per platform/sport.
- The pinned system-diagram graphic (design task).

---

## 14. Path to launch

The owner wants the whole thing **fully planned before any code.** So we complete a planning
package first, review each piece thoroughly, then build.

### Phase A — Planning package (docs, no code)

1. **`FEATURE_ROADMAP.md`** — starts with a **per-sport data-availability audit** (the chosen
   free dataset + the exact fields/tables it actually exposes), then derives the feature
   ladders *from that*: ~30–50 features × 6 leagues, each entry citing its real data
   field/source, its hypothesis, and how impact is measured. **No aspirational features —
   every rung maps to data we actually have.** This is the research backbone.
2. **`ARCHITECTURE.md`** — the engineering blueprint: repo structure; data sources & pipeline
   per sport; the model + walk-forward eval harness; content generators; publishing adapters
   (IG / X / Reddit); the approval queue; R2 storage; the GitHub Actions topology; the
   scheduled-agent design; secrets management.
3. **`CONTENT_SPEC.md`** — post templates per type × platform; the reel spec; caption
   templates; the voice/style guide v1; the 🟡 guardrail-check spec; posting times.
4. **`OPS_RUNBOOK.md`** — Green/Yellow/Red workflows in detail; escalation paths; the
   calibration process; failure modes & recovery; monitoring/alerting; the tighten-back switch.
5. **`BUILD_PLAN.md`** — phased, ordered milestones with acceptance criteria (Phase B,
   expanded).

### Phase B — Build (only after the package is reviewed & locked)

Repo surgery → day-1 NFL model + eval harness → content loop (per-sport feature posts +
combined predictions reel + results/grading) → approval queue + 🟡 guardrails → GitHub Actions
pipeline + scheduled Claude agent → first end-to-end experiment as the flagship launch post.
