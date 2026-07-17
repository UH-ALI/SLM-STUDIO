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
import api from '@/lib/api';
import type { FewShotExample, Hyperparameters } from '@/types/project';

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
};

function NewProjectPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const resumeId = searchParams.get('resumeId');
  const { createProject, uploadDatasets, startTraining } = useProjectStore();
  const { addToast } = useUIStore();
  const [currentStep, setCurrentStep] = useState(0);
  const [wizardData, setWizardData] = useState<WizardData>(defaultWizardData);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [isResuming, setIsResuming] = useState(false);

  // ── Resume Draft Project ──────────────────────────────────────────────
  // If ?resumeId is present, load the existing project's config and datasets
  // and jump the wizard to the appropriate step.
  useEffect(() => {
    if (!resumeId) return;

    setIsResuming(true);
    (async () => {
      try {
        const [projectRes, datasetsRes] = await Promise.all([
          api.get(`/projects/${resumeId}`),
          api.get(`/projects/${resumeId}/datasets`),
        ]);
        const project = projectRes.data;
        const datasets = datasetsRes.data;

        setProjectId(resumeId);
        setWizardData((prev) => ({
          ...prev,
          name: project.name || prev.name,
          useCase: project.useCase || prev.useCase,
          persona: project.persona || prev.persona,
          // Two storage shapes exist. The wizard posts {question, answer}, which the
          // backend stores verbatim; older rows use the collapsed {<question>: <answer>}
          // form. Reading keys[0] blindly turns the first into the literal "question".
          fewShotExamples: project.fewShotExamples?.length
            ? project.fewShotExamples.map((ex: Record<string, string>) => {
                if ('question' in ex && 'answer' in ex) {
                  return { question: ex.question ?? '', answer: ex.answer ?? '' };
                }
                const [question, answer] = Object.entries(ex)[0] ?? ['', ''];
                return { question, answer };
              })
            : prev.fewShotExamples,
        }));

        // If datasets exist, jump to Configure (step 2); otherwise Upload (step 1)
        if (datasets && datasets.length > 0) {
          setCurrentStep(2);
        } else {
          setCurrentStep(1);
        }

        addToast({ type: 'info', message: `Resuming "${project.name}" — pick up where you left off.` });
      } catch (err) {
        addToast({ type: 'error', message: 'Failed to resume draft project. Starting fresh.' });
      } finally {
        setIsResuming(false);
      }
    })();
  }, [resumeId]);

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
    try {
      let currentProjectId = projectId;
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
      
      setIsSubmitting(false);
      setCurrentStep(2);
    } catch (err) {
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
      'Resuming your draft project...',
      'Loading saved configuration...',
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

// useSearchParams() forces this route out of static prerendering, which `next build`
// rejects unless the reader sits inside a Suspense boundary.
export default function NewProjectPage() {
  return (
    <Suspense fallback={<LoadingBuffer messages={['Loading the setup wizard...']} />}>
      <NewProjectPageInner />
    </Suspense>
  );
}
