# AI Backend Implementation Change Log (Sync Tracker)

This document tracks every file change, line range, and exact code modification performed on the AI backend (`backend/app/ai/` and `backend/app/worker/`).
Use this file to synchronize AI enhancements with team members working on deployment or other branches.

---

## Change Tracking Table

| Date | File Path | Lines Modified | Priority / Task | Description of Change | Sync Status |
| :--- | :--- | :--- | :---: | :--- | :---: |
| 2026-07-08 | `rag_inference.py` | L1-80 | **P0.1** | Two-tier VRAM Cache (`ACTIVE_BASE_MODELS`/`ACTIVE_ADAPTERS`), Redis client, domain-aware temp map, inference mutex. Replaced `ACTIVE_MODELS` dict + `MAX_CACHED_MODELS` with two-tier architecture. | ✅ Done |
| 2026-07-08 | `rag_inference.py` | L80-220 | **P0.1/P0.3** | `_read_adapter_base_model()`, `_wait_for_gpu_ready()`, refactored `get_or_load_model()` with LoRA adapter swap + Redis `gpu:state` check. | ✅ Done |
| 2026-07-08 | `rag_inference.py` | L220-260 | **P0.1** | Updated `unload_model()` to work with adapter registry. Updated `free_all_memory()` with `gc.collect()`. Added `_increment/_decrement_inference_count()`. | ✅ Done |
| 2026-07-08 | `rag_inference.py` | L200-230 | **P1.5** | Adaptive RAG distance thresholding (`ADAPTIVE_THRESHOLD=0.55`). Best chunk < 0.45 allows borderline chunks up to 0.55. | ✅ Done |
| 2026-07-08 | `rag_inference.py` | L335-355 | **P0.2/P1.3** | `generate_rag_response`: wrapped `model.generate()` with `_inference_lock`, `repetition_penalty=1.05`, removed `no_repeat_ngram_size=4`. | ✅ Done |
| 2026-07-08 | `rag_inference.py` | L438-470 | **P0.2/P1.3** | `generate_rag_response_stream`: same mutex + generation param fixes in streaming path. | ✅ Done |
| 2026-07-08 | `rag_inference.py` | L37-38 | **P1.4** | `MAX_SEQ_LEN = 3072` (was 4096). Added `ADAPTIVE_THRESHOLD = 0.55`. | ✅ Done |
| 2026-07-08 | `tasks.py` | L8-20 | **P0.4** | Added `import redis, time` and `_redis_client` for GPU state coordination. | ✅ Done |
| 2026-07-08 | `tasks.py` | L155-195 | **P0.4** | Pre-training request draining: `gpu:state=draining` → wait 5s for active inference → `gpu:state=training` → fail-closed VRAM handshake with retry+abort. | ✅ Done |
| 2026-07-08 | `tasks.py` | L235-250 | **P0.4** | `finally` block: always clear `gpu:state` from Redis so inference can resume after training (success or failure). | ✅ Done |
| 2026-07-08 | `finetune.py` | L43 | **P1.1** | `MAX_SEQ_LEN = 3072` (was 2048) — aligned with inference. | ✅ Done |
| 2026-07-08 | `finetune.py` | L286-298 | **P1.1** | Added `EarlyStoppingCallback(early_stopping_patience=1)` to `SFTTrainer` callbacks. | ✅ Done |
| 2026-07-08 | `data_generator.py` | L152-190 | **P2.1** | Added embedding-based cosine similarity grounding check (`> 0.5`) using resident `SentenceTransformer`. Catches paraphrased hallucinations that pass word-overlap. | ✅ Done |
| *Deferred* | `data_generator.py` | — | **P2.2** | Log skipped/failed chunks to `JobLog` & diversify negative refusal phrasing. **Deferred per user request.** | ⏸️ Deferred |
| 2026-07-08 | `rag_ingestion.py` | L1-8, L205-215 | **P2.3** | Added `import logging` + `logger`. Replaced silent `print()` for `MAX_CHUNKS_PER_PROJECT` with `logger.warning()`. | ✅ Done |

---

## Key Architectural Changes Summary

### Globals Renamed/Replaced
- `ACTIVE_MODELS` (old) → `ACTIVE_BASE_MODELS` + `ACTIVE_ADAPTERS` (new)
- `MAX_CACHED_MODELS` (old, removed) → base models cached by slug, adapters tracked separately
- `MAX_SEQ_LEN = 4096` (old) → `MAX_SEQ_LEN = 3072` (new, both inference + training)

### New Imports Added
- `rag_inference.py`: `asyncio`, `json`, `time`, `redis`, `app.core.config.settings`
- `tasks.py`: `redis`, `time`
- `finetune.py`: `EarlyStoppingCallback` from `transformers`

### New Functions Added
- `rag_inference.py`: `_read_adapter_base_model()`, `_wait_for_gpu_ready()`, `_increment_inference_count()`, `_decrement_inference_count()`, `get_active_inference_count()`

### API/Endpoint Impact
- **No endpoint signature changes** — all changes are internal backend logic
- **SSE Behavior Change**: Chat requests during training will now wait (via `_wait_for_gpu_ready()`) instead of crashing. Frontend should handle a delay gracefully.
- **Deployment team note**: The `free_all_memory()` function signature is unchanged but now also clears `ACTIVE_ADAPTERS`.
