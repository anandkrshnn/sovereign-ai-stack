import React from 'react';
import { Composition, registerRoot } from 'remotion';
import { WalkthroughComposition } from './WalkthroughComposition';

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="SovereignAirlockExplainer"
        component={WalkthroughComposition}
        durationInFrames={1800} // 60 seconds at 30fps
        fps={30}
        width={1920}
        height={1080}
      />
    </>
  );
};

registerRoot(RemotionRoot);
