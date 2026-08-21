/**
 * Shared brand primitives used by every frame. The Wordmark's red period is a
 * LOCKED brand element — do not restyle it.
 */
import React from 'react';
import {FONTS} from './theme';

type Palette = {ink: string; accent: string; muted: string; hairline: string};

/**
 * "CHALK." wordmark — Fraunces 700, ~54px, letter-spacing -1px, with the
 * period rendered in the accent colour. `color` is the wordmark ink; `accent`
 * is the locked period colour.
 */
export const Wordmark: React.FC<{
  color: string;
  accent: string;
  size?: number;
}> = ({color, accent, size = 54}) => {
  return (
    <span
      style={{
        fontFamily: FONTS.serif,
        fontWeight: 700,
        fontSize: size,
        letterSpacing: -1,
        lineHeight: 1,
        color,
        whiteSpace: 'nowrap',
      }}
    >
      CHALK<span style={{color: accent}}>.</span>
    </span>
  );
};

/** Monospace kicker/label/date/handle — UPPERCASE, tracked, usually muted. */
export const Mono: React.FC<{
  children: React.ReactNode;
  color: string;
  size?: number;
  spacing?: number;
  weight?: 400 | 500 | 600;
  style?: React.CSSProperties;
}> = ({children, color, size = 22, spacing = 2, weight = 500, style}) => (
  <span
    style={{
      fontFamily: FONTS.mono,
      fontWeight: weight,
      fontSize: size,
      letterSpacing: spacing,
      textTransform: 'uppercase',
      color,
      lineHeight: 1,
      ...style,
    }}
  >
    {children}
  </span>
);

/** Full-width 1px hairline in the palette's hairline colour. */
export const Hairline: React.FC<{color: string; style?: React.CSSProperties}> = ({
  color,
  style,
}) => <div style={{height: 1, width: '100%', backgroundColor: color, ...style}} />;

/** Top row: wordmark on the left, a mono slug on the right. */
export const TopRow: React.FC<{
  palette: Palette;
  wordmarkColor: string;
  right: React.ReactNode;
}> = ({palette, wordmarkColor, right}) => (
  <div
    style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
    }}
  >
    <Wordmark color={wordmarkColor} accent={palette.accent} />
    <Mono color={palette.muted} size={22} spacing={3}>
      {right}
    </Mono>
  </div>
);

/** Bottom row: handle on the left, a muted mono note on the right. */
export const Footer: React.FC<{
  palette: Palette;
  left: React.ReactNode;
  right: React.ReactNode;
  leftColor?: string;
}> = ({palette, left, right, leftColor}) => (
  <div
    style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
    }}
  >
    <Mono color={leftColor ?? palette.muted} size={22} spacing={3}>
      {left}
    </Mono>
    <Mono color={palette.muted} size={22} spacing={3}>
      {right}
    </Mono>
  </div>
);
