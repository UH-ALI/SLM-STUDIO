# Root Cause Analysis: VRAM Contention (OOM)

You asked me to check the logs and explain what happened. Here is the full breakdown of the crash.

## What Happened
The training worker crashed with the following error:
```
ValueError: Some modules are dispatched on the CPU or the disk. Make sure you have enough GPU RAM to fit the quantized model.
```

## The Root Cause
This is a classic **VRAM contention** issue between your two containers (`slm_api` and `slm_worker`). You have a single RTX 5060 with **8GB of VRAM**.

1. **The API Inference Cache:** In `rag_inference.py`, the backend has an `@lru_cache` that loads the model into VRAM so that chat responses are instantaneous. **This cache never expires.**
2. **The Sequence of Events:** 
   - Earlier, you chatted with the Physics tutor. The `slm_api` container loaded the 1.7B model into VRAM, consuming about **~3GB**.
   - You then went to the Studio and clicked "Start Training" for a new project.
   - The `slm_worker` container tried to load the base model into VRAM to start fine-tuning. Fine-tuning requires VRAM for the model weights *plus* gradients and optimizer states (usually **~5-6GB**).
   - 8GB (Total) - 3GB (API) = **5GB remaining**.
   - Hugging Face Accelerate detected that 5GB was not enough to fit the training setup, so it attempted to offload parts of the model to your system RAM (CPU). 
   - 4-bit quantized models (`bitsandbytes`) strictly forbid CPU offloading without a special flag, causing the hard crash!

## Proposed Fix
Since we are constrained to 8GB of VRAM, we cannot simultaneously hold a model for chatting and a model for training. We need to implement a **VRAM Manager**:

1. Create a `free_memory()` utility in the API that clears the `@lru_cache` and calls `torch.cuda.empty_cache()`.
2. Right before the Worker begins Phase 3 (Fine-tuning), it should send a request to the API to forcibly drop any active inference models from VRAM.
3. This guarantees the Worker will always have the full 8GB of VRAM available when it needs to train!

*(Since you requested "PLAN ONLY", I have not implemented this yet. Let me know if you would like me to proceed with this fix!)*
