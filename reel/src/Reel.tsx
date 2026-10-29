/**
 * Master composition: Intro → Game×N → Outro, chained with <Series>.
 *
 * Between consecutive GAME frames we play a clean horizontal WIPE: each game
 * after the first starts a few frames early (negative offset) so it overlaps
 * its predecessor, and a clip-path reveal sweeps it in from the left. The
 * previous game stays visible underneath during the sweep.
 */
import React from 'react';
import {Easing, interpolate, Series, useCurrentFrame} from 'remotion';
import {DURATION, type ReelProps} from './theme';
import {Intro} from './frames/Intro';
import {Game} from './frames/Game';
import {Outro} from './frames/Outro';

/**
 * Wraps a game frame in a left-to-right clip-path reveal for the first
 * `WIPE` frames of its sequence. `enabled=false` (the first game) renders with
 * no wipe.
 */
const WipeIn: React.FC<{enabled: boolean; children: React.ReactNode}> = ({
  enabled,
  children,
}) => {
  const frame = useCurrentFrame();
  if (!enabled) {
    return <>{children}</>;
  }
  // inset() right edge animates 100% → 0% over the wipe window.
  const rightInset = interpolate(frame, [0, DURATION.wipe], [100, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.inOut(Easing.cubic),
  });
  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        clipPath: `inset(0 ${rightInset}% 0 0)`,
      }}
    >
      {children}
    </div>
  );
};

export const Reel: React.FC<ReelProps> = ({date, trackRecord, yesterday, slate}) => {
  const total = slate.length;

  return (
    <Series>
      {/* INTRO */}
      <Series.Sequence durationInFrames={DURATION.intro}>
        <Intro date={date} slate={slate} trackRecord={trackRecord} />
      </Series.Sequence>

      {/* GAME × N, each after the first overlaps the previous for the wipe. */}
      {slate.map((game, i) => (
        <Series.Sequence
          key={i}
          durationInFrames={DURATION.game}
          offset={i === 0 ? 0 : -DURATION.wipe}
        >
          <WipeIn enabled={i > 0}>
            <Game game={game} index={i + 1} total={total} />
          </WipeIn>
        </Series.Sequence>
      ))}

      {/* OUTRO */}
      <Series.Sequence durationInFrames={DURATION.outro}>
        <Outro yesterday={yesterday} trackRecord={trackRecord} />
      </Series.Sequence>
    </Series>
  );
};

/**
 * Total frames for a given slate length. Kept here so both the composition and
 * calculateMetadata() agree. Games after the first overlap by DURATION.wipe.
 */
export const totalDurationInFrames = (nGames: number): number =>
  DURATION.intro +
  DURATION.game * nGames -
  DURATION.wipe * Math.max(0, nGames - 1) +
  DURATION.outro;
