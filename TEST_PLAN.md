# Test Plan — AI Backend Changes

This document defines exactly how to verify every change across P0, P1, and P2. All tests can be run locally without a production deployment.

---

## Pre-Requisites
- Redis running (already required for Celery broker)
- Backend API running (`uvicorn` or `docker-compose up api`)
- Celery worker running (`celery -A app.worker.celery_app worker`)
- At least one project with uploaded documents and a completed training job

---

## P0: GPU Concurrency & Dynamic Adapter Swapping

### Test P0.1 — Two-Tier VRAM Cache
**Goal**: Verify that switching between two projects using the same base model does NOT reload the base model.
1. Send a chat request to Project A (job_A, uses Qwen3-1.7B).
2. Note VRAM usage from logs (e.g., `VRAM: 1.90 GB`).
3. Send a chat request to Project B (job_B, also uses Qwen3-1.7B).
4. **Expected**: Logs show `"Adapter swap: job_B"` and VRAM stays at ~1.9GB (no second base model load). Response is correct for Project B's persona.

### Test P0.2 — Per-Model Async Mutex
**Goal**: Verify two simultaneous chat requests don't crash CUDA.
1. Open two browser tabs, both logged into the same project.
2. Send a chat message in Tab 1 and immediately send another in Tab 2.
3. **Expected**: Tab 1 gets its response first (~1.5s). Tab 2 gets its response shortly after (~3s total). Neither crashes. No garbled output.

### Test P0.3 — GPU State Awareness (SSE Waiting Event)
**Goal**: Verify chat requests wait gracefully during training.
1. Start a training job on any project.
2. While training is running, send a chat request to any trained project.
3. **Expected**: Chat SSE stream emits `{"status": "waiting_for_gpu", "message": "..."}` events every ~2s. When training completes, the chat response generates automatically.

### Test P0.4 — Pre-Training Request Draining & Fail-Closed VRAM Handshake
**Goal**: Verify training doesn't kill active chat mid-sentence.
1. Send a chat request (long enough to take ~2s to generate).
2. Immediately trigger a training job while the response is streaming.
3. **Expected**: Chat finishes streaming its full response. Training starts only after chat completes. Redis shows `gpu:state` transitions: `draining` → `training` → cleared.

---

## P1: Model Quality & Persona Adherence

### Test P1.1 — Early Stopping Callback
**Goal**: Verify training can stop before epoch 3 if eval loss plateaus.
1. Run a training job with default 3 epochs.
2. Check training logs / `JobLog` entries.
3. **Expected**: If eval loss didn't improve after epoch 2, training stopped at epoch 2 instead of running all 3. Metrics reflect `epochs_completed: 2`.

### Test P1.2 — Domain-Aware Temperature Map
**Goal**: Verify different use_cases get different default temperatures.
1. Create a medical project → send a factual query.
2. Create a general/education project → send the same query.
3. **Expected**: Medical responses are more precise/deterministic (temp 0.15). General responses have slightly more variety (temp 0.3). Verify by checking logs or response style across 3–5 identical queries.

### Test P1.3 — No-Repeat N-Gram Removal & Repetition Penalty
**Goal**: Verify refusal phrases render cleanly.
1. Ask a question whose answer is NOT in the uploaded documents.
2. **Expected**: Model responds with clean refusal: `"This information is not available in the provided document."` — no garbled syntax, no broken words, no stuttering.

### Test P1.4 — MAX_SEQ_LEN = 3072
**Goal**: Verify inference and training both use 3072.
1. Check `finetune.py` logs during training: `max_seq_len=3072`.
2. Send a chat query with large context (5+ RAG chunks).
3. **Expected**: No truncation errors. Response correctly synthesizes information from all chunks.

### Test P1.5 — Adaptive Distance Thresholding
**Goal**: Verify borderline-relevant chunks are included.
1. Ask a query that is slightly tangential to the document content.
2. **Expected**: RAG retrieves chunks with distance up to 0.55 (previously would have been cut off at 0.45). Response includes relevant context that was previously missed.

---

## P2: Data Pipeline & Visibility

### Test P2.1 — Embedding-Based Grounding Check
**Goal**: Verify paraphrased hallucinations are caught during data generation.
1. Trigger a new training job (which runs `data_generator.py`).
2. Check generated `train.jsonl` for quality.
3. **Expected**: QA pairs that semantically diverge from source chunks (cosine sim < 0.5) are filtered out. Logs show `"Grounding filter: removed X pairs"`.

### Test P2.2 — Surface Skipped Chunks to JobLog
**Goal**: Verify users see why data generation had low coverage.
1. Upload a document with mixed quality (some OCR noise pages).
2. Trigger training.
3. **Expected**: `JobLog` table shows WARNING entries like `"Skipped chunk in 'document.pdf': low text quality"`. Frontend training log displays these warnings.

### Test P2.3 — MAX_CHUNKS_PER_PROJECT Warning
**Goal**: Verify large corpus warning is visible.
1. Upload enough documents to exceed 2500 chunks (or temporarily lower `MAX_CHUNKS_PER_PROJECT` to 10 for testing).
2. **Expected**: `JobLog` shows a WARNING: `"Project has reached maximum chunk limit (2500). Consider splitting into multiple projects."` Message is visible in the frontend project status.

---

## Quick Smoke Test Checklist (Run After All Changes)
- [ ] Start API + Worker successfully (no import errors)
- [ ] Send a chat message → get a streamed response
- [ ] Send two simultaneous chat messages → both succeed without crash
- [ ] Start training → chat requests wait gracefully → training completes → chat resumes
- [ ] Ask an out-of-scope question → clean refusal sentence
- [ ] Check training logs → early stopping and correct MAX_SEQ_LEN reported
