/**
 * INTRO frame (~75f, light). Top row wordmark + date; accent kicker; a big
 * three-line Fraunces headline that staggers up; a muted subhead; a
 * track-record block; and a footer with handle + "swipe →".
 */
import React from 'react';
import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {FONTS, LIGHT, PADDING, type ReelProps} from '../theme';
import {Footer, Hairline, Mono, TopRow} from '../components';

const P = LIGHT;

/** opacity 0→1 over [start, start+len]. */
const fade = (frame: number, start: number, len = 15) =>
  interpolate(frame, [start, start + len], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

export const Intro: React.FC<Pick<ReelProps, 'date' | 'slate' | 'trackRecord'>> = ({
  date,
  slate,
  trackRecord,
}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const n = slate.length;

  // Wordmark + date fade in 0–15f.
  const headerOpacity = fade(frame, 0, 15);

  // Each headline line springs up (translateY 30→0 + opacity), staggered.
  const line = (index: number) => {
    const delay = 8 + index * 8; // ~8f, ~16f, ~24f
    const s = spring({frame: frame - delay, fps, config: {damping: 200}});
    return {
      opacity: s,
      transform: `translateY(${interpolate(s, [0, 1], [30, 0])}px)`,
    };
  };

  // Kicker rides just ahead of the first headline line.
  const kicker = (() => {
    const s = spring({frame: frame - 6, fps, config: {damping: 200}});
    return {opacity: s, transform: `translateY(${interpolate(s, [0, 1], [30, 0])}px)`};
  })();

  const subheadOpacity = fade(frame, 30, 20);

  // Track-record block fades up 45–65f.
  const trackS = spring({frame: frame - 45, fps, config: {damping: 200}});
  const trackStyle: React.CSSProperties = {
    opacity: interpolate(trackS, [0, 1], [0, 1]),
    transform: `translateY(${interpolate(trackS, [0, 1], [24, 0])}px)`,
  };

  const winPctTxt = Number.isFinite(trackRecord.winPct)
    ? trackRecord.winPct.toFixed(1)
    : '—';
  const nPicksTxt = trackRecord.nPicks.toLocaleString('en-US');

  return (
    <AbsoluteFill style={{backgroundColor: P.bg}}>
      <div
        style={{
          position: 'absolute',
          inset: 0,
          paddingTop: PADDING.top,
          paddingBottom: PADDING.bottom,
          paddingLeft: PADDING.side,
          paddingRight: PADDING.side,
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {/* Top row: wordmark + date */}
        <div style={{opacity: headerOpacity}}>
          <TopRow palette={P} wordmarkColor={P.ink} right={date} />
        </div>

        {/* Kicker */}
        <div style={{marginTop: 96, ...kicker}}>
          <Mono color={P.accent} size={24} spacing={10} weight={600}>
            Today&rsquo;s calls
          </Mono>
        </div>

        {/* Headline: "N games. / N predictions. / 0 odds." */}
        <div
          style={{
            marginTop: 26,
            fontFamily: FONTS.serif,
            fontWeight: 700,
            fontSize: 150,
            lineHeight: 0.92,
            color: P.ink,
            letterSpacing: -2,
          }}
        >
          <div style={line(0)}>{n} games.</div>
          <div style={line(1)}>{n} predictions.</div>
          <div style={line(2)}>0 odds.</div>
        </div>

        {/* Subhead — last sentence bold ink */}
        <div
          style={{
            marginTop: 40,
            maxWidth: 820,
            fontFamily: FONTS.serif,
            fontWeight: 400,
            fontSize: 46,
            lineHeight: 1.25,
            color: P.muted,
            opacity: subheadOpacity,
          }}
        >
          Every game tonight, called by our model before tip-off.{' '}
          <span style={{fontWeight: 600, color: P.ink}}>Winner and final score.</span>
        </div>

        {/* Flex spacer pushes the track record to the lower third */}
        <div style={{flex: 1}} />

        {/* Track record block */}
        <div style={trackStyle}>
          <Hairline color={P.hairline} style={{marginBottom: 26}} />
          <Mono color={P.muted} size={22} spacing={6}>
            Track record
          </Mono>
          <div
            style={{
              marginTop: 16,
              fontFamily: FONTS.serif,
              fontWeight: 400,
              fontSize: 52,
              lineHeight: 1.2,
              color: P.ink,
            }}
          >
            <b style={{fontWeight: 700}}>{winPctTxt}%</b> of games called correctly ·{' '}
            <b style={{fontWeight: 700}}>{nPicksTxt}</b> graded
          </div>
        </div>

        {/* Footer */}
        <div style={{marginTop: 40, opacity: fade(frame, 55, 15)}}>
          <Footer palette={P} left="@playthechalk" right="swipe →" />
        </div>
      </div>
    </AbsoluteFill>
  );
};
