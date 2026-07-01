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

    // Extract series without turning nulls into 0
    // For valLoss, we'll carry forward the last known value to avoid spikes to 0
    const rawTrain = data.map((d) => d.trainLoss);
    const rawVal = data.map((d) => d.valLoss);
    const rawGpu = data.map((d) => d.gpuUtil);

    // Fill forward nulls for a continuous line
    const fillForward = (arr: (number | null | undefined)[]) => {
      let last = arr.find((v) => v != null) ?? 0;
      return arr.map((v) => {
        if (v != null) last = v;
        return last;
      });
    };

    const trainLoss = fillForward(rawTrain);
    const valLoss = fillForward(rawVal);
    const gpu = fillForward(rawGpu);

    // Calculate global bounds for Loss (shared between Train and Val)
    const validLosses = [...trainLoss, ...valLoss].filter((v) => v != null && !isNaN(v));
    const maxLoss = validLosses.length > 0 ? Math.max(...validLosses) * 1.1 : 1; // 10% headroom
    const minLoss = validLosses.length > 0 ? Math.max(0, Math.min(...validLosses) - 0.1) : 0;

    // GPU is fixed 0-100
    const maxGpu = 100;
    const minGpu = 0;

    const normalizeLoss = (arr: number[]) =>
      arr.map((v) => (maxLoss === minLoss ? 0.5 : (v - minLoss) / (maxLoss - minLoss)));
    const normalizeGpu = (arr: number[]) =>
      arr.map((v) => (v - minGpu) / (maxGpu - minGpu));

    const nTrain = normalizeLoss(trainLoss);
    const nVal = normalizeLoss(valLoss);
    const nGpu = normalizeGpu(gpu);

    const effectiveData = data.length === 1 ? [data[0], data[0]] : data;
    const effectiveNTrain = data.length === 1 ? [nTrain[0], nTrain[0]] : nTrain;
    const effectiveNVal = data.length === 1 ? [nVal[0], nVal[0]] : nVal;
    const effectiveNGpu = data.length === 1 ? [nGpu[0], nGpu[0]] : nGpu;

    const pointCount = effectiveData.length;

    const xPos = (i: number) =>
      PAD.left + (pointCount > 1 ? (i / (pointCount - 1)) * plotW : plotW / 2);
    // Inverted: high normalized value = tall peak from bottom
    const yPos = (v: number) => PAD.top + plotH - v * plotH;

    // Grid and Y-axis labels
    c.font = "10px Inter, sans-serif";
    for (let g = 0; g <= 4; g++) {
      const y = PAD.top + (g / 4) * plotH;
      c.beginPath();
      c.moveTo(PAD.left, y);
      c.lineTo(PAD.left + plotW, y);
      c.strokeStyle = "rgba(255,255,255,0.04)";
      c.lineWidth = 1;
      c.stroke();

      // Left Y-axis (Loss)
      const lossVal = maxLoss - (g / 4) * (maxLoss - minLoss);
      c.fillStyle = "#8A9B8E";
      c.textAlign = "right";
      c.fillText(lossVal.toFixed(2), PAD.left - 8, y + 4);

      // Right Y-axis (GPU)
      const gpuVal = maxGpu - (g / 4) * (maxGpu - minGpu);
      c.fillStyle = "#8A9B8E";
      c.textAlign = "left";
      c.fillText(`${Math.round(gpuVal)}%`, PAD.left + plotW + 8, y + 4);
    }

    // X axis labels
    const step = Math.max(1, Math.ceil(effectiveData.length / 8));
    effectiveData.forEach((d, i) => {
      if (i % step === 0 || i === effectiveData.length - 1) {
        c.fillStyle = "#4A5D52";
        c.textAlign = "center";
        c.fillText(`Epoch ${d.epoch}`, xPos(i), H - 10);
      }
    });

    // Draw filled area — pure soft gradients, no harsh lines
    function drawFill(values: number[], color: string, alpha: number) {
      if (values.length < 2) return;

      const grad = c!.createLinearGradient(0, PAD.top, 0, PAD.top + plotH);
      // We use globalCompositeOperation to make overlaps look luminous instead of muddy
      c!.globalCompositeOperation = "screen";

      grad.addColorStop(0, color.replace(")", `, ${alpha})`).replace("rgb", "rgba"));
      grad.addColorStop(1, color.replace(")", ", 0.02)").replace("rgb", "rgba"));

      c!.beginPath();
      c!.moveTo(xPos(0), PAD.top + plotH);
      c!.lineTo(xPos(0), yPos(values[0]));

      for (let i = 1; i < values.length; i++) {
        const x0 = xPos(i - 1), y0 = yPos(values[i - 1]);
        const x1 = xPos(i), y1 = yPos(values[i]);
        const cpx = (x0 + x1) / 2;
        c!.bezierCurveTo(cpx, y0, cpx, y1, x1, y1);
      }

      c!.lineTo(xPos(values.length - 1), PAD.top + plotH);
      c!.closePath();
      c!.fillStyle = grad;
      c!.fill();
      
      // Reset composite operation
      c!.globalCompositeOperation = "source-over";
    }

    // Draw back to front — GPU first, then Val Loss, then Train Loss
    drawFill(effectiveNGpu, "rgb(77, 208, 225)", 0.25); // GPU (Cyan - distinct color)
    drawFill(effectiveNVal, "rgb(127, 176, 105)", 0.35); // Val Loss (Sage)
    drawFill(effectiveNTrain, "rgb(212, 168, 83)", 0.45); // Train Loss (Gold)

    // Legend — small color swatches
    const legend = [
      { label: "Train Loss", color: "#D4A853" },
      { label: "Val Loss", color: "#7FB069" },
      { label: "GPU Util %", color: "#4DD0E1" },
    ];
    let lx = PAD.left;
    const ly = 14;
    legend.forEach(({ label, color }) => {
      // Small filled rounded rect swatch with glow
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
