import type { Dataset, User, LogEntry, Metrics, Project } from '@/types/project';

export const mockUser: User = {
  id: 'user-001',
  email: 'demo@slmstudio.ai',
  username: 'demo_user',
  fullName: 'Demo User',
  isActive: true,
  createdAt: '2024-01-15T08:00:00Z',
};

export const mockDatasets: Dataset[] = [
  {
    id: 'ds-001',
    name: 'Customer Support QA.pdf',
    filePath: '/uploads/customer-support-qa.pdf',
    datasetType: 'structured',
    userId: 'user-001',
    createdAt: '2024-03-10T14:30:00Z',
  },
  {
    id: 'ds-002',
    name: 'Medical Knowledge Base.docx',
    filePath: '/uploads/medical-kb.docx',
    datasetType: 'unstructured',
    userId: 'user-001',
    createdAt: '2024-03-12T09:15:00Z',
  },
  {
    id: 'ds-003',
    name: 'Financial Reports 2024.csv',
    filePath: '/uploads/financial-reports.csv',
    datasetType: 'structured',
    userId: 'user-001',
    createdAt: '2024-03-15T11:00:00Z',
  },
];

export const mockJobs: Project[] = [
  {
    id: 'job-001',
    name: 'Customer Support Bot',
    status: 'completed' as const,
    baseModelName: 'Qwen 2.5 1.5B',
    useCase: 'business' as const,
    hyperparameters: { epochs: 50, learningRate: 0.0002, batchSize: 8, maxSeqLen: 512 },
    persona: 'You are a helpful customer support assistant. Be concise, friendly, and professional.',
    fewShotExamples: [],
    datasetId: 'ds-001',
    createdAt: '2024-03-20T10:00:00Z',
    errorMessage: null,
  },
  {
    id: 'job-002',
    name: 'Medical Assistant',
    status: 'processing' as const,
    baseModelName: 'Qwen 2.5 1.5B',
    useCase: 'medical' as const,
    hyperparameters: { epochs: 50, learningRate: 0.0001, batchSize: 4, maxSeqLen: 1024 },
    persona: 'You are a medical knowledge assistant. Provide accurate, evidence-based information.',
    fewShotExamples: [],
    datasetId: 'ds-002',
    createdAt: '2024-03-22T08:30:00Z',
    errorMessage: null,
  },
  {
    id: 'job-003',
    name: 'Finance Analyst',
    status: 'pending' as const,
    baseModelName: 'Qwen 2.5 0.5B',
    useCase: 'finance' as const,
    hyperparameters: { epochs: 30, learningRate: 0.0003, batchSize: 16, maxSeqLen: 256 },
    persona: 'You are a financial analysis assistant. Interpret data clearly and highlight trends.',
    fewShotExamples: [],
    datasetId: 'ds-003',
    createdAt: '2024-03-25T16:00:00Z',
    errorMessage: null,
  },
  {
    id: 'job-004',
    name: 'Legal Research Helper',
    status: 'completed' as const,
    baseModelName: 'Qwen 2.5 1.5B',
    useCase: 'legal' as const,
    hyperparameters: { epochs: 40, learningRate: 0.00015, batchSize: 8, maxSeqLen: 768 },
    persona: 'You are a legal research assistant. Cite relevant precedents and statutes.',
    fewShotExamples: [],
    datasetId: 'ds-001',
    createdAt: '2024-03-28T09:00:00Z',
    errorMessage: null,
  },
  {
    id: 'job-005',
    name: 'Education Tutor',
    status: 'failed' as const,
    baseModelName: 'Qwen 2.5 0.5B',
    useCase: 'education' as const,
    hyperparameters: { epochs: 20, learningRate: 0.0005, batchSize: 32, maxSeqLen: 256 },
    persona: 'You are an educational tutor. Explain concepts simply with examples.',
    fewShotExamples: [],
    datasetId: 'ds-002',
    createdAt: '2024-03-30T13:00:00Z',
    errorMessage: 'CUDA out of memory. Reduce batch size or sequence length.',
  },
  {
    id: 'job-006',
    name: 'General Assistant',
    status: 'completed' as const,
    baseModelName: 'Qwen 2.5 0.5B',
    useCase: 'general' as const,
    hyperparameters: { epochs: 25, learningRate: 0.0002, batchSize: 16, maxSeqLen: 512 },
    persona: 'You are a helpful general-purpose assistant.',
    fewShotExamples: [],
    datasetId: 'ds-003',
    createdAt: '2024-04-01T10:30:00Z',
    errorMessage: null,
  },
];

export const mockActivities = [
  { id: 'act-001', type: 'success' as const, message: 'Customer Support Bot training completed', timestamp: '2024-03-20T12:00:00Z' },
  { id: 'act-002', type: 'training' as const, message: 'Medical Assistant started training Epoch 12/50', timestamp: '2024-03-22T10:00:00Z' },
  { id: 'act-003', type: 'info' as const, message: 'Finance Analyst queued for training', timestamp: '2024-03-25T16:05:00Z' },
  { id: 'act-004', type: 'success' as const, message: 'Legal Research Helper deployed to playground', timestamp: '2024-03-28T11:00:00Z' },
  { id: 'act-005', type: 'error' as const, message: 'Education Tutor training failed', timestamp: '2024-03-30T13:30:00Z' },
  { id: 'act-006', type: 'success' as const, message: 'General Assistant training completed', timestamp: '2024-04-01T12:30:00Z' },
];

export const mockLogs: LogEntry[] = [
  { time: '2024-03-20T10:00:00Z', level: 'info', message: 'Initializing training environment...' },
  { time: '2024-03-20T10:00:05Z', level: 'info', message: 'Loading dataset Customer Support QA.pdf...' },
  { time: '2024-03-20T10:00:08Z', level: 'success', message: 'Dataset loaded. 1,248 samples found.' },
  { time: '2024-03-20T10:00:10Z', level: 'info', message: 'Starting epoch 1/50' },
  { time: '2024-03-20T10:00:15Z', level: 'info', message: 'Epoch 5/50 — Loss: 1.8234 — Val Loss: 1.9123' },
  { time: '2024-03-20T10:00:20Z', level: 'info', message: 'Epoch 10/50 — Loss: 1.2345 — Val Loss: 1.3456' },
  { time: '2024-03-20T10:00:25Z', level: 'warn', message: 'Learning rate adjusted: 0.00019' },
  { time: '2024-03-20T10:00:30Z', level: 'info', message: 'Epoch 25/50 — Loss: 0.5678 — Val Loss: 0.6789' },
  { time: '2024-03-20T10:00:35Z', level: 'info', message: 'Epoch 40/50 — Loss: 0.2345 — Val Loss: 0.3456' },
  { time: '2024-03-20T10:00:40Z', level: 'success', message: 'Training completed successfully!' },
  { time: '2024-03-20T10:00:41Z', level: 'info', message: 'Saving model checkpoint...' },
  { time: '2024-03-20T10:00:45Z', level: 'success', message: 'Model saved. Ready for deployment.' },
];

export const mockMetrics: Metrics[] = Array.from({ length: 50 }, (_, i) => {
  const epoch = i + 1;
  const trainLoss = 2.5 * Math.exp(-0.08 * epoch) + 0.1 + Math.random() * 0.05;
  return {
    epoch,
    trainLoss,
    valLoss: trainLoss * (1 + 0.05 + Math.random() * 0.05),
    learningRate: 0.0002 * Math.pow(0.95, epoch),
    perplexity: Math.exp(trainLoss),
    gpuUtil: 60 + Math.random() * 35,
  };
});

export const mockConversations = [
  {
    id: 'conv-001',
    title: 'Customer Support Bot Chat',
    messages: [
      { role: 'user' as const, content: 'How do I reset my password?' },
      { role: 'assistant' as const, content: 'You can reset your password by clicking "Forgot Password" on the login page. A reset link will be sent to your email.', citations: ['Support Guide — Chapter 2'] },
    ],
    createdAt: '2024-03-20T14:00:00Z',
  },
  {
    id: 'conv-002',
    title: 'Medical Assistant Chat',
    messages: [
      { role: 'user' as const, content: 'What are the symptoms of vitamin D deficiency?' },
      { role: 'assistant' as const, content: 'Common symptoms include fatigue, bone pain, muscle weakness, and mood changes. Consult a healthcare provider for proper diagnosis.', citations: ['Medical KB — Chapter 5'] },
    ],
    createdAt: '2024-03-22T15:00:00Z',
  },
];
