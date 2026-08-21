// Remotion CLI config. Applies to `remotion studio`, `remotion render` and
// `remotion still`. See https://www.remotion.dev/docs/config
import {Config} from '@remotion/cli/config';

// The reel is a vertical 9:16 social video. H.264 MP4 is the universally
// postable format for IG/TikTok/Shorts.
Config.setVideoImageFormat('jpeg');
Config.setPixelFormat('yuv420p');
Config.setCodec('h264');

// Crisp text: full-quality JPEG frames feeding the encoder.
Config.setJpegQuality(100);

// Always overwrite the previous export so the daily job is idempotent.
Config.setOverwriteOutput(true);

// The entry point that calls registerRoot().
Config.setEntryPoint('./src/index.ts');
