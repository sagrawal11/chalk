/**
 * Remotion entry point. This is the file passed to `remotion render` /
 * `remotion studio` (also wired via Config.setEntryPoint in remotion.config.ts).
 */
import {registerRoot} from 'remotion';
import {RemotionRoot} from './Root';

registerRoot(RemotionRoot);
