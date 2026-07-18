'use client';

import { Suspense, useState, useEffect } from 'react';
import { Canvas } from '@react-three/fiber';
import { Float, MeshDistortMaterial } from '@react-three/drei';

function Blob({
  color,
  position,
  scale,
  speed,
}: {
  color: string;
  position: [number, number, number];
  scale: number;
  speed: number;
}) {
  return (
    <Float speed={speed} rotationIntensity={0.4} floatIntensity={0.6}>
      <mesh position={position} scale={scale}>
        <sphereGeometry args={[1, 32, 32]} />
        <MeshDistortMaterial
          color={color}
          distort={0.4}
          speed={2}
          roughness={0.2}
          metalness={0.8}
          transparent
          opacity={0.6}
        />
      </mesh>
    </Float>
  );
}

function Scene() {
  return (
    <>
      <ambientLight intensity={0.4} />
      <pointLight position={[10, 10, 10]} intensity={0.8} />
      <pointLight position={[-10, -10, -10]} intensity={0.3} color="#7FB069" />

      <Blob color="#D4A853" position={[-3, 1, -2]} scale={1.8} speed={1.5} />
      <Blob color="#7FB069" position={[3, -1, -3]} scale={1.4} speed={2} />
      <Blob color="#5EEAD4" position={[0, 2, -4]} scale={1.2} speed={1.8} />
    </>
  );
}

function CSSFallback() {
  return (
    <div className="absolute inset-0 overflow-hidden">
      <div
        className="absolute w-[320px] h-[320px] sm:w-[500px] sm:h-[500px] rounded-full opacity-20 animate-drift"
        style={{
          background: 'radial-gradient(circle, #D4A853, transparent 70%)',
          top: '10%',
          left: '20%',
          filter: 'blur(60px)',
        }}
      />
      <div
        className="absolute w-[260px] h-[260px] sm:w-[400px] sm:h-[400px] rounded-full opacity-15 animate-drift-slow"
        style={{
          background: 'radial-gradient(circle, #7FB069, transparent 70%)',
          top: '50%',
          right: '10%',
          filter: 'blur(60px)',
        }}
      />
      <div
        className="absolute w-[220px] h-[220px] sm:w-[350px] sm:h-[350px] rounded-full opacity-15 animate-drift-fast"
        style={{
          background: 'radial-gradient(circle, #5EEAD4, transparent 70%)',
          bottom: '20%',
          left: '40%',
          filter: 'blur(60px)',
        }}
      />
    </div>
  );
}

export function HeroBackground() {
  const [webglFailed, setWebglFailed] = useState(false);

  useEffect(() => {
    try {
      const canvas = document.createElement('canvas');
      const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
      if (!gl) {
        setWebglFailed(true);
      }
    } catch {
      setWebglFailed(true);
    }
  }, []);

  if (webglFailed) {
    return <CSSFallback />;
  }

  return (
    <div className="absolute inset-0">
      <CSSFallback />
      <Suspense fallback={null}>
        <Canvas
          camera={{ position: [0, 0, 8], fov: 45 }}
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
