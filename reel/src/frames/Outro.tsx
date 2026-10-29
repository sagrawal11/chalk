/**
 * OUTRO frame (~105f, DARK). Top wordmark (light) + "The receipts"; accent
 * kicker "YESTERDAY"; a big "We went / {correct} for {total}." with the
 * {correct} number counting up; a season line; a CTA that slides up; footer.
 */
import React from 'react';
import {
  AbsoluteFill,
  Easing,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import {DARK, FONTS, PADDING, type ReelProps} from '../theme';
import {Footer, Hairline, Mono, TopRow} from '../components';

const P = {ink: DARK.text, accent: DARK.accent, muted: DARK.muted, hairline: DARK.hairline};

const fade = (frame: number, start: number, len = 15) =>
  interpolate(frame, [start, start + len], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

export const Outro: React.FC<Pick<ReelProps, 'yesterday' | 'trackRecord'>> = ({
  yesterday,
  trackRecord,
}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  const headerOpacity = fade(frame, 0, 15);

  // Kicker + headline stagger in.
  const kickerS = spring({frame: frame - 6, fps, config: {damping: 200}});
  const headS = spring({frame: frame - 12, fps, config: {damping: 200}});
  const headStyle: React.CSSProperties = {
    opacity: headS,
    transform: `translateY(${interpolate(headS, [0, 1], [30, 0])}px)`,
  };

  // "{correct}" counts up 0 → correct over ~40f, ease-out.
  const countProgress = interpolate(frame, [14, 54], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.out(Easing.cubic),
  });
  const correct = Math.round(yesterday.correct * countProgress);

  const seasonOpacity = fade(frame, 46, 18);

  // CTA slides up near the end.
  const ctaS = spring({frame: frame - 60, fps, config: {damping: 200}});
  const ctaStyle: React.CSSProperties = {
    opacity: ctaS,
    transform: `translateY(${interpolate(ctaS, [0, 1], [30, 0])}px)`,
  };

  const winPctTxt = Number.isFinite(trackRecord.winPct)
    ? trackRecord.winPct.toFixed(1)
    : '-';
  const nPicksTxt = trackRecord.nPicks.toLocaleString('en-US');

  return (
    <AbsoluteFill style={{backgroundColor: DARK.bg}}>
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
        {/* Top row: light wordmark + "The receipts" */}
        <div style={{opacity: headerOpacity}}>
          <TopRow palette={P} wordmarkColor={DARK.text} right="The receipts" />
        </div>

        {/* Kicker */}
        <div style={{marginTop: 96, opacity: kickerS}}>
          <Mono color={P.accent} size={24} spacing={10} weight={600}>
            Yesterday
          </Mono>
        </div>

        {/* Headline: "We went / {correct} for {total}." */}
        <div
          style={{
            marginTop: 26,
            fontFamily: FONTS.serif,
            fontWeight: 700,
            fontSize: 130,
            lineHeight: 0.94,
            color: DARK.text,
            letterSpacing: -2,
            ...headStyle,
          }}
        >
          <div>We went</div>
          <div style={{color: DARK.accent}}>
            <span style={{fontVariantNumeric: 'tabular-nums'}}>{correct}</span> for{' '}
            {yesterday.total}.
          </div>
        </div>

        {/* Season line */}
        <div style={{marginTop: 44, opacity: seasonOpacity}}>
          <div
            style={{
              fontFamily: FONTS.serif,
              fontWeight: 400,
              fontSize: 52,
              lineHeight: 1.2,
              color: DARK.text,
              maxWidth: 860,
            }}
          >
            This season: {winPctTxt}% of games called correctly.
          </div>
          <div style={{marginTop: 18}}>
            <Mono color={P.muted} size={22} spacing={4}>
              {nPicksTxt} graded · every pick locked before tip-off
            </Mono>
          </div>
        </div>

        {/* Flex spacer pushes the CTA to the lower third */}
        <div style={{flex: 1}} />

        {/* CTA */}
        <div style={ctaStyle}>
          <Hairline color={P.hairline} style={{marginBottom: 30}} />
          <div
            style={{
              fontFamily: FONTS.serif,
              fontWeight: 400,
              fontSize: 58,
              lineHeight: 1.18,
              color: DARK.text,
            }}
          >
            <div>New calls every morning.</div>
            <div>
              Follow <b style={{fontWeight: 700, color: DARK.accent}}>@playthechalk</b>.
            </div>
          </div>
        </div>

        {/* Footer */}
        <div style={{marginTop: 40, opacity: fade(frame, 70, 15)}}>
          <Footer
            palette={P}
            left="playthechalk.com"
            right="100% algorithmic · full record online"
          />
        </div>
      </div>
    </AbsoluteFill>
  );
};
