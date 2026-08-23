# CHALK — Launch runbook (M6)

The whole system is built and green **in the dark** (M0–M5): data → leakage-safe features
→ one honest experiment at a time → rendered content → LLM copy → 8 guardrail checks →
approval queue → (dry-run) publish → daily orchestrator + scheduled agent. Nothing can post
(`AUTONOMY_MODE=approve_all` + `CHALK_DRY_RUN=1` + kill switch). This runbook is the
owner-only, outward-facing go-live. Do the steps in order.

## Step 0 — repo cutover (one-time)
The public `sagrawal11/chalk` still holds an early scaffold push and should be replaced by
the clean local tree at `~/Desktop/App Projects/chalk` (currently unpushed).

```bash
# remove the stale public repo (grant the scope first if needed)
gh auth refresh -h github.com -s delete_repo
gh repo delete sagrawal11/chalk --yes
# recreate it public + do the INITIAL push (you run the push)
gh repo create sagrawal11/chalk --public \
  --description "CHALK — a market-blind sports-prediction research project, built in public."
git -C "$HOME/Desktop/App Projects/chalk" remote add origin https://github.com/sagrawal11/chalk.git
git -C "$HOME/Desktop/App Projects/chalk" push -u origin main
```
CI (`ci.yml`: pinned-image pytest + reel contract) should go green on the push.

## Step 1 — Actions secrets
No secret is in the repo; the workflows read GitHub Actions encrypted secrets. Add what you
have (publishers stay dry-run until their creds exist):

```bash
R=sagrawal11/chalk
gh secret set ANTHROPIC_API_KEY   --repo $R    # LLM copy drafting (else the template runs)
gh secret set ODDS_API_KEY        --repo $R    # free odds — grading only, never a model input
gh secret set CFBD_API_KEY        --repo $R    # college football (M7)
gh secret set R2_ACCOUNT_ID       --repo $R
gh secret set R2_ACCESS_KEY_ID    --repo $R
gh secret set R2_SECRET_ACCESS_KEY --repo $R
gh secret set R2_BUCKET_NAME      --repo $R
gh secret set KAGGLE_USERNAME     --repo $R
gh secret set KAGGLE_KEY          --repo $R
gh secret set UPSTASH_REDIS_URL   --repo $R
# publishing (add when ready — Reddit + X carry launch; IG is manual-interim)
gh secret set REDDIT_CLIENT_ID --repo $R; gh secret set REDDIT_CLIENT_SECRET --repo $R
gh secret set REDDIT_REFRESH_TOKEN --repo $R
gh secret set X_API_KEY --repo $R; gh secret set X_API_SECRET --repo $R
gh secret set X_ACCESS_TOKEN --repo $R; gh secret set X_ACCESS_SECRET --repo $R
```
(The values live in your local `.env` / the private `betting_testingground` repo's secrets.)

## Step 2 — go-live (cautious)
1. In `.github/workflows/chalk_daily.yml` (and `chalk_weekly.yml`), **uncomment the `schedule:` cron**.
2. Keep `AUTONOMY_MODE: approve_all` (nothing auto-posts) for weeks 1–4.
3. Flip `CHALK_DRY_RUN` to `"0"` only when you're ready for real posts to Reddit/X (IG stays manual).
4. Run once manually first: Actions → **CHALK Daily** → *Run workflow*; confirm it lands drafts and posts nothing.
5. Approve the first batch (`python -m agent.agent_run` shows it; the Telegram/Slack bot is the phone-friendly version — pick one and wire it).

## Go-live checklist (BUILD_PLAN §4)
- [x] NFL champion promoted through ≥ Rung 3 with ledger rows for every experiment (kept + dropped) — `nfl-v2`, ledger has NFL-06/10/11.
- [x] `honest_readout.py` emits the untouched-test number + the selected-vs-untouched gap + multiple-comparisons counter.
- [x] Every pick locked (SHA-256) pre-tip; unpriced picks → `units=NaN` (no fabricated ROI).
- [x] Cards + combined reel render from real data in the locked skin; reel pipeline-wired.
- [x] All 8 guardrail checks live + gating; tout / hallucinated-number / tragedy test drafts blocked or 🔴-routed.
- [x] X + Reddit idempotent (proven no-double-post); IG approve→manual interim; global kill switch works.
- [x] Full unattended daily run lands drafts with zero auto-posts; a broken source → 🔴 + graceful skip.
- [ ] `/api/experiments` + the changelog site live (API done; wire the frontend view + deploy).
- [ ] All secrets in Actions; brand default = CHALK; no `betting_venv/`; tests green in CI. *(local ✓; confirm on push)*
- [ ] A read-through against the Constitution confirms zero violations in the launch batch.

## Daily ops (OPS_RUNBOOK §12)
Glance at the run summary (green exit? slate locked? yesterday graded? 🔴 count 0?), approve
the batch, resolve any 🔴s, confirm the weekly retrain, watch the IG ~60-day token.

## Kill switch / rollback
Set repo variable/secret `CHALK_KILL_SWITCH=1` (halts all posting) and/or `AUTONOMY_MODE=approve_all`.
Corrections are public + prompt (Constitution #6) — edit the reel/card + a pinned correction; never quiet-delete.
