/**
 * CHALK — "Editorial Terminal" design tokens (LOCKED).
 *
 * Single source of truth for colour, type, spacing and motion. Every frame
 * imports from here so the reel stays pixel-faithful to the brand.
 */
import {loadFont as loadFraunces} from '@remotion/google-fonts/Fraunces';
import {loadFont as loadPlexMono} from '@remotion/google-fonts/IBMPlexMono';
import {loadFont as loadInter} from '@remotion/google-fonts/Inter';

// ---------------------------------------------------------------------------
// Fonts (loaded once at module import; Remotion blocks the render until ready).
// NOTE: @remotion/google-fonts fetches the font files over the network at
// build/render time, so the FIRST render needs connectivity (then cached).
// ---------------------------------------------------------------------------
const fraunces = loadFraunces('normal', {weights: ['400', '600', '700'], subsets: ['latin']});
const frauncesItalic = loadFraunces('italic', {weights: ['400', '600'], subsets: ['latin']});
const plexMono = loadPlexMono('normal', {weights: ['400', '500', '600'], subsets: ['latin']});
const inter = loadInter('normal', {weights: ['400', '500', '600'], subsets: ['latin']});

export const FONTS = {
  /** Serif — team names, score numerals, headlines, verdicts. */
  serif: fraunces.fontFamily,
  serifItalic: frauncesItalic.fontFamily,
  /** Monospace — labels, kickers, date, handle (UPPERCASE, tracked, muted). */
  mono: plexMono.fontFamily,
  /** Sans — body / utility (rarely visible but registered per the brief). */
  sans: inter.fontFamily,
} as const;

/** Force fonts to finish downloading before the render starts. */
export const waitForFonts = () =>
  Promise.all([
    fraunces.waitUntilDone(),
    frauncesItalic.waitUntilDone(),
    plexMono.waitUntilDone(),
    inter.waitUntilDone(),
  ]);

// ---------------------------------------------------------------------------
// Colour — light frames (Intro / Game) and the dark Outro frame.
// ---------------------------------------------------------------------------
export const LIGHT = {
  bg: '#F4F1EA',
  ink: '#16130F',
  muted: '#6B6459',
  accent: '#C1272D',
  hairline: 'rgba(22,19,15,.09)',
} as const;

export const DARK = {
  bg: '#15130E',
  text: '#F1ECE0',
  muted: '#9A9184',
  accent: '#E7473C',
  hairline: 'rgba(255,255,255,.12)',
} as const;

// ---------------------------------------------------------------------------
// Layout — canvas + frame padding.
// ---------------------------------------------------------------------------
export const CANVAS = {
  width: 1080,
  height: 1920,
  fps: 30,
} as const;

export const PADDING = {
  top: 110,
  bottom: 110,
  side: 80,
} as const;

// ---------------------------------------------------------------------------
// Per-frame durations (frames @ 30fps) and the wipe overlap between games.
// Exported so calculateMetadata() can scale total duration to the slate.
// ---------------------------------------------------------------------------
export const DURATION = {
  intro: 75,
  game: 75,
  outro: 105,
  /** Frames a game overlaps its predecessor for the wipe transition. */
  wipe: 12,
} as const;

// ---------------------------------------------------------------------------
// Data contract — the JSON slate the Python pipeline writes.
// ---------------------------------------------------------------------------
export type GameSlate = {
  homeName: string;
  homeShort: string;
  homeCity: string;
  awayName: string;
  awayShort: string;
  awayCity: string;
  homeScore: number;
  awayScore: number;
  winnerSide: 'home' | 'away';
  /** 0–100. */
  confidence: number;
  reasoning: string;
};

export type ReelProps = {
  date: string;
  trackRecord: {winPct: number; nPicks: number};
  yesterday: {correct: number; total: number};
  slate: GameSlate[];
};

// ---------------------------------------------------------------------------
// Shared type helpers used across frames.
// ---------------------------------------------------------------------------
export const MONO_LABEL = (extra?: React.CSSProperties): React.CSSProperties => ({
  fontFamily: FONTS.mono,
  fontWeight: 500,
  textTransform: 'uppercase',
  ...extra,
});
