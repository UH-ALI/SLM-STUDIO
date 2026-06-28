"use client";

import { useEffect } from "react";
import { useParams } from "next/navigation";
import { TrainingPanel } from "@/components/organisms/TrainingPanel";
import { LogPanel } from "@/components/organisms/LogPanel";
import { GraphPanel } from "@/components/organisms/GraphPanel";
import { ErrorPanel } from "@/components/organisms/ErrorPanel";
import { LoadingBuffer } from "@/components/organisms/LoadingBuffer";
import { useJob } from "@/hooks/useJobs";
import { useTrainingStore } from "@/stores/trainingStore";
import { useUIStore } from "@/stores/uiStore";

interface TrainingLayoutProps {
  children?: React.ReactNode;
}

export function TrainingLayout({ children }: TrainingLayoutProps) {
  const params = useParams();
  const jobId = params.id as string;
  const { data: job, isLoading } = useJob(jobId);
  const {
    status,
    metrics,
    logs,
    progress,
    epoch,
    history,
    setStatus,
    updateMetrics,
    setLogs,
    setProgress,
    setEpoch,
  } = useTrainingStore();
  const { addToast } = useUIStore();

  // Sync job data to training store
  useEffect(() => {
    if (job) {
      const jobStatus = job.status || "pending";
      setStatus(
        jobStatus === "processing"
          ? "processing"
          : jobStatus === "training"
            ? "training"
            : jobStatus === "completed"
              ? "completed"
              : jobStatus === "failed"
                ? "failed"
                : "pending",
      );
      setProgress(job.progress || 0);
      setEpoch(job.epoch || 0);
      if (job.metrics) {
        updateMetrics(job.metrics);
      }
      // Bug 4 fix: replace logs in bulk instead of appending duplicates
      if (job.logs && job.logs.length > 0) {
        setLogs(job.logs);
      }
    }
  }, [job]);

  if (isLoading) {
    return <LoadingBuffer />;
  }

  return (
    <div className="space-y-6">
      {/* Main panels */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* Left: Training Panel */}
        <div className="lg:col-span-3">
          <TrainingPanel
            status={status}
            metrics={metrics}
            progress={progress}
            epoch={epoch}
          />
        </div>

        {/* Right: Log Panel */}
        <div className="lg:col-span-2">
          <LogPanel logs={logs} status={status} />
        </div>
      </div>

      {/* Bottom: Graph or Error */}
      {status === "completed" && history.length > 0 && (
        <>
          <GraphPanel data={history} />

          <div className="glass-card flex flex-col sm:flex-row items-center justify-between gap-4">
            <div>
              <h3 className="text-sm font-semibold text-ivory">
                Training Complete
              </h3>
              <p className="text-xs text-fern mt-1">
                Your model is ready — test it in the Playground.
              </p>
            </div>

            <a
              href={`/projects/${jobId}/playground`}
              className="shrink-0 px-5 py-2.5 rounded-xl bg-gold text-void text-sm font-semibold hover:bg-amber transition-colors"
            >
              Open Playground →
            </a>
          </div>
        </>
      )}

      {status === "failed" && (
        <ErrorPanel
          errorMessage={job?.errorMessage || "Training failed"}
          onRetry={() => {
            // Retry logic
            addToast({ type: "info", message: "Retrying training..." });
          }}
        />
      )}

      {children}
    </div>
  );
}
