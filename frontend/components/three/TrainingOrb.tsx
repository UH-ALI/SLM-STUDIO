"use client";

import { useRef, useEffect, useState } from "react";

type TrainingStatus =
  | "idle"
  | "training"
  | "converged"
  | "failed"
  | "pending"
  | "processing"
  | "completed";

const STATUS_CONFIG = {
  idle: {
    primary: "#D4A853",
    secondary: "#8B6914",
    glow: "rgba(212,168,83,0.6)",
    label: "Idle",
  },
  pending: {
    primary: "#D4A853",
    secondary: "#8B6914",
    glow: "rgba(212,168,83,0.6)",
    label: "Pending",
  },
  processing: {
    primary: "#5EEAD4",
    secondary: "#0D9488",
    glow: "rgba(94,234,212,0.7)",
    label: "Training",
  },
  training: {
    primary: "#5EEAD4",
    secondary: "#0D9488",
    glow: "rgba(94,234,212,0.7)",
    label: "Training",
  },
  completed: {
    primary: "#7FB069",
    secondary: "#3D6B30",
    glow: "rgba(127,176,105,0.6)",
    label: "Converged",
  },
  converged: {
    primary: "#7FB069",
    secondary: "#3D6B30",
    glow: "rgba(127,176,105,0.6)",
    label: "Converged",
  },
  failed: {
    primary: "#E05C5C",
    secondary: "#7F1D1D",
    glow: "rgba(224,92,92,0.6)",
    label: "Failed",
  },
};

interface TrainingOrbProps {
  trainingStatus: TrainingStatus;
  className?: string;
}

export function TrainingOrb({ trainingStatus, className }: TrainingOrbProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animRef = useRef<number>(0);
  const timeRef = useRef(0);
  const [size, setSize] = useState(280);

  const status = STATUS_CONFIG[trainingStatus] ?? STATUS_CONFIG.idle;
  const isActive =
    trainingStatus === "processing" || trainingStatus === "training";

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const draw = (timestamp: number) => {
      timeRef.current = timestamp / 1000;
      const t = timeRef.current;
      const w = canvas.width;
      const h = canvas.height;
      const cx = w / 2;
      const cy = h / 2;
      const R = Math.min(w, h) * 0.32;

      ctx.clearRect(0, 0, w, h);

      // Outer glow rings
      for (let i = 3; i >= 1; i--) {
        const ringR = R + i * 22 + (isActive ? Math.sin(t * 2 + i) * 6 : 0);
        const grad = ctx.createRadialGradient(
          cx,
          cy,
          ringR * 0.7,
          cx,
          cy,
          ringR + 10,
        );
        const glowAlpha = Math.round((0.12 / i) * 255)
          .toString(16)
          .padStart(2, "0");
        grad.addColorStop(0, status.primary + glowAlpha);
        grad.addColorStop(1, "transparent");
        ctx.beginPath();
        ctx.arc(cx, cy, ringR, 0, Math.PI * 2);
        ctx.fillStyle = grad;
        ctx.fill();
      }

      // Rotating orbit rings
      const numRings = 3;
      for (let r = 0; r < numRings; r++) {
        const angle = t * (0.3 + r * 0.15) + (r * Math.PI * 2) / numRings;
        const rx = R * (1.5 + r * 0.25);
        const ry = rx * 0.3;
        ctx.save();
        ctx.translate(cx, cy);
        ctx.rotate(angle);
        ctx.beginPath();
        ctx.ellipse(0, 0, rx, ry, 0, 0, Math.PI * 2);
        ctx.strokeStyle =
          status.primary + (r === 0 ? "60" : r === 1 ? "40" : "25");
        ctx.lineWidth = 1.5 - r * 0.3;
        ctx.stroke();
        ctx.restore();

        // Dot on ring
        ctx.save();
        ctx.translate(cx, cy);
        ctx.rotate(angle);
        const dotX = rx;
        const dotY = 0;
        ctx.beginPath();
        ctx.arc(dotX, dotY, 3 - r * 0.5, 0, Math.PI * 2);
        ctx.fillStyle = status.primary;
        ctx.shadowColor = status.primary;
        ctx.shadowBlur = 10;
        ctx.fill();
        ctx.restore();
      }

      // Main orb — deep sphere with gradient
      const sphereGrad = ctx.createRadialGradient(
        cx - R * 0.3,
        cy - R * 0.3,
        R * 0.05,
        cx,
        cy,
        R,
      );
      sphereGrad.addColorStop(0, "#ffffff40");
      sphereGrad.addColorStop(0.2, status.primary + "CC");
      sphereGrad.addColorStop(0.6, status.secondary + "AA");
      sphereGrad.addColorStop(1, "#00000088");
      ctx.beginPath();
      ctx.arc(cx, cy, R, 0, Math.PI * 2);
      ctx.fillStyle = sphereGrad;
      ctx.shadowColor = status.primary;
      ctx.shadowBlur = isActive ? 40 + Math.sin(t * 3) * 15 : 25;
      ctx.fill();
      ctx.shadowBlur = 0;

      // Inner core glow
      const coreGrad = ctx.createRadialGradient(cx, cy, 0, cx, cy, R * 0.55);
      coreGrad.addColorStop(0, "#ffffff30");
      coreGrad.addColorStop(0.5, status.primary + "20");
      coreGrad.addColorStop(1, "transparent");
      ctx.beginPath();
      ctx.arc(cx, cy, R * 0.55, 0, Math.PI * 2);
      ctx.fillStyle = coreGrad;
      ctx.fill();

      // Specular highlight
      const specGrad = ctx.createRadialGradient(
        cx - R * 0.28,
        cy - R * 0.28,
        0,
        cx - R * 0.28,
        cy - R * 0.28,
        R * 0.45,
      );
      specGrad.addColorStop(0, "rgba(255,255,255,0.45)");
      specGrad.addColorStop(0.5, "rgba(255,255,255,0.08)");
      specGrad.addColorStop(1, "transparent");
      ctx.beginPath();
      ctx.arc(cx, cy, R, 0, Math.PI * 2);
      ctx.fillStyle = specGrad;
      ctx.fill();

      // Animated particles when active
      if (isActive) {
        const numParticles = 12;
        for (let p = 0; p < numParticles; p++) {
          const angle = (p / numParticles) * Math.PI * 2 + t * 0.8;
          const dist = R * (1.1 + 0.4 * Math.sin(t * 1.5 + p * 0.8));
          const px = cx + Math.cos(angle) * dist;
          const py = cy + Math.sin(angle) * dist * 0.5;
          const alpha = 0.3 + 0.5 * Math.abs(Math.sin(t * 2 + p));
          ctx.beginPath();
          ctx.arc(px, py, 2.5, 0, Math.PI * 2);
          ctx.fillStyle =
            status.primary +
            Math.round(alpha * 255)
              .toString(16)
              .padStart(2, "0");
          ctx.shadowColor = status.primary;
          ctx.shadowBlur = 8;
          ctx.fill();
          ctx.shadowBlur = 0;
        }
      }

      // Pulse ring when active
      if (isActive) {
        const pulseR = R * (1.1 + ((t * 0.5) % 1) * 0.8);
        const pulseAlpha = 1 - ((t * 0.5) % 1);
        ctx.beginPath();
        ctx.arc(cx, cy, pulseR, 0, Math.PI * 2);
        ctx.strokeStyle =
          status.primary +
          Math.round(pulseAlpha * 120)
            .toString(16)
            .padStart(2, "0");
        ctx.lineWidth = 2;
        ctx.stroke();
      }

      animRef.current = requestAnimationFrame(draw);
    };

    animRef.current = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(animRef.current);
  }, [trainingStatus, isActive, status]);

  useEffect(() => {
    const el = canvasRef.current?.parentElement;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => {
      setSize(Math.min(entry.contentRect.width, 320));
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  return (
    <div
      className={className}
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <canvas
        ref={canvasRef}
        width={size}
        height={size}
        style={{ width: size, height: size }}
      />
    </div>
  );
}
