'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { DashboardLayout } from '@/components/templates/DashboardLayout';
import { WizardLayout } from '@/components/templates/WizardLayout';
import { WizardSetup } from '@/components/organisms/WizardSetup';
import { WizardUpload } from '@/components/organisms/WizardUpload';
import { WizardConfigure } from '@/components/organisms/WizardConfigure';
import { LoadingBuffer } from '@/components/organisms/LoadingBuffer';
import { useProjectStore } from '@/stores/projectStore';
import { useUIStore } from '@/stores/uiStore';
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
  selectedModel: 'qwen-2.5-1.5b',
  hyperparameters: {
    epochs: 3,
    learningRate: 0.0002,
    batchSize: 8,
    maxSeqLen: 512,
    temperature: 0.3,
  },
};

export default function NewProjectPage() {
  const router = useRouter();
  const { createProject, uploadDatasets, startTraining } = useProjectStore();
  const { addToast } = useUIStore();
  const [currentStep, setCurrentStep] = useState(0);
  const [wizardData, setWizardData] = useState<WizardData>(defaultWizardData);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSetupChange = (data: {
    name: string;
    useCase: string;
    persona: string;
    fewShotExamples: FewShotExample[];
  }) => {
    setWizardData((prev) => ({ ...prev, ...data }));
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

  // Runs the real 3-step backend flow: create project shell -> upload files -> start training.
  // Each step is awaited and surfaced separately so a failure midway (e.g. upload succeeds
  // but training fails to start) gives a specific error instead of one generic message,
  // and so the project the user already created isn't silently orphaned.
  const handleStartTraining = async () => {
    setIsSubmitting(true);
    try {
      // Step 1: create the project shell
      const project = await createProject({
        name: wizardData.name,
        useCase: wizardData.useCase,
        persona: wizardData.persona,
        fewShotExamples: wizardData.fewShotExamples.filter(
          (ex) => ex.question.trim() && ex.answer.trim()
        ),
      });

      // Step 2: upload the collected files, or convert pasted text into a .txt
      // file if that's what the user provided instead — the backend's upload
      // endpoint only accepts files, there's no separate "raw text" endpoint.
      const filesToUpload: File[] = [...wizardData.files];
      if (filesToUpload.length === 0 && wizardData.textInput.trim()) {
        filesToUpload.push(
          new File([wizardData.textInput], 'pasted-text.txt', { type: 'text/plain' })
        );
      }

      if (filesToUpload.length > 0) {
        try {
          await uploadDatasets(project.id, filesToUpload);
        } catch (err) {
          const detail = extractErrorDetail(err);
          addToast({
            type: 'error',
            message: detail || 'Project created, but file upload failed. You can retry uploading from the project page.',
          });
          router.push(`/projects/${project.id}/train`);
          return;
        }
      }

      // Step 3: start training with the chosen model + hyperparameters
      try {
        await startTraining(project.id, {
          baseModelName: wizardData.selectedModel,
          hyperparameters: wizardData.hyperparameters,
        });
      } catch (err) {
        const detail = extractErrorDetail(err);
        addToast({
          type: 'error',
          message: detail || 'Files uploaded, but starting training failed. You can retry from the project page.',
        });
        router.push(`/projects/${project.id}/train`);
        return;
      }

      addToast({ type: 'success', message: 'Project created! Starting training...' });

      // Navigate to training page, NEVER /dashboard
      router.push(`/projects/${project.id}/train`);
    } catch (err) {
      const detail = extractErrorDetail(err);
      addToast({ type: 'error', message: detail || 'Failed to create project' });
      setIsSubmitting(false);
    }
  };

  if (isSubmitting) {
    return <LoadingBuffer />;
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
            onFilesChange={handleUploadChange}
            onTextChange={handleTextChange}
            onContinue={() => setCurrentStep(2)}
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
