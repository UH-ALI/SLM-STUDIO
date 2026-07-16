"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { AlertTriangle } from "lucide-react";
import { TrainingPanel } from "@/components/organisms/TrainingPanel";
import { LogPanel } from "@/components/organisms/LogPanel";
import { GraphPanel } from "@/components/organisms/GraphPanel";
import { ErrorPanel } from "@/components/organisms/ErrorPanel";
import { LoadingBuffer } from "@/components/organisms/LoadingBuffer";
import { WarningModal } from "@/components/organisms/WarningModal";
import { useProjectStatus } from "@/hooks/useJobs";
import { useTrainingStore } from "@/stores/trainingStore";
import { useProjectStore } from "@/stores/projectStore";
import { useUIStore } from "@/stores/uiStore";

interface TrainingLayoutProps {
  children?: React.ReactNode;
}

export function TrainingLayout({ children }: TrainingLayoutProps) {
  const params = useParams();
  const jobId = params.id as string;
  const queryClient = useQueryClient();
  const { data: job, isLoading } = useProjectStatus(jobId);
  const {
    status,
    metrics,
    logs,
    progress,
    epoch,
    history,
    setStatus,
    setLogs,
    setHistory,
    setProgress,
    setEpoch,
  } = useTrainingStore();
  const { addToast } = useUIStore();
  const { fetchProject, startTraining, cancelProject } = useProjectStore();

  const [showRetryModal, setShowRetryModal] = useState(false);
  const [retryProjectData, setRetryProjectData] = useState<any>(null);
  const [isCancelling, setIsCancelling] = useState(false);

  const handleCancel = async () => {
    setIsCancelling(true);
    try {
      await cancelProject(jobId);
      addToast({ type: "success", message: "Project cancelled and unlocked. You can retry or delete it." });
      queryClient.invalidateQueries({ queryKey: ['projectStatus', jobId] });
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      addToast({ type: "error", message: detail || "Failed to cancel project." });
    } finally {
      setIsCancelling(false);
    }
  };

  const executeRetry = async (useSafeDefaults: boolean) => {
    setShowRetryModal(false);
    if (!retryProjectData) return;
    
    try {
      addToast({ type: "info", message: "Retrying training..." });
      
      let hyperparameters = retryProjectData.hyperparameters || {};
      let temperature = retryProjectData.inferenceTemperature ?? hyperparameters.temperature ?? 0.3;

      if (useSafeDefaults) {
        hyperparameters = {
          batchSize: 1,
          maxSeqLen: 2048,
          epochs: 3,
          learningRate: 0.0002,
        };
      }

      // Clear local training store state so we don't show old logs/orbs while restarting
      const { reset } = useTrainingStore.getState();
      reset();

      await startTraining(jobId, {
        baseModelName: retryProjectData.baseModelName || "llama-3.2-1b",
        hyperparameters: {
          ...hyperparameters,
          temperature,
        }
      });
      
      // Optimistically set React Query cache to 'processing' so it doesn't flash the old failed state
      queryClient.setQueryData(['projectStatus', jobId], (old: any) => ({
        ...old,
        status: 'processing',
        progress: 0,
        epoch: 0,
        logs: [],
        metrics: null,
      }));
      
      // Invalidate React Query so it immediately re-fetches the actual status
      queryClient.invalidateQueries({ queryKey: ['projectStatus', jobId] });
      
      addToast({ type: "success", message: "Training restarted successfully!" });
    } catch (err) {
      addToast({ type: "error", message: "Failed to restart training" });
    }
  };

  const handleRetry = async () => {
    try {
      addToast({ type: "info", message: "Fetching project configuration..." });
      const project = await fetchProject(jobId);
      
      const errorMsg = job?.errorMessage?.toLowerCase() || "";
      const isResourceError = errorMsg.includes('out of memory') || 
                              errorMsg.includes('oom') || 
                              errorMsg.includes('acceleratorerror') ||
                              errorMsg.includes('runtimeerror') ||
                              errorMsg.includes('out of bounds');

      if (isResourceError) {
        setRetryProjectData(project);
        setShowRetryModal(true);
        return;
      }
      
      setRetryProjectData(project);
      await executeRetry(false);
    } catch (err) {
      addToast({ type: "error", message: "Failed to fetch project configuration" });
    }
  };

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
        // Only update the metrics ref, don't append to history on every poll
        useTrainingStore.setState({ metrics: job.metrics });

        // Populate graph history from backend's per-epoch training history
        if (job.metrics.trainingHistory && job.metrics.trainingHistory.length > 0) {
          setHistory(job.metrics.trainingHistory);
        } else if (history.length === 0 && jobStatus === "completed") {
          // Fallback: if no trainingHistory but we have final metrics, create a single-point history
          setHistory([job.metrics]);
        }
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
      {showRetryModal && (
        <WarningModal 
          title="Retry with Safe Defaults"
          description="The training failed because the hyperparameters exceeded system limits. Would you like to retry using safe fallback defaults?"
          onCancel={() => setShowRetryModal(false)} 
          onContinue={() => executeRetry(true)} 
        />
      )}

      {/* Cancel & Unlock circuit breaker banner */}
      {(status === "processing" || status === "training") && (
        <div className="glass-card flex items-center justify-between gap-4 border border-amber/20 bg-amber/[0.04]">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-amber/10 flex items-center justify-center shrink-0">
              <AlertTriangle size={18} className="text-amber" />
            </div>
            <div>
              <h4 className="text-sm font-medium text-ivory">
                Project is {status === "training" ? "training" : "processing"}
              </h4>
              <p className="text-xs text-fern mt-0.5">
                If this seems stuck, you can cancel and unlock the project to retry or delete it.
              </p>
            </div>
          </div>
          <button
            onClick={handleCancel}
            disabled={isCancelling}
            className="shrink-0 px-4 py-2 rounded-xl bg-amber/10 border border-amber/30 text-amber text-sm font-medium hover:bg-amber/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isCancelling ? "Cancelling..." : "⚠️ Cancel & Unlock"}
          </button>
        </div>
      )}

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
          errorMessage={job?.errorMessage || job?.error_message || "Training failed"}
          onRetry={handleRetry}
        />
      )}

      {children}
    </div>
  );
}
