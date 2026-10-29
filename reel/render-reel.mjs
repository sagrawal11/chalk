#!/usr/bin/env node
/**
 * Thin render wrapper for the daily job.
 *
 *   node render-reel.mjs [--check] <slate.json> [out.mp4]
 *
 * Defaults: slate = ./sample-slate.json, out = ./out/reel-<date>.mp4
 *
 * It validates the slate against the data contract (see SLATE_CONTRACT.md), then
 * invokes the Remotion CLI:  npx remotion render Reel <out> --props=<slate>
 *
 * With --check it validates and exits 0 WITHOUT rendering, the fast CI gate and
 * the pipeline seam smoke-test (Python writes the slate; see content/reel_slate.py).
 *
 * The Python pipeline calls this after writing the day's slate JSON.
 */
import {spawnSync} from 'node:child_process';
import {readFileSync, existsSync, mkdirSync} from 'node:fs';
import {dirname, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));

// Args: [--check] <slate.json> [out.mp4].  --check validates only (no render).
const argv = process.argv.slice(2);
const checkOnly = argv.includes('--check');
const positional = argv.filter((a) => !a.startsWith('--'));

const slatePath = resolve(positional[0] ?? resolve(HERE, 'sample-slate.json'));

if (!existsSync(slatePath)) {
  console.error(`[render-reel] slate not found: ${slatePath}`);
  process.exit(1);
}

let slate;
try {
  slate = JSON.parse(readFileSync(slatePath, 'utf8'));
} catch (err) {
  console.error(`[render-reel] slate is not valid JSON: ${err.message}`);
  process.exit(1);
}

// ---- Validate the data contract (fail fast with a clear message) -----------
const problems = [];
const req = (cond, msg) => {
  if (!cond) problems.push(msg);
};
req(typeof slate.date === 'string' && slate.date.length > 0, 'date must be a non-empty string');
req(slate.trackRecord && typeof slate.trackRecord.winPct === 'number', 'trackRecord.winPct must be a number');
req(slate.trackRecord && typeof slate.trackRecord.nPicks === 'number', 'trackRecord.nPicks must be a number');
req(slate.yesterday && typeof slate.yesterday.correct === 'number', 'yesterday.correct must be a number');
req(slate.yesterday && typeof slate.yesterday.total === 'number', 'yesterday.total must be a number');
req(Array.isArray(slate.slate) && slate.slate.length > 0, 'slate must be a non-empty array of games');

if (Array.isArray(slate.slate)) {
  slate.slate.forEach((g, i) => {
    const at = `slate[${i}]`;
    for (const k of ['homeName', 'homeShort', 'homeCity', 'awayName', 'awayShort', 'awayCity', 'reasoning']) {
      req(typeof g?.[k] === 'string' && g[k].length > 0, `${at}.${k} must be a non-empty string`);
    }
    for (const k of ['homeScore', 'awayScore', 'confidence']) {
      req(typeof g?.[k] === 'number', `${at}.${k} must be a number`);
    }
    req(g?.winnerSide === 'home' || g?.winnerSide === 'away', `${at}.winnerSide must be "home" or "away"`);
  });
}

if (problems.length) {
  console.error('[render-reel] slate failed validation:');
  for (const p of problems) console.error('  - ' + p);
  process.exit(1);
}

if (checkOnly) {
  console.log(`[render-reel] slate OK, ${slate.slate.length} game(s). (--check: not rendering)`);
  process.exit(0);
}

// ---- Resolve output path ---------------------------------------------------
const safeDate = String(slate.date).replace(/[^A-Za-z0-9]+/g, '-').replace(/^-|-$/g, '').toLowerCase();
const defaultOut = resolve(HERE, 'out', `reel-${safeDate || 'output'}.mp4`);
const outPath = resolve(positional[1] ?? defaultOut);
mkdirSync(dirname(outPath), {recursive: true});

console.log(`[render-reel] slate : ${slatePath}`);
console.log(`[render-reel] games : ${slate.slate.length}`);
console.log(`[render-reel] out   : ${outPath}`);

// ---- Render ----------------------------------------------------------------
// On macOS the Homebrew `node` binary is a UNIVERSAL binary; a spawned child
// can land on the x86_64 slice under Rosetta, which then fails to load the
// arm64 rspack bundler binding. Pin the child to this process's architecture
// via `arch -<arch>` so the correct native binding resolves. No-op elsewhere.
const remotionArgs = ['remotion', 'render', 'Reel', outPath, `--props=${slatePath}`];
const [cmd, args] =
  process.platform === 'darwin'
    ? ['arch', [`-${process.arch}`, 'npx', ...remotionArgs]]
    : ['npx', remotionArgs];

const res = spawnSync(cmd, args, {cwd: HERE, stdio: 'inherit', env: process.env});

if (res.error) {
  console.error(`[render-reel] failed to launch remotion: ${res.error.message}`);
  process.exit(1);
}
process.exit(res.status ?? 1);
