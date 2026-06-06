import React from 'react';
import { AbsoluteFill, Sequence, spring, useCurrentFrame, useVideoConfig, interpolate } from 'remotion';

export const WalkthroughComposition: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Basic styling setup
  const bgStyle: React.CSSProperties = {
    backgroundColor: '#0A0A0A',
    color: '#E0E0E0',
    fontFamily: 'Inter, sans-serif',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    textAlign: 'center',
  };

  // Phase 1: Intro (0-4 seconds)
  const introOpacity = interpolate(frame, [0, 15, 100, 120], [0, 1, 1, 0], { extrapolateRight: 'clamp' });
  const introScale = spring({ frame, fps, config: { damping: 12 } });

  // Phase 2: Hardware Attestation (4-15 seconds)
  const tpmOpacity = interpolate(frame, [120, 135, 420, 450], [0, 1, 1, 0], { extrapolateRight: 'clamp' });
  
  // Phase 3: NLI Grounding (15-25 seconds)
  const nliOpacity = interpolate(frame, [450, 465, 720, 750], [0, 1, 1, 0], { extrapolateRight: 'clamp' });
  
  // Phase 4: Merkle Logging (25-35 seconds)
  const merkleOpacity = interpolate(frame, [750, 765, 1020, 1050], [0, 1, 1, 0], { extrapolateRight: 'clamp' });

  // Phase 5: Outro (35-60 seconds)
  const outroOpacity = interpolate(frame, [1050, 1080], [0, 1], { extrapolateLeft: 'clamp' });

  return (
    <AbsoluteFill style={bgStyle}>
      {/* Abstract Background Elements */}
      <div style={{ position: 'absolute', width: '100%', height: '100%', opacity: 0.05, backgroundImage: 'radial-gradient(circle, #FFFFFF 1px, transparent 1px)', backgroundSize: '20px 20px' }} />

      {/* Intro */}
      <Sequence from={0} durationInFrames={120}>
        <AbsoluteFill style={{ ...bgStyle, opacity: introOpacity }}>
          <h1 style={{ fontSize: '80px', margin: 0, transform: `scale(${introScale})`, color: '#FFFFFF' }}>
            The Sovereign AI Stack
          </h1>
          <h2 style={{ fontSize: '40px', fontWeight: 'normal', color: '#888888', marginTop: '20px' }}>
            Verify-First Airlock Architecture
          </h2>
        </AbsoluteFill>
      </Sequence>

      {/* Stage 1: Hardware Attestation */}
      <Sequence from={120} durationInFrames={330}>
        <AbsoluteFill style={{ ...bgStyle, opacity: tpmOpacity }}>
          <div style={{ fontSize: '100px' }}>🔐</div>
          <h1 style={{ fontSize: '60px', color: '#FFFFFF' }}>Stage 1: Hardware Trust</h1>
          <p style={{ fontSize: '32px', width: '60%', color: '#AAAAAA' }}>
            TPM 2.0 validates the enclave state before the gateway boots. Keys never touch system memory.
          </p>
        </AbsoluteFill>
      </Sequence>

      {/* Stage 2: NLI Gate */}
      <Sequence from={450} durationInFrames={300}>
        <AbsoluteFill style={{ ...bgStyle, opacity: nliOpacity }}>
          <div style={{ fontSize: '100px' }}>🧠</div>
          <h1 style={{ fontSize: '60px', color: '#FFFFFF' }}>Stage 2: NLI Grounding Gate</h1>
          <p style={{ fontSize: '32px', width: '60%', color: '#AAAAAA' }}>
            Mathematical entailment scoring. If hallucination risk is detected (score &lt; 0.85), the pipeline strictly fails closed.
          </p>
        </AbsoluteFill>
      </Sequence>

      {/* Stage 3: Merkle Audit */}
      <Sequence from={750} durationInFrames={300}>
        <AbsoluteFill style={{ ...bgStyle, opacity: merkleOpacity }}>
          <div style={{ fontSize: '100px' }}>🌳</div>
          <h1 style={{ fontSize: '60px', color: '#FFFFFF' }}>Stage 3: Merkle Audit Chain</h1>
          <p style={{ fontSize: '32px', width: '60%', color: '#AAAAAA' }}>
            O(1) tamper-evident cryptographic logging. Defensible audit trails for regulatory compliance.
          </p>
        </AbsoluteFill>
      </Sequence>

      {/* Outro */}
      <Sequence from={1050}>
        <AbsoluteFill style={{ ...bgStyle, opacity: outroOpacity }}>
          <h1 style={{ fontSize: '80px', color: '#FFFFFF', marginBottom: '20px' }}>
            Fail-Closed is the Only Acceptable State.
          </h1>
          <p style={{ fontSize: '40px', color: '#FF6B6B', fontWeight: 'bold' }}>
            End Security Theater.
          </p>
        </AbsoluteFill>
      </Sequence>
    </AbsoluteFill>
  );
};
