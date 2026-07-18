export interface Hyperparameters {
  epochs?: number;
  learningRate?: number;
  batchSize?: number;
  maxSeqLen?: number;
  gradientAccumulationSteps?: number;
  temperature?: number;
}

export interface FewShotExample {
  question: string;
  answer: string;
}

export interface Project {
  id: string;
  name: string;
  status: 'pending' | 'processing' | 'training' | 'completed' | 'failed';
  baseModelName: string;
  useCase: 'education' | 'business' | 'finance' | 'medical' | 'legal' | 'general';
  hyperparameters: Hyperparameters;
  persona: string;
  fewShotExamples: FewShotExample[];
  datasetId: string;
  // [FEATURE] Full dataset objects already linked to this project — used by
  // the resume flow and the "reuse existing dataset" picker.
  datasets?: Dataset[];
  createdAt: string;
  errorMessage: string | null;
  inferenceTemperature?: number;
  progress?: number;
  epoch?: number;
}

export interface Dataset {
  id: string;
  name: string;
  filePath: string;
  datasetType: 'structured' | 'unstructured';
  userId: string;
  createdAt: string;
}

export interface User {
  id: string;
  email: string;
  username: string;
  fullName: string;
  isActive: boolean;
  createdAt: string;
}

export interface Metrics {
  epoch: number;
  trainLoss: number;
  valLoss: number;
  learningRate: number;
  gpuUtil: number;
}

export interface LogEntry {
  time?: string;
  createdAt?: string;
  level: 'info' | 'warn' | 'error' | 'success';
  message: string;
}

export interface Citation {
  id: string;
  documentName: string;
  chapter: string;
  content?: string;
}

export interface Message {
  role: 'user' | 'assistant';
  content: string;
  citations?: Citation[];
}

export interface JobCreate {
  name: string;
  datasetId: string;
  baseModelName: string;
  useCase: string;
  persona: string;
  fewShotExamples?: FewShotExample[];
  hyperparameters?: Hyperparameters;
}

export interface Toast {
  id: string;
  type: 'success' | 'error' | 'warning' | 'info';
  message: string;
  duration?: number;
}

export interface Activity {
  id: string;
  type: 'success' | 'training' | 'info' | 'error';
  message: string;
  timestamp: string;
}

export interface Conversation {
  id: string;
  title: string;
  messages: Message[];
  createdAt: string;
}
