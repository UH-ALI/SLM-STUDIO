# Comprehensive Changes Summary

This document details all the enhancements, bug fixes, and architectural changes implemented in the AI Backend. It explains what was modified, the previous behavior, and the exact improvements made.

---

## 1. `backend/app/ai/rag_inference.py`

### 1.1 Two-Tier VRAM Cache (`P0.1`)
- **Earlier Behavior**: The system used `ACTIVE_MODELS` to load the full base model combined with the LoRA adapter for every active job. Switching between two jobs that used the same base model resulted in loading the heavy base model into VRAM twice (consuming ~1.9GB each time) or evicting and reloading it, causing severe VRAM strain on an 8GB GPU.
- **What Improved**: Replaced `ACTIVE_MODELS` with a two-tier system: `ACTIVE_BASE_MODELS` and `ACTIVE_ADAPTERS`. The base model (e.g., `unsloth/Qwen3-1.7B-bnb-4bit`) is loaded **once**. LoRA adapters for different jobs are dynamically swapped on top of the active base model using `set_adapter()`. This adapter swap takes <50ms and completely eliminates redundant base model VRAM usage.

### 1.2 Per-Model Async Inference Mutex (`P0.2`)
- **Earlier Behavior**: Concurrent requests to `model.generate()` could execute simultaneously. On a shared GPU, this led to CUDA crashes and KV-cache corruption, causing garbled text output for users.
- **What Improved**: Wrapped both synchronous and streaming generation calls in a thread lock (`_inference_lock`). Added `_increment_inference_count()` and `_decrement_inference_count()` to track active requests. Concurrent requests now queue cleanly and wait for their turn, preventing CUDA crashes.

### 1.3 Redis GPU State Awareness (`P0.3`)
- **Earlier Behavior**: Chat requests (inference) would blindly execute or attempt to load models into VRAM even when the Celery worker was executing a heavy fine-tuning job. This guaranteed an Out-Of-Memory (OOM) crash.
- **What Improved**: Added `_wait_for_gpu_ready()`. Before loading a model or generating text, the inference pipeline checks the `gpu:state` key in Redis. If the state is `draining` or `training`, the chat request pauses gracefully until the GPU is free, emitting SSE "waiting" events.

### 1.4 Domain-Aware Temperature (`P1.2`)
- **Earlier Behavior**: The inference `temperature` was hardcoded to `0.3`, which made medical queries slightly too creative and creative queries too rigid.
- **What Improved**: Added `DEFAULT_TEMPERATURE_BY_USE_CASE`. Medical and Legal queries default to a highly factual `0.15`. Business and General default to `0.30`, while Education defaults to `0.35` to allow for varied explanations.

### 1.5 Generation Parameters & Sequence Length (`P1.3`, `P1.4`)
- **Earlier Behavior**: `repetition_penalty` was high (`1.15`), and `no_repeat_ngram_size=4` was used. This inadvertently blocked the SLM from outputting its trained refusal phrasing cleanly. `MAX_SEQ_LEN` was `4096`, which mismatched the training phase.
- **What Improved**: Removed `no_repeat_ngram_size`, relaxed `repetition_penalty` to `1.05` for cleaner, stutter-free outputs, and aligned `MAX_SEQ_LEN` to `3072` (matching the new training target).

### 1.6 Adaptive Distance Thresholding (`P1.5`)
- **Earlier Behavior**: RAG retrieval had a hard cutoff at `0.45` (`RELEVANCE_THRESHOLD`). Borderline relevant chunks were entirely dropped.
- **What Improved**: Added `ADAPTIVE_THRESHOLD = 0.55`. If the top retrieved chunk is highly relevant (distance ≤ 0.45), the system "unlocks" borderline chunks up to a distance of 0.55, providing richer context without sacrificing precision.

---

## 2. `backend/app/worker/tasks.py`

### 2.1 Request Draining & Fail-Closed VRAM Handshake (`P0.4`)
- **Earlier Behavior**: When a training job started, the worker attempted to clear the API VRAM blindly. If a user was mid-chat, the API might reload the model instantly, or the VRAM clear might fail, leading the worker to start training anyway and crash the GPU.
- **What Improved**: 
  1. **Request Draining**: Worker sets Redis `gpu:state = "draining"` and waits up to 5 seconds for any active `_inference_lock` requests to finish.
  2. **Fail-Closed Handshake**: Sets `gpu:state = "training"` and attempts to clear API VRAM. If it fails, it retries once. If it still fails, it **aborts training** (fail-closed) to prevent the entire system from crashing.
  3. **Cleanup**: A `finally` block ensures `gpu:state` is always deleted from Redis, guaranteeing inference can resume even if training fails.

---

## 3. `backend/app/ai/finetune.py`

### 3.1 Early Stopping & Context Window (`P1.1`, `P1.4`)
- **Earlier Behavior**: Training ran blindly for exactly 3 epochs, regardless of whether the model was already optimized, risking overfitting. Context length was limited to 2048.
- **What Improved**: Added Hugging Face's `EarlyStoppingCallback(early_stopping_patience=1)`. Training now evaluates after each epoch and halts automatically if validation loss stops improving. Increased `MAX_SEQ_LEN` to `3072` to allow for larger RAG context windows during generation.

---

## 4. `backend/app/ai/data_generator.py`

### 4.1 Embedding-Based Grounding Check (`P2.1`)
- **Earlier Behavior**: To ensure generated training data didn't hallucinate, the system only checked if 40% of the words in the output existed in the source document chunk. This missed "paraphrased hallucinations" where semantic meaning drifted but words matched.
- **What Improved**: Added `_is_grounded_semantic()` using the already-loaded `SentenceTransformer`. It computes the Cosine Similarity between the source chunk and the generated output. Outputs with `cosine_sim < 0.5` are rejected. This costs 0 extra VRAM as the embedder is already resident for RAG.

---

## 5. `backend/app/ai/rag_ingestion.py`

### 5.1 System Visibility for Chunk Limits (`P2.3`)
- **Earlier Behavior**: When a user uploaded too many documents and exceeded `MAX_CHUNKS_PER_PROJECT = 2500`, the system executed a silent `print()` statement that was invisible to observability tools.
- **What Improved**: Integrated standard Python `logging`. The warning is now emitted via `logger.warning()`, ensuring it is captured in structured server logs and alerting systems so administrators know when a project requires splitting.
