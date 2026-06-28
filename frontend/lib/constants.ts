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
  batchSize: 8,
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
  { value: 'qwen-2.5-1.5b', label: 'Qwen 2.5 1.5B', description: 'Balanced performance and speed' },
  { value: 'qwen-2.5-0.5b', label: 'Qwen 2.5 0.5B', description: 'Faster training, lighter weight' },
] as const;
