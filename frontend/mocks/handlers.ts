import { http, HttpResponse, delay } from 'msw';
import {
  mockUser,
  mockDatasets,
  mockJobs,
  mockLogs,
  mockMetrics,
} from './data';
import type { JobCreate, Project, User } from '@/types/project';

// In-memory mutable state
let jobs: Project[] = [...mockJobs];
let datasets = [...mockDatasets];
let jobStatusMap: Record<string, string> = {};
let jobMetricsMap: Record<string, typeof mockMetrics> = {};
let jobLogsMap: Record<string, typeof mockLogs> = {};
let jobProgressMap: Record<string, number> = {};
let jobEpochMap: Record<string, number> = {};

// In-memory user registry: email -> user object
let registeredUsers: Record<string, User> = {
  [mockUser.email]: mockUser,
};
// Token -> email map so /users/me can return the right user
let tokenUserMap: Record<string, string> = {};

const TOKEN_RESPONSES = [
  'Based',
  ' on',
  ' your',
  ' documents',
  ',',
  ' the',
  ' answer',
  ' is',
  ' that',
  ' this',
  ' model',
  ' performs',
  ' optimally',
  ' with',
  ' the',
  ' configured',
  ' hyperparameters',
  '.',
  ' The',
  ' training',
  ' data',
  ' shows',
  ' consistent',
  ' improvement',
  ' across',
  ' all',
  ' epochs',
  '.',
];

export function generateChatTokens() {
  return TOKEN_RESPONSES;
}

function simulateTraining(jobId: string) {
  if (jobStatusMap[jobId]) return;

  jobStatusMap[jobId] = 'processing';
  jobMetricsMap[jobId] = [];
  jobLogsMap[jobId] = [
    { time: new Date().toISOString(), level: 'info' as const, message: 'Initializing training environment...' },
    { time: new Date().toISOString(), level: 'info' as const, message: 'Loading dataset...' },
    { time: new Date().toISOString(), level: 'success' as const, message: 'Dataset loaded successfully. 1,248 samples found.' },
  ];
  jobProgressMap[jobId] = 0;
  jobEpochMap[jobId] = 0;

  const totalEpochs = 50;
  let currentEpoch = 0;

  const interval = setInterval(() => {
    currentEpoch++;
    jobEpochMap[jobId] = currentEpoch;
    jobProgressMap[jobId] = (currentEpoch / totalEpochs) * 100;

    // Generate metrics for this epoch
    const trainLoss = 2.5 * Math.exp(-0.08 * currentEpoch) + 0.1 + Math.random() * 0.05;
    const valLoss = trainLoss * (1 + 0.05 + Math.random() * 0.05);
    const lr = 0.0002 * Math.pow(0.95, currentEpoch);
    const perplexity = Math.exp(trainLoss);
    const gpuUtil = 60 + Math.random() * 35;

    const metrics = {
      epoch: currentEpoch,
      trainLoss,
      valLoss,
      learningRate: lr,
      perplexity,
      gpuUtil,
    };

    if (!jobMetricsMap[jobId]) {
      jobMetricsMap[jobId] = [];
    }
    jobMetricsMap[jobId].push(metrics);

    // Add logs
    if (currentEpoch % 5 === 0) {
      jobLogsMap[jobId].push({
        time: new Date().toISOString(),
        level: 'info' as const,
        message: `Epoch ${currentEpoch}/${totalEpochs} — Loss: ${trainLoss.toFixed(4)} — Val Loss: ${valLoss.toFixed(4)}`,
      });
    }

    if (currentEpoch >= totalEpochs) {
      clearInterval(interval);
      jobStatusMap[jobId] = 'completed';
      jobLogsMap[jobId].push({
        time: new Date().toISOString(),
        level: 'success' as const,
        message: 'Training completed successfully!',
      });
    }
  }, 800);
}

export const handlers = [
  // Auth
  http.post('/api/v1/auth/login', async ({ request }) => {
    const formData = await request.formData();
    const email = formData.get('username')?.toString() || '';

    await delay(500);

    // Look up the registered user by email; fall back to demo user
    const user = registeredUsers[email] || mockUser;
    const token = 'mock-jwt-token-' + Date.now();
    tokenUserMap[token] = user.email;

    return HttpResponse.json({
      access_token: token,
      token_type: 'bearer',
      user,
    });
  }),

  http.post('/api/v1/auth/register', async ({ request }) => {
    const body = await request.json() as Record<string, string>;
    await delay(600);

    const newUser: User = {
      id: 'user-' + Date.now(),
      email: body.email || '',
      username: body.username || '',
      fullName: `${body.firstName || ''} ${body.lastName || ''}`.trim(),
      isActive: true,
      createdAt: new Date().toISOString(),
    };

    // Persist new user so subsequent login returns their own profile
    registeredUsers[newUser.email] = newUser;

    return HttpResponse.json(newUser, { status: 201 });
  }),

  http.get('/api/v1/users/me', async ({ request }) => {
    await delay(200);
    // Resolve which user owns this token
    const authHeader = request.headers.get('Authorization') || '';
    const token = authHeader.replace('Bearer ', '');
    const email = tokenUserMap[token];
    const user = (email && registeredUsers[email]) ? registeredUsers[email] : mockUser;
    return HttpResponse.json(user);
  }),

  // Datasets
  http.get('/api/v1/datasets', async () => {
    await delay(300);
    return HttpResponse.json(datasets);
  }),

  http.post('/api/v1/datasets', async ({ request }) => {
    await delay(1500);

    const formData = await request.formData();
    const file = formData.get('file') as File | null;

    const newDataset = {
      id: 'dataset-' + Date.now(),
      name: file?.name || 'Untitled Dataset',
      filePath: `/uploads/${file?.name || 'untitled'}`,
      datasetType: 'structured' as const,
      userId: mockUser.id,
      createdAt: new Date().toISOString(),
    };

    datasets.push(newDataset);
    return HttpResponse.json(newDataset, { status: 201 });
  }),

  http.post('/api/v1/datasets/:id/extend', async ({ params }) => {
    await delay(800);
    const dataset = datasets.find((d) => d.id === params.id);

    if (!dataset) {
      return HttpResponse.json({ error: 'Dataset not found' }, { status: 404 });
    }

    return HttpResponse.json({
      ...dataset,
      name: dataset.name + ' (Extended)',
    });
  }),

  // Jobs
  http.get('/api/v1/jobs', async () => {
    await delay(300);
    // Enrich jobs with live simulation data (progress, epoch, status)
    const enrichedJobs = jobs.map((job) => ({
      ...job,
      status: jobStatusMap[job.id] || job.status,
      progress: jobProgressMap[job.id] || 0,
      epoch: jobEpochMap[job.id] || 0,
    }));
    return HttpResponse.json(enrichedJobs);
  }),

  http.post('/api/v1/jobs', async ({ request }) => {
    const body = await request.json() as JobCreate;
    await delay(500);

    const newJob: Project = {
      id: 'job-' + Date.now(),
      name: body.name,
      status: 'pending',
      baseModelName: body.baseModelName || 'Qwen 2.5 1.5B',
      useCase: (body.useCase || 'general') as Project['useCase'],
      hyperparameters: body.hyperparameters || {},
      persona: body.persona || '',
      fewShotExamples: body.fewShotExamples || [],
      datasetId: body.datasetId || '',
      createdAt: new Date().toISOString(),
      errorMessage: null,
    };

    jobs.push(newJob);

    // Auto-start simulation after 2s
    setTimeout(() => {
      simulateTraining(newJob.id);
    }, 2000);

    return HttpResponse.json(newJob, { status: 201 });
  }),

  http.get('/api/v1/jobs/:id/status', async ({ params }) => {
    await delay(300);
    const job = jobs.find((j) => j.id === params.id);

    if (!job) {
      return HttpResponse.json({ error: 'Job not found' }, { status: 404 });
    }

    const status = jobStatusMap[job.id] || job.status;

    return HttpResponse.json({
      ...job,
      status,
      progress: jobProgressMap[job.id] || 0,
      epoch: jobEpochMap[job.id] || 0,
      metrics: jobMetricsMap[job.id]?.[jobMetricsMap[job.id].length - 1] || null,
      logs: jobLogsMap[job.id] || [],
    });
  }),

  // Inference
  http.post('/api/v1/inference/chat', async () => {
    await delay(2000);

    return HttpResponse.json({
      response: 'Based on your training data, I can provide insights about your specific use case. The model has been fine-tuned to understand your domain and will respond accordingly.',
      citations: ['Document 1 — Chapter 3', 'Document 2 — Chapter 1'],
    });
  }),

  http.post('/api/v1/inference/chat/stream', async () => {
    const encoder = new TextEncoder();
    const tokens = generateChatTokens();

    const stream = new ReadableStream({
      async start(controller) {
        for (const token of tokens) {
          await delay(80);
          controller.enqueue(
            encoder.encode(`data: ${JSON.stringify({ token })}\n\n`)
          );
        }
        controller.enqueue(encoder.encode('data: [DONE]\n\n'));
        controller.close();
      },
    });

    return new HttpResponse(stream, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        Connection: 'keep-alive',
      },
    });
  }),
];
