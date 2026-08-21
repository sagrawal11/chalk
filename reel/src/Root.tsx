/**
 * Composition registry. The single <Composition id="Reel"> scales its
 * duration to the slate length via calculateMetadata, so the same comp renders
 * a 3-game or a 12-game slate with no config changes.
 */
import React from 'react';
import {CalculateMetadataFunction, Composition} from 'remotion';
import {CANVAS, waitForFonts, type ReelProps} from './theme';
import {Reel, totalDurationInFrames} from './Reel';
import sampleSlate from '../sample-slate.json';

const calculateMetadata: CalculateMetadataFunction<ReelProps> = async ({props}) => {
  // Block the render until webfonts are ready (first run needs network).
  await waitForFonts();
  const nGames = Array.isArray(props.slate) ? props.slate.length : 0;
  return {
    durationInFrames: totalDurationInFrames(nGames),
    fps: CANVAS.fps,
    width: CANVAS.width,
    height: CANVAS.height,
  };
};

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="Reel"
      component={Reel}
      // Placeholder; calculateMetadata computes the real duration from the slate.
      durationInFrames={totalDurationInFrames((sampleSlate as ReelProps).slate.length)}
      fps={CANVAS.fps}
      width={CANVAS.width}
      height={CANVAS.height}
      defaultProps={sampleSlate as ReelProps}
      calculateMetadata={calculateMetadata}
    />
  );
};
