/**
 * GAME frame (parametric, ~75f, light). Top wordmark + "Game k / N"; pager
 * dots; a "{HOME CITY} · {AWAY CITY}" lead; a two-row game block (side dot +
 * team name + score) bounded by hairlines with the scores COUNTING UP from 0;
 * a verdict; a CONFIDENCE bar that fills via spring; an italic reason; footer.
 *
 * The horizontal WIPE between consecutive games is applied by the parent
 * (Reel.tsx) via a clip-path reveal on each Series.Sequence.
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
import {FONTS, LIGHT, PADDING, type GameSlate} from '../theme';
import {Footer, Hairline, Mono, TopRow} from '../components';

const P = LIGHT;

export type GameProps = {
  game: GameSlate;
  /** 1-based index of this game. */
  index: number;
  /** Total number of games (for "Game k / N" and pager dots). */
  total: number;
};

const fade = (frame: number, start: number, len = 15) =>
  interpolate(frame, [start, start + len], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

/** N pager dots; the active one is the accent colour. */
const Pager: React.FC<{total: number; active: number}> = ({total, active}) => (
  <div style={{display: 'flex', gap: 12, alignItems: 'center'}}>
    {Array.from({length: total}).map((_, i) => (
      <div
        key={i}
        style={{
          width: i === active ? 26 : 10,
          height: 10,
          borderRadius: 5,
          backgroundColor: i === active ? P.accent : P.hairline,
        }}
      />
    ))}
  </div>
);

/** One team row: [20px side dot] [Fraunces name] [Fraunces score]. */
const TeamRow: React.FC<{
  name: string;
  score: number;
  isWinner: boolean;
}> = ({name, score, isWinner}) => (
  <div style={{display: 'flex', alignItems: 'center'}}>
    <div
      style={{
        width: 20,
        height: 20,
        borderRadius: 10,
        marginRight: 28,
        flexShrink: 0,
        backgroundColor: isWinner ? P.accent : P.muted,
      }}
    />
    <div
      style={{
        flex: 1,
        fontFamily: FONTS.serif,
        fontWeight: isWinner ? 700 : 400,
        fontSize: 88,
        lineHeight: 1,
        color: P.ink,
        letterSpacing: -1,
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap',
      }}
    >
      {name}
    </div>
    <div
      style={{
        fontFamily: FONTS.serif,
        fontWeight: 700,
        fontSize: 150,
        lineHeight: 1,
        fontVariantNumeric: 'tabular-nums',
        color: isWinner ? P.accent : P.ink,
        marginLeft: 24,
      }}
    >
      {score}
    </div>
  </div>
);

export const Game: React.FC<GameProps> = ({game, index, total}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  const homeWins = game.winnerSide === 'home';
  const winnerShort = homeWins ? game.homeShort : game.awayShort;

  // Scores count up 0 → final over ~40f with an ease-out curve.
  const countProgress = interpolate(frame, [8, 48], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.out(Easing.cubic),
  });
  const homeScore = Math.round(game.homeScore * countProgress);
  const awayScore = Math.round(game.awayScore * countProgress);

  // Confidence bar fills 0 → confidence% via spring.
  const barS = spring({frame: frame - 30, fps, config: {damping: 200}});
  const confPct = Math.max(0, Math.min(100, game.confidence));
  const barWidth = interpolate(barS, [0, 1], [0, confPct]);
  const shownPct = Math.round(interpolate(barS, [0, 1], [0, confPct]));

  // Verdict + reason fade/slide in.
  const verdictS = spring({frame: frame - 22, fps, config: {damping: 200}});
  const verdictStyle: React.CSSProperties = {
    opacity: verdictS,
    transform: `translateY(${interpolate(verdictS, [0, 1], [24, 0])}px)`,
  };
  const reasonOpacity = fade(frame, 42, 16);

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
        {/* Top row: wordmark + "Game k / N" */}
        <TopRow palette={P} wordmarkColor={P.ink} right={`Game ${index} / ${total}`} />

        {/* Pager dots */}
        <div style={{marginTop: 34}}>
          <Pager total={total} active={index - 1} />
        </div>

        {/* Lead: "{HOME CITY} · {AWAY CITY}" */}
        <div style={{marginTop: 40}}>
          <Mono color={P.muted} size={24} spacing={8}>
            {game.homeCity} · {game.awayCity}
          </Mono>
        </div>

        {/* Game block bounded by hairlines */}
        <div style={{marginTop: 40}}>
          <Hairline color={P.hairline} />
          <div style={{padding: '36px 0', display: 'flex', flexDirection: 'column', gap: 24}}>
            <TeamRow name={game.homeName} score={homeScore} isWinner={homeWins} />
            <TeamRow name={game.awayName} score={awayScore} isWinner={!homeWins} />
          </div>
          <Hairline color={P.hairline} />
        </div>

        {/* Verdict */}
        <div
          style={{
            marginTop: 46,
            fontFamily: FONTS.serif,
            fontWeight: 400,
            fontSize: 60,
            lineHeight: 1.15,
            color: P.ink,
            ...verdictStyle,
          }}
        >
          Our model calls the{' '}
          <b style={{fontWeight: 700, color: P.accent}}>{winnerShort}</b>.
        </div>

        {/* Confidence row */}
        <div style={{marginTop: 40, opacity: fade(frame, 30, 12)}}>
          <div style={{display: 'flex', alignItems: 'center', gap: 20}}>
            <Mono color={P.muted} size={22} spacing={6} style={{flexShrink: 0}}>
              Confidence
            </Mono>
            <div
              style={{
                flex: 1,
                height: 14,
                borderRadius: 7,
                backgroundColor: P.hairline,
                overflow: 'hidden',
              }}
            >
              <div
                style={{
                  width: `${barWidth}%`,
                  height: '100%',
                  borderRadius: 7,
                  backgroundColor: P.accent,
                }}
              />
            </div>
            <span
              style={{
                fontFamily: FONTS.mono,
                fontWeight: 600,
                fontSize: 40,
                color: P.ink,
                fontVariantNumeric: 'tabular-nums',
                flexShrink: 0,
                minWidth: 96,
                textAlign: 'right',
              }}
            >
              {shownPct}%
            </span>
          </div>
        </div>

        {/* Flex spacer keeps the reason anchored above the footer */}
        <div style={{flex: 1}} />

        {/* Reason: Fraunces italic, muted */}
        <div
          style={{
            fontFamily: FONTS.serifItalic,
            fontStyle: 'italic',
            fontWeight: 400,
            fontSize: 44,
            lineHeight: 1.3,
            color: P.muted,
            maxWidth: 860,
            opacity: reasonOpacity,
          }}
        >
          {game.reasoning}
        </div>

        {/* Footer */}
        <div style={{marginTop: 40}}>
          <Footer palette={P} left="@playthechalk" right="100% algorithmic · no odds" />
        </div>
      </div>
    </AbsoluteFill>
  );
};
