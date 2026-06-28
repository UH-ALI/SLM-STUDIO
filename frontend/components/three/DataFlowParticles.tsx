'use client';

import { Suspense, useRef, useMemo, useState, useEffect } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { Points } from '@react-three/drei';
import * as THREE from 'three';

function Particles() {
  const pointsRef = useRef<THREE.Points>(null);

  const positions = useMemo(() => {
    const count = 60;
    const pos = new Float32Array(count * 3);

    for (let i = 0; i < count; i++) {
      pos[i * 3] = (Math.random() - 0.5) * 20;
      pos[i * 3 + 1] = (Math.random() - 0.5) * 10;
      pos[i * 3 + 2] = (Math.random() - 0.5) * 5;
    }

    return pos;
  }, []);

  useFrame(({ clock }) => {
    if (!pointsRef.current) return;

    const geo = pointsRef.current.geometry;
    const posAttr = geo.attributes.position;
    const t = clock.getElapsedTime();

    for (let i = 0; i < 60; i++) {
      const idx = i * 3;
      // Flow left to right with sine wave
      posAttr.array[idx] += 0.01;
      posAttr.array[idx + 1] += Math.sin(t * 0.5 + i * 0.2) * 0.002;

      // Wrap around
      if (posAttr.array[idx] > 10) {
        posAttr.array[idx] = -10;
      }
    }

    posAttr.needsUpdate = true;
  });

  return (
    <Points ref={pointsRef} positions={positions}>
      <pointsMaterial
        color="#D4A853"
        size={0.06}
        transparent
        opacity={0.7}
        blending={THREE.AdditiveBlending}
        depthWrite={false}
      />
    </Points>
  );
}

function Scene() {
  return (
    <>
      <ambientLight intensity={0.5} />
      <Particles />
    </>
  );
}

function CSSFallback() {
  return (
    <div className="absolute inset-0 overflow-hidden opacity-30">
      {Array.from({ length: 20 }, (_, i) => (
        <div
          key={i}
          className="absolute w-1 h-1 rounded-full bg-gold animate-pulse"
          style={{
            left: `${Math.random() * 100}%`,
            top: `${Math.random() * 100}%`,
            animationDelay: `${Math.random() * 3}s`,
            animationDuration: `${2 + Math.random() * 3}s`,
          }}
        />
      ))}
    </div>
  );
}

interface DataFlowParticlesProps {
  className?: string;
}

export function DataFlowParticles({ className }: DataFlowParticlesProps) {
  const [webglFailed, setWebglFailed] = useState(false);

  useEffect(() => {
    try {
      const canvas = document.createElement('canvas');
      const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
      if (!gl) setWebglFailed(true);
    } catch {
      setWebglFailed(true);
    }
  }, []);

  if (webglFailed) {
    return <CSSFallback />;
  }

  return (
    <div className={className}>
      <CSSFallback />
      <Suspense fallback={null}>
        <Canvas
          camera={{ position: [0, 0, 10], fov: 50 }}
          style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%' }}
          gl={{ alpha: true, antialias: true }}
          onError={() => setWebglFailed(true)}
        >
          <Scene />
        </Canvas>
      </Suspense>
    </div>
  );
}
