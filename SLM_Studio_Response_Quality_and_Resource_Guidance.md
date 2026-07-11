# SLM Studio — Response Quality, Data Pipeline & Resource-Use Guidance

**Purpose of this document:** actionable guidance for the AI/backend team on getting better model responses, tightening the data pipeline, and using the 8GB GPU efficiently — without adding VRAM pressure. Everything below is scoped to what's realistic in ~2 days, on the current hardware.

---

## 1. Hyperparameters — what to keep, what to adjust

Current settings (from `finetune.py` / `rag_inference.py`):

| Parameter | Current value | Verdict | Notes |
|---|---|---|---|
| Learning rate | `2e-4` | **Keep** | Standard, well-tested range for QLoRA. No change needed. |
| Epochs | `3` (fixed) | **Keep, but make it adaptive** | 3 is a reasonable default, and you already log an eval loss and a post-training health check (`loss < 0.5 → overfitting`). Turn that observation into an automatic stop instead of a print statement (see §3.1). |
| Batch size | `1` (per device), `grad_acc=8` → effective batch 8 | **Keep as-is** | This is the correct choice for an 8GB card running a 4-bit 1.7B–4B model. Do not raise per-device batch size — that's the single fastest way to OOM mid-training. If you want a larger effective batch, raise `grad_acc`, not `batch_size`. |
| LoRA rank (`r`) | 16 default, 32 for finance/legal/medical | **Keep** | Sensible mapping of capacity to task complexity. Don't raise this further "to improve quality" — see §2. |
| Temperature (inference) | `0.3` default | **Keep as the default, but make it domain-aware** | 0.3 is a good factual-RAG default. See §3.2 for a low-effort, zero-VRAM-cost refinement. |
| `top_p` / `repetition_penalty` / `no_repeat_ngram_size` | 0.9 / 1.15 / 4 | **Keep** | Reasonable anti-repetition settings for small models, which repeat more than larger ones. Only revisit if you see actual repetition in production logs — don't tune this blind. |
| `max_seq_len` (inference) | 4096 | **Keep** | Raising this increases VRAM per request (KV cache scales with sequence length). Only raise if you have concrete evidence documents/context are being truncated in a way that hurts answers — check job logs first. |

**Bottom line: the current hyperparameters are already reasonable defaults. Nothing here needs to change to move the needle on response quality — the actual quality wins are in data and prompt-level tuning (§3), not hyperparameter tuning.**

---

## 2. What NOT to do

Explicitly ruling these out, so no one spends the 2-day window on them:

- **Do not swap in a larger base model** (7B/8B-class) to chase quality. On an 8GB card running 4-bit, you're already close to the ceiling with the current 1.7B/4B lineup — a bigger model risks breaking both training and concurrent inference, and the VRAM-coordination fix you already built (API flushing its cache before a training job starts) only buys you headroom for models in the current size class, not a meaningfully larger one.
- **Do not raise LoRA rank beyond 32.** Rank increases VRAM and overfitting risk on the modest dataset sizes this pipeline produces (dozens to a few hundred pairs per chunk sample); it does not reliably improve answer quality at this data scale.
- **Do not raise `MAX_CACHED_MODELS`** (currently 3) without first measuring actual headroom. Every additional cached model raises your *baseline* VRAM usage even when idle, shrinking the margin before a training job needs the GPU.
- **Do not do full fine-tuning** (unfreezing the base model) instead of LoRA. This is the most common "quality" temptation and the most VRAM-expensive one — it doesn't fit the resource budget and isn't necessary for the score improvements you're after.
- **In short: every "make the model bigger/deeper" lever is off the table for this pass.** The wins below all come from better use of what's already loaded.

---

## 3. What to do instead — 2-day action list, zero additional VRAM

### 3.1 Add early stopping instead of always running the fixed epoch count
You already compute `eval_loss` every epoch and set `load_best_model_at_end=True` — you're one `EarlyStoppingCallback` away from actually acting on that signal instead of just printing a warning about it after the fact.

```python
from transformers import EarlyStoppingCallback

trainer = SFTTrainer(
    ...,
    callbacks=[MemoryClearCallback(), EpochUpdateCallback(),
               EarlyStoppingCallback(early_stopping_patience=1)],
)
```
This *reduces* GPU time (training can stop before epoch 3 if validation loss stops improving) rather than adding any cost — a rare case where the "do less" fix is also the resource-efficient one.

### 3.2 Domain-aware temperature defaults
You already do this pattern for LoRA rank (`16` vs `32` by use case) — apply the same idea to inference temperature. Precision-sensitive domains benefit from tighter sampling:

```python
DEFAULT_TEMPERATURE_BY_USE_CASE = {
    "medical": 0.15,
    "legal": 0.15,
    "finance": 0.2,
    "business": 0.3,
    "education": 0.35,
    "general": 0.3,
}
```
This is a config-only change — no retraining, no extra VRAM, immediate effect on the next inference call.

### 3.3 Strengthen the grounding check using the embedder you already have loaded
`_is_grounded()` in `data_generator.py` currently uses a bag-of-words overlap heuristic (40% of significant words must appear in the chunk). This works but is crude — it can pass paraphrased-but-ungrounded answers and fail correctly-grounded answers that use synonyms.

Since `SentenceTransformer("BAAI/bge-small-en-v1.5")` is already loaded for retrieval, reuse it here: embed the chunk and the generated answer, and require a minimum cosine similarity (e.g. `> 0.5`) in addition to (or instead of) the word-overlap check. This costs no additional VRAM or new dependency — it's the same embedder already resident in memory, just called on two more short strings per candidate pair.

### 3.4 Surface skipped/failed data-generation chunks instead of only printing them
When a chunk permanently fails generation (`generate_pairs_from_chunk`, after 4 retries) or produces a `data: []` empty response, it's currently just a `print()`. Log it to the `JobLog` table (which already exists and is used elsewhere in the pipeline) so a user with a document that's mostly image/OCR noise or badly formatted actually sees *why* their model's coverage is thin, rather than silently getting fewer training pairs than expected. This is a data-engineering visibility fix, not a resource change.

---

## 4. Overflow-handling & data-engineering review

### What's working well — keep these as-is
- **Context-window overflow is handled correctly at generation time.** The loop in `rag_inference.py` that drops context blocks from the *end* of the joined context string, one at a time, until the prompt fits the token budget, is doing the right thing — because retrieved chunks are already ordered by relevance (closest distance first), trimming from the end means you're dropping the *least* relevant chunk first, not an arbitrary one. This is good, deliberate design; no change needed.
- **The hybrid chunker** (`hybrid_chunk_markdown`) — header-aware splitting, falling back to sentence-aware splitting, with special handling so tables never get split mid-row — is solid data-engineering work. It correctly filters out reference-heavy chunks and chunks with too little alphabetic content before they ever reach the embedder.
- **Anti-hallucination and anti-circularity filters** in the synthetic data generator (word-overlap grounding check, circular-answer detection, an explicit forced negative example per chunk) are a genuinely good practice most teams skip. Keep the underlying approach; §3.3 above is a refinement, not a rewrite.
- **Deduplication** on the final training set (by lowercased instruction) is a correct, cheap safeguard against the LLM generating near-identical Q&A pairs across overlapping chunks.

### What needs improvement — actionable, in priority order
1. **`MAX_CHUNKS_PER_PROJECT` (2500) is a silent console warning, not an enforced limit or a user-facing signal.** A user uploading a very large corpus won't know their project has quietly crossed into "consider splitting into multiple projects" territory unless someone is watching the backend logs. Surface this as a warning in the project's status/logs the frontend already displays, or make it a hard cap with a clear error — either is fine, but "print and continue" isn't visible to the person it affects.
2. **`dynamic_pair_count()` caps at 10 pairs per chunk regardless of domain.** For domains like legal/medical where you already generate a richer `data_mix` prompt, 10 pairs may under-sample the chunk's actual content relative to a well-organized education chunk. Worth revisiting per-domain pair-count ceilings using the same use-case profile structure you already have — this is a data-quality lever, not a compute one.
3. **The VRAM-clearance call before training silently continues on failure.** In `tasks.py`, if the `DELETE /system/vram` call to the API container fails (timeout, API down, wrong secret), the worker logs a warning and proceeds to load the training model anyway. On an 8GB shared GPU, that's the exact scenario the coordination was built to prevent — a failed handshake shouldn't fail open. Recommend: retry once with backoff, and if it still fails, mark the job as failed with a clear log message rather than gambling on an OOM crash mid-run.
4. **No lock prevents inference from reloading a model into VRAM *during* an active training run.** The current fix flushes the API's cache once, right before training starts — but nothing stops a chat request arriving two minutes into training from loading a model back into VRAM mid-job. A simple Redis flag (`training_active`), set before the flush call and cleared in a `finally` block after `run_finetuning_pipeline` completes (success or failure), checked in `get_or_load_model` to return a "temporarily busy, a training job is running" response instead of attempting to load, would close this gap. Small addition, directly protects the constraint you're already designing around.

---

## 5. Model deployment & efficient resource use — standing guidance

- **The VRAM-coordination handshake you built (API flush → training start) is the right architecture — finish closing the two gaps in §4.3–4.4 above rather than adding new capability elsewhere.** This is the highest-leverage remaining piece of "system optimization" work on the table.
- **Log actual VRAM usage at the start and end of both inference and training calls** (you already call `torch.cuda.memory_allocated()` in places — make it consistent and always logged, not just printed during debugging). This costs nothing and gives you real numbers for capacity planning instead of guessing at headroom.
- **Don't expand the model catalog (`MODEL_CONFIGS`) without first benchmarking the new model's VRAM footprint on the actual 8GB box**, ideally under a simulated "training + one cached inference model" load, since that's the realistic worst case your coordination logic is meant to handle.
- **Treat the 8GB limit as fixed for this phase.** Every recommendation above works within it; none of them require negotiating for more GPU. If response quality still isn't where you want it after the data-engineering and prompt-level changes in §3, that's a signal to gather more/better source documents for the affected project, not to reach for a bigger model.

---

**Suggested order of work for the 2-day window:**
1. §3.1 (early stopping) and §3.2 (domain temperature map) — both are small, isolated, low-risk changes, do them first.
2. §4.3 (fail-closed VRAM handshake) — directly protects against the failure mode your architecture exists to prevent.
3. §3.4 (log skipped chunks) and §4.1 (surface the chunk-limit warning) — visibility improvements, no risk.
4. §3.3 (embedding-based grounding check) and §4.4 (training-active lock) if time remains — both are good but slightly more involved than the rest.
