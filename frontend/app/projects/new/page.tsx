'use client';

import { useState, useEffect, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { DashboardLayout } from '@/components/templates/DashboardLayout';
import { WizardLayout } from '@/components/templates/WizardLayout';
import { WizardSetup } from '@/components/organisms/WizardSetup';
import { WizardUpload } from '@/components/organisms/WizardUpload';
import { WizardConfigure } from '@/components/organisms/WizardConfigure';
import { LoadingBuffer } from '@/components/organisms/LoadingBuffer';
import { useProjectStore } from '@/stores/projectStore';
import { useUIStore } from '@/stores/uiStore';
import type { FewShotExample, Hyperparameters } from '@/types/project';

// [FEATURE] Reverse-lookup from the full HuggingFace repo slug stored on the
// project back to the short alias the model-selector UI (WizardConfigure)
// works with. Kept in sync with BASE_MODEL_ALIASES in backend/app/ai/finetune.py.
// Includes the old, renamed/broken slugs too, so a project created before that
// fix still resumes onto the right selector option instead of none at all.
const MODEL_SLUG_TO_ALIAS: Record<string, string> = {
  'unsloth/Qwen3-1.7B-unsloth-bnb-4bit': 'qwen3-1.7b',
  'unsloth/Qwen3-4B-unsloth-bnb-4bit': 'qwen3-4b',
  'unsloth/Phi-3.5-mini-instruct-bnb-4bit': 'phi-3.5-mini',
  'unsloth/Qwen3-1.7B-bnb-4bit': 'qwen3-1.7b',
  'unsloth/Qwen3-4B-bnb-4bit': 'qwen3-4b',
};

// FastAPI returns errors in two shapes: a plain HTTPException gives
// `{ detail: "some string" }`; a Pydantic validation failure (422) gives
// `{ detail: [{ msg: "...", loc: [...], ... }, ...] }`. Axios wraps either as
// err.response.data. This normalizes both into a single displayable string.
function extractErrorDetail(err: unknown): string | null {
  if (typeof err !== 'object' || err === null) return null;
  const response = (err as { response?: { data?: { detail?: unknown } } }).response;
  const detail = response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    return detail
      .map((d) => (typeof d === 'object' && d !== null && 'msg' in d ? String((d as { msg: unknown }).msg) : null))
      .filter(Boolean)
      .join('; ') || null;
  }
  return null;
}

interface WizardData {
  name: string;
  useCase: string;
  persona: string;
  fewShotExamples: FewShotExample[];
  files: File[];
  textInput: string;
  selectedModel: string;
  hyperparameters: Hyperparameters;
  // [FEATURE] Previously uploaded datasets the user chose to reuse.
  existingDatasetIds: string[];
}

const defaultWizardData: WizardData = {
  name: '',
  useCase: 'general',
  persona: '',
  fewShotExamples: [
    { question: '', answer: '' },
  ],
  files: [],
  textInput: '',
  selectedModel: 'qwen3-1.7b',
  hyperparameters: {
    epochs: 3,
    learningRate: 0.0002,
    batchSize: 1,
    maxSeqLen: 512,
    temperature: 0.3,
  },
  existingDatasetIds: [],
};

function NewProjectWizard() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const resumeProjectId = searchParams.get('resume');
  const { createProject, uploadDatasets, startTraining, fetchProject, attachDatasets } = useProjectStore();
  const { addToast } = useUIStore();
  const [currentStep, setCurrentStep] = useState(0);
  const [wizardData, setWizardData] = useState<WizardData>(defaultWizardData);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [projectId, setProjectId] = useState<string | null>(null);
  // [FEATURE] True while we're fetching an existing project to resume into —
  // separate from isSubmitting, which drives the wizard's own loading buffer.
  const [isResuming, setIsResuming] = useState(!!resumeProjectId);

  // [FEATURE] Resume flow: a project that already has a persona and at least
  // one dataset attached (status still 'pending' because the user left
  // before hitting "Start Training") no longer needs to go through Setup or
  // Upload again — jump straight to Configure (select model) with
  // everything else pre-filled from what's already saved.
  useEffect(() => {
    if (!resumeProjectId) return;

    let cancelled = false;
    (async () => {
      try {
        const project = await fetchProject(resumeProjectId);
        if (cancelled) return;

        setWizardData((prev) => ({
          ...prev,
          name: project.name,
          useCase: project.useCase,
          persona: project.persona || '',
          fewShotExamples:
            project.fewShotExamples && project.fewShotExamples.length > 0
              ? project.fewShotExamples
              : prev.fewShotExamples,
          selectedModel: MODEL_SLUG_TO_ALIAS[project.baseModelName] || prev.selectedModel,
          hyperparameters: {
            ...prev.hyperparameters,
            ...(project.hyperparameters || {}),
          },
        }));
        setProjectId(project.id);
        setCurrentStep(2);
      } catch (err) {
        addToast({ type: 'error', message: 'Could not load that project to resume. Starting fresh instead.' });
      } finally {
        if (!cancelled) setIsResuming(false);
      }
    })();

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resumeProjectId]);

  const handleSetupChange = (data: {
    name: string;
    useCase: string;
    persona: string;
    fewShotExamples: FewShotExample[];
  }) => {
    setWizardData((prev) => {
      let nextModel = prev.selectedModel;
      if (data.useCase !== prev.useCase) {
        if (['medical'].includes(data.useCase)) {
          nextModel = 'phi-3.5-mini';
        } else if (['finance', 'legal'].includes(data.useCase)) {
          nextModel = 'qwen3-4b';
        } else {
          nextModel = 'qwen3-1.7b';
        }
      }
      return { ...prev, ...data, selectedModel: nextModel };
    });
  };

  const handleUploadChange = (files: File[]) => {
    setWizardData((prev) => ({ ...prev, files }));
  };

  const handleExistingDatasetsChange = (existingDatasetIds: string[]) => {
    setWizardData((prev) => ({ ...prev, existingDatasetIds }));
  };

  const handleTextChange = (text: string) => {
    setWizardData((prev) => ({ ...prev, textInput: text }));
  };

  const handleModelChange = (model: string) => {
    setWizardData((prev) => ({ ...prev, selectedModel: model }));
  };

  const handleHyperparametersChange = (hp: Hyperparameters) => {
    setWizardData((prev) => ({ ...prev, hyperparameters: hp }));
  };

  const handleUploadContinue = async () => {
    setIsSubmitting(true);
    let currentProjectId = projectId;
    
    try {
      // Step 1: create the project shell if not already created
      if (!currentProjectId) {
        const project = await createProject({
          name: wizardData.name,
          useCase: wizardData.useCase,
          persona: wizardData.persona,
          fewShotExamples: wizardData.fewShotExamples.filter(
            (ex) => ex.question.trim() && ex.answer.trim()
          ),
        });
        currentProjectId = project.id;
        setProjectId(currentProjectId);
      }

      // Step 2: upload the collected files, or convert pasted text into a .txt
      const filesToUpload: File[] = [...wizardData.files];
      if (filesToUpload.length === 0 && wizardData.textInput.trim()) {
        filesToUpload.push(
          new File([wizardData.textInput], 'pasted-text.txt', { type: 'text/plain' })
        );
      }

      if (filesToUpload.length > 0) {
        await uploadDatasets(currentProjectId, filesToUpload);
      }

      // [FEATURE] Attach any previously-uploaded datasets the user picked,
      // in addition to (or instead of) a fresh upload.
      if (wizardData.existingDatasetIds.length > 0) {
        await attachDatasets(currentProjectId, wizardData.existingDatasetIds);
      }
      
      setIsSubmitting(false);
      setCurrentStep(2);
    } catch (err: any) {
      // ─── CRITICAL TUNNEL DROPOUT INTERCEPTION ─────────────────────────────
      // If the project container shell was verified, but ngrok/HTTP2 terminated 
      // the large multi-part upload connection early, bypass the error block.
      if (currentProjectId && (err.message === 'Network Error' || !err.response)) {
        console.warn("Tunnel dropped streaming response context. Forcing wizard pipeline progression.");
        setIsSubmitting(false);
        setCurrentStep(2); // Safely push layout views forward to step 3 configuration
        return;
      }
      // ──────────────────────────────────────────────────────────────────────

      const detail = extractErrorDetail(err);
      addToast({ type: 'error', message: detail || 'Failed to upload datasets.' });
      setIsSubmitting(false);
    }
  };

  const handleStartTraining = async () => {
    if (!projectId) return;

    setIsSubmitting(true);

    // Request OS notification permission so we can alert when training finishes in the background
    if ("Notification" in window && Notification.permission === "default") {
      Notification.requestPermission();
    }

    const tryStartTraining = async () => {
      try {
        await startTraining(projectId, {
          baseModelName: wizardData.selectedModel,
          hyperparameters: wizardData.hyperparameters,
        });

        addToast({ type: 'success', message: 'Project created! Starting training...' });
        router.push(`/projects/${projectId}/train`);
      } catch (err: any) {
        const detail = extractErrorDetail(err);
        // If the backend rejects because ChromaDB ingestion is still ongoing, poll again
        if (detail?.toLowerCase().includes('processing') || detail?.toLowerCase().includes('vectors')) {
          setTimeout(tryStartTraining, 2500);
        } else {
          addToast({
            type: 'error',
            message: detail || 'Starting training failed.',
          });
          setIsSubmitting(false);
          router.push(`/projects/${projectId}/train`);
        }
      }
    };

    tryStartTraining();
  };

  if (isResuming) {
    return <LoadingBuffer messages={[
      'Loading your project...',
      'Restoring persona and datasets...',
    ]} />;
  }

  if (isSubmitting) {
    if (currentStep === 2) {
      return <LoadingBuffer messages={[
        'Processing your documents...',
        'Building knowledge base...',
        'Indexing content...',
        'Preparing training pipeline...'
      ]} />;
    }
  }

  return (
    <DashboardLayout>
      <WizardLayout currentStep={currentStep}>
        {currentStep === 0 && (
          <WizardSetup
            data={{
              name: wizardData.name,
              useCase: wizardData.useCase,
              persona: wizardData.persona,
              fewShotExamples: wizardData.fewShotExamples,
            }}
            onChange={handleSetupChange}
            onContinue={() => setCurrentStep(1)}
          />
        )}
        {currentStep === 1 && (
          <WizardUpload
            files={wizardData.files}
            textInput={wizardData.textInput}
            isSubmitting={isSubmitting}
            onFilesChange={handleUploadChange}
            onTextChange={handleTextChange}
            selectedExistingDatasetIds={wizardData.existingDatasetIds}
            onExistingDatasetsChange={handleExistingDatasetsChange}
            onContinue={handleUploadContinue}
            onBack={() => setCurrentStep(0)}
          />
        )}
        {currentStep === 2 && (
          <WizardConfigure
            selectedModel={wizardData.selectedModel}
            hyperparameters={wizardData.hyperparameters}
            onModelChange={handleModelChange}
            onHyperparametersChange={handleHyperparametersChange}
            onStartTraining={handleStartTraining}
            onBack={() => setCurrentStep(1)}
          />
        )}
      </WizardLayout>
    </DashboardLayout>
  );
}
// [FIX] useSearchParams() (used for the ?resume= param above) requires a
// Suspense boundary in the Next.js App Router, or the production build
// fails with "useSearchParams() should be wrapped in a suspense boundary".
export default function NewProjectPage() {
  return (
    <Suspense fallback={<LoadingBuffer messages={['Loading...']} />}>
      <NewProjectWizard />
    </Suspense>
  );
}
