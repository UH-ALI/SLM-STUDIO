"use client";

import { useRef, useEffect } from "react";
import type { Metrics } from "@/types/project";

interface TrainingGraphProps {
  data: Metrics[];
  className?: string;
}

export function TrainingGraph({ data, className }: TrainingGraphProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || data.length === 0) return;
    const c = canvas.getContext("2d");
    if (!c) return;

    const W = canvas.width;
    const H = canvas.height;
    const PAD = { top: 32, right: 32, bottom: 44, left: 48 };
    const plotW = W - PAD.left - PAD.right;
    const plotH = H - PAD.top - PAD.bottom;

    c.clearRect(0, 0, W, H);

    // Dark background
    c.fillStyle = "#0E1812";
    c.beginPath();
    c.roundRect(0, 0, W, H, 16);
    c.fill();

    const trainLoss = data.map((d) => d.trainLoss);
    const valLoss = data.map((d) => d.valLoss);
    const perp = data.map((d) => d.perplexity);
    const gpu = data.map((d) => d.gpuUtil);

    // Normalize each series to 0–1 range so they all fill the same height
    const normalize = (arr: number[]) => {
      const min = Math.min(...arr);
      const max = Math.max(...arr);
      return arr.map((v) => (max === min ? 0.5 : (v - min) / (max - min)));
    };

    const nTrain = normalize(trainLoss);
    const nVal = normalize(valLoss);
    const nPerp = normalize(perp);
    const nGpu = normalize(gpu);

    const xPos = (i: number) => PAD.left + (i / (data.length - 1)) * plotW;
    // Inverted: high normalized value = tall peak from bottom
    const yPos = (v: number) => PAD.top + plotH - v * plotH;

    // Subtle grid
    for (let g = 0; g <= 4; g++) {
      const y = PAD.top + (g / 4) * plotH;
      c.beginPath();
      c.moveTo(PAD.left, y);
      c.lineTo(PAD.left + plotW, y);
      c.strokeStyle = "rgba(255,255,255,0.04)";
      c.lineWidth = 1;
      c.stroke();
    }

    // X axis labels
    const step = Math.ceil(data.length / 8);
    data.forEach((d, i) => {
      if (i % step === 0 || i === data.length - 1) {
        c.fillStyle = "#4A5D52";
        c.font = "10px Inter, sans-serif";
        c.textAlign = "center";
        c.fillText(`Epoch ${d.epoch}`, xPos(i), H - 10);
      }
    });

    // Draw filled area — NO border line, pure fill only
    function drawFill(values: number[], color: string, alpha: number) {
      if (values.length < 2) return;

      const grad = c!.createLinearGradient(0, PAD.top, 0, PAD.top + plotH);
      grad.addColorStop(
        0,
        color.replace(")", `, ${alpha})`).replace("rgb", "rgba"),
      );
      grad.addColorStop(
        1,
        color.replace(")", ", 0.02)").replace("rgb", "rgba"),
      );

      c!.beginPath();
      c!.moveTo(xPos(0), PAD.top + plotH);
      c!.lineTo(xPos(0), yPos(values[0]));

      for (let i = 1; i < values.length; i++) {
        const x0 = xPos(i - 1),
          y0 = yPos(values[i - 1]);
        const x1 = xPos(i),
          y1 = yPos(values[i]);
        const cpx = (x0 + x1) / 2;
        c!.bezierCurveTo(cpx, y0, cpx, y1, x1, y1);
      }

      c!.lineTo(xPos(values.length - 1), PAD.top + plotH);
      c!.closePath();
      c!.fillStyle = grad;
      c!.fill();
    }

    // Draw back to front — GPU first (widest/tallest), then others on top
    // Colors match site palette, soft pastels like reference
    drawFill(nGpu, "rgb(233, 163, 25)", 0.3); // amber  — GPU
    drawFill(nPerp, "rgb(94, 234, 212)", 0.35); // mint   — Perplexity
    drawFill(nVal, "rgb(127, 176, 105)", 0.4); // sage   — Val Loss
    drawFill(nTrain, "rgb(212, 168, 83)", 0.55); // gold   — Train Loss (front)

    // Legend — small color swatches, no lines
    const legend = [
      { label: "Train Loss", color: "#D4A853" },
      { label: "Val Loss", color: "#7FB069" },
      { label: "Perplexity", color: "#5EEAD4" },
      { label: "GPU Util %", color: "#E9A319" },
    ];
    let lx = PAD.left;
    const ly = 14;
    legend.forEach(({ label, color }) => {
      // Small filled rounded rect swatch
      c.fillStyle = color + "99";
      c.beginPath();
      c.roundRect(lx, ly - 7, 14, 8, 3);
      c.fill();
      c.fillStyle = "#8A9B8E";
      c.font = "10px Inter, sans-serif";
      c.textAlign = "left";
      c.fillText(label, lx + 18, ly);
      lx += c.measureText(label).width + 38;
    });
  }, [data]);

  if (data.length === 0) {
    return (
      <div className={`flex items-center justify-center h-64 ${className}`}>
        <p className="text-sm text-muted">No training data available</p>
      </div>
    );
  }

  return (
    <div className={className}>
      <canvas
        ref={canvasRef}
        width={900}
        height={320}
        style={{ width: "100%", height: "320px", borderRadius: "12px" }}
      />
    </div>
  );
}
