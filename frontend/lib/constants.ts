import type { Hyperparameters } from '@/types/project';

export const MAX_FILE_SIZE = 100 * 1024 * 1024; // 100MB

export const ALLOWED_FILE_TYPES = [
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'text/plain',
  'text/csv',
];

export const ALLOWED_FILE_EXTENSIONS = ['.pdf', '.docx', '.txt', '.csv'];

export const DEFAULT_HYPERPARAMETERS: Required<Hyperparameters> = {
  epochs: 3,
  learningRate: 0.0002,
  batchSize: 1,
  maxSeqLen: 512,
  gradientAccumulationSteps: 1,
  temperature: 0.3,
};

export const USE_CASES = [
  { value: 'education' as const, label: 'Education', description: 'Create tutors, teaching aids, and learning companions' },
  { value: 'business' as const, label: 'Business', description: 'Build customer support and business intelligence bots' },
  { value: 'finance' as const, label: 'Finance', description: 'Analyze reports and provide financial insights' },
  { value: 'medical' as const, label: 'Medical', description: 'Medical knowledge assistants and research helpers' },
  { value: 'legal' as const, label: 'Legal', description: 'Legal research and document analysis tools' },
  { value: 'general' as const, label: 'General', description: 'All-purpose AI assistants for any task' },
] as const;

export const MODEL_OPTIONS = [
  { value: 'llama-3.2-1b', label: 'Llama 3.2 1B', description: 'Fast, lightweight instruct model' },
  { value: 'gemma-2-2b', label: 'Gemma 2 2B', description: 'Reasoning-heavy instruct model' },
  { value: 'phi-3-mini', label: 'Phi 3 Mini', description: 'Precision-critical instruct model' },
] as const;
