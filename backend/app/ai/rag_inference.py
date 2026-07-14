import asyncio
import json
import queue
import os
import re
import time
import torch
import warnings
import logging
import transformers
from collections import OrderedDict
from sentence_transformers import SentenceTransformer
import chromadb
import threading
from transformers import TextIteratorStreamer
import redis
from app.core.config import settings

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", message=".*max_new_tokens.*max_length.*")
warnings.filterwarnings("ignore", message=".*warmup_ratio.*deprecated.*")
transformers.logging.set_verbosity_error()

logger = logging.getLogger(__name__)

# ─── QWEN3 OUTPUT CLEANING ──────────────────────────────────────────────────
_THINK_BLOCK = re.compile(r'<think>.*?</think>', re.DOTALL)

def _clean_model_output(text: str) -> str:
    """Strip Qwen3 <think> reasoning blocks, source tags, and normalize whitespace."""
    text = _THINK_BLOCK.sub('', text)
    # Strip in-text Source/citation tags like [Source: ...], source:[], Source: [...]
    text = re.sub(r'\[?[Ss]ources?:?\s*(\[.*?\]|[^.\n\]]+\]?)', '', text)
    # Fix merged words: insert space before uppercase letters that follow lowercase
    text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
    # Collapse multiple spaces
    text = re.sub(r' {2,}', ' ', text)
    return text.strip()

# --- HARDWARE DETECTOR ---
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# ─── REDIS CLIENT (reuse Celery broker connection) ──────────────────────────
_redis_client = redis.Redis.from_url(settings.CELERY_BROKER_URL, decode_responses=True)

# ─── CONFIG ──────────────────────────────────────────────────────────────────
TOP_K               = 5
MAX_NEW_TOKENS      = 512
MAX_SEQ_LEN         = 3072           # [P1.4] Aligned with training (was 4096)
RELEVANCE_THRESHOLD = 0.45
ADAPTIVE_THRESHOLD  = 0.55           # [P1.5] Adaptive upper bound for borderline chunks

# ─── DOMAIN-AWARE TEMPERATURE DEFAULTS (§3.2) ───────────────────────────────
DEFAULT_TEMPERATURE_BY_USE_CASE = {
    "medical":   0.15,
    "legal":     0.15,
    "finance":   0.2,
    "business":  0.3,
    "education": 0.35,
    "general":   0.3,
}

# ─── CACHE LIMITS ────────────────────────────────────────────────────────────
MAX_CACHED_COLLECTIONS = 5
# [FIX] Explicit cap on simultaneously-resident base models (was previously
# unbounded — grew until VRAM ran out). Each quantized small base model is
# roughly 1.5-4GB; size this to your deployment GPU's VRAM budget, leaving
# headroom for activations + a training run's overhead:
#   8GB dev box    -> 1 (matches what actually fits; see vram_analysis.md)
#   24GB Vast.ai box -> 3-4 is comfortable
MAX_CACHED_BASE_MODELS = int(os.environ.get("MAX_CACHED_BASE_MODELS", "3"))

# ─── TWO-TIER VRAM CACHE (P0.1) ─────────────────────────────────────────────
# Tier 1: Base model cache — keyed by HF model slug (e.g., "unsloth/Qwen3-1.7B-bnb-4bit")
# Tier 2: Adapter registry — tracks which LoRA adapters are mounted on which base model
ACTIVE_BASE_MODELS = OrderedDict()   # { base_model_slug: (model, tokenizer) }
ACTIVE_ADAPTERS    = {}              # { job_id: base_model_slug }
ACTIVE_COLLECTIONS = OrderedDict()   # { project_id: collection }
_cache_lock = threading.Lock()
_embedder = None

# ─── PER-MODEL INFERENCE MUTEX (P0.2) ───────────────────────────────────────
# Prevents concurrent model.generate() calls which corrupt KV-cache on shared GPU
_inference_lock = threading.Lock()
# Track how many active inference requests are in-flight (for graceful draining)
_active_inference_count = 0
_active_inference_count_lock = threading.Lock()


def get_embedder():
    global _embedder
    if _embedder is None:
        logging.getLogger("sentence_transformers").setLevel(logging.ERROR)
        _embedder = SentenceTransformer("BAAI/bge-small-en-v1.5")
    return _embedder


def get_or_load_collection(project_id: str):
    """
    LRU cache for ChromaDB collections.
    """
    global ACTIVE_COLLECTIONS
    with _cache_lock:
        if project_id in ACTIVE_COLLECTIONS:
            ACTIVE_COLLECTIONS.move_to_end(project_id)
            return ACTIVE_COLLECTIONS[project_id]
        if len(ACTIVE_COLLECTIONS) >= MAX_CACHED_COLLECTIONS:
            oldest_id, _ = ACTIVE_COLLECTIONS.popitem(last=False)
            print("  Evicted collection cache")

        chroma_dir = f"data/vector_stores/project_{project_id}"
        if not os.path.exists(chroma_dir):
            chroma_dir = f"data/vector_stores/dataset_{project_id}"
            if not os.path.exists(chroma_dir):
                raise ValueError("Vector store not found.")
        client = chromadb.PersistentClient(path=chroma_dir)
        collection = client.get_or_create_collection(name=f"docs_{project_id}", metadata={"hnsw:space": "cosine"})
        ACTIVE_COLLECTIONS[project_id] = collection
        return collection


def _read_adapter_base_model(adapter_path: str) -> str:
    """Read the base_model_name_or_path from an adapter's config."""
    config_path = os.path.join(adapter_path, "adapter_config.json")
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            config = json.load(f)
        return config.get("base_model_name_or_path", "")
    return ""


def _is_small_slm(adapter_path: str) -> bool:
    """Check if the active model is a <=2B SLM (e.g. 1.5B or 1.7B)."""
    base_slug = _read_adapter_base_model(adapter_path).lower()
    return any(tag in base_slug for tag in ["1.5b", "1.7b", "0.5b", "1b"])


GPU_WAIT_MAX_SECONDS = 600      # 10 minutes max wait — final fallback timeout
GPU_WAIT_POLL_SECONDS = 2.0     # how often we check Redis
GPU_WAIT_HEARTBEAT_SECONDS = 6  # how often we tell the SSE client we're still waiting


def _wait_for_gpu_ready_sse():
    """
    [P0.3][FIX] Generator version of the GPU-ready wait.

    Polls Redis every GPU_WAIT_POLL_SECONDS, but only YIELDS a heartbeat
    event every GPU_WAIT_HEARTBEAT_SECONDS — this keeps the SSE connection
    alive (proxies/browsers kill idle connections after ~60-120s of silence)
    and lets the frontend show "waiting for GPU" instead of looking hung.

    Yields: {"status": "waiting_for_gpu", "message": str, "waited_seconds": int}
    Returns normally (StopIteration) once the GPU is free.
    Raises TimeoutError after GPU_WAIT_MAX_SECONDS — caller must catch this
    and turn it into a clean SSE error event; letting it propagate un-caught
    produces the "10 minutes of silence then one error" behavior we're fixing.
    """
    waited = 0
    last_heartbeat = -GPU_WAIT_HEARTBEAT_SECONDS  # force an immediate first heartbeat if busy

    gpu_state = _redis_client.get("gpu:state")
    if gpu_state in (None, "idle", ""):
        return  # fast path — GPU already free, no heartbeat needed

    while waited < GPU_WAIT_MAX_SECONDS:
        gpu_state = _redis_client.get("gpu:state")
        if gpu_state in (None, "idle", ""):
            return

        if waited - last_heartbeat >= GPU_WAIT_HEARTBEAT_SECONDS:
            last_heartbeat = waited
            friendly = "training" if gpu_state == "training" else "updating"
            logger.info(f"GPU busy (state={gpu_state}), waiting... ({waited}s)")
            yield {
                "status": "waiting_for_gpu",
                "message": f"Assistant is currently {friendly} with new data. "
                           f"Your response will begin shortly...",
                "waited_seconds": waited,
            }

        time.sleep(GPU_WAIT_POLL_SECONDS)
        waited += GPU_WAIT_POLL_SECONDS

    raise TimeoutError("GPU did not become available within 10 minutes.")


def _wait_for_gpu_ready():
    """
    Blocking wrapper around _wait_for_gpu_ready_sse() for non-streaming call
    sites (e.g. get_or_load_model, used by the synchronous chat endpoint).
    Drains the heartbeat generator silently; a TimeoutError raised inside
    the generator propagates out of this loop unchanged.
    """
    for _ in _wait_for_gpu_ready_sse():
        pass
    return True


def get_or_load_model(job_id: str):
    """
    [P0.1] Two-Tier VRAM Cache: Base Model + Dynamic LoRA Adapter Swapping.
    
    Instead of loading a full copy of the base model per adapter, we:
    1. Check which base model the adapter needs (from adapter_config.json)
    2. Load the base model ONCE into VRAM if not already cached
    3. Mount/swap the LoRA adapter on top (<50ms) without reloading the base
    
    [P0.3] Also checks Redis gpu:state — waits if training is active.
    """
    global ACTIVE_BASE_MODELS, ACTIVE_ADAPTERS

    # [P0.3] Wait for GPU to be available (not training/draining)
    _wait_for_gpu_ready()

    adapter_path = f"data/adapters/job_{job_id}"
    if not os.path.exists(adapter_path):
        raise ValueError("Adapter not found. Has training completed?")

    try:
        from unsloth import FastLanguageModel
    except ImportError:
        raise RuntimeError('Unsloth is not installed.')

    with _cache_lock:
        # Determine which base model this adapter needs
        base_slug = _read_adapter_base_model(adapter_path)
        if not base_slug:
            # Fallback: load directly from adapter path (legacy behavior)
            base_slug = adapter_path

        # --- Tier 1: Base Model Cache ---
        if base_slug in ACTIVE_BASE_MODELS:
            model, tokenizer = ACTIVE_BASE_MODELS[base_slug]
            ACTIVE_BASE_MODELS.move_to_end(base_slug)
            logger.info(f"  Base model cache hit: {base_slug}")
        else:
            # [FIX] Evict oldest base model(s) if we're at/over the cap, so the
            # cache size is deterministic instead of "however many happen to
            # fit" (previously unbounded — see MAX_CACHED_BASE_MODELS).
            while len(ACTIVE_BASE_MODELS) >= MAX_CACHED_BASE_MODELS:
                evicted_slug, _ = ACTIVE_BASE_MODELS.popitem(last=False)
                stale_adapters = [jid for jid, slug in ACTIVE_ADAPTERS.items() if slug == evicted_slug]
                for jid in stale_adapters:
                    del ACTIVE_ADAPTERS[jid]
                logger.info(
                    f"  Evicted base model from VRAM cache (cap={MAX_CACHED_BASE_MODELS}): "
                    f"{evicted_slug} (dropped {len(stale_adapters)} adapter mapping(s))"
                )
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

            # Load fresh base model into VRAM
            logger.info(f"  Loading base model into VRAM: {base_slug}")
            model, tokenizer = FastLanguageModel.from_pretrained(
                model_name=adapter_path,
                max_seq_length=MAX_SEQ_LEN,
                dtype=None,
                load_in_4bit=True,
                local_files_only=True,
            )
            FastLanguageModel.for_inference(model)
            ACTIVE_BASE_MODELS[base_slug] = (model, tokenizer)
            logger.info(f"  Base model cached. VRAM: {torch.cuda.memory_allocated() / 1e9:.2f} GB")

        # --- Tier 2: LoRA Adapter Swap ---
        if ACTIVE_ADAPTERS.get(job_id) != base_slug:
            # This adapter is not yet the active one on this base model
            try:
                # Try fast adapter swap (<50ms)
                model.set_adapter(job_id)
                logger.info(f"  Adapter swap (set_adapter): {job_id} (<50ms)")
            except (ValueError, KeyError):
                # Adapter not yet mounted — load it first
                try:
                    from peft import PeftModel
                    if not isinstance(model, PeftModel):
                        # First adapter load on a fresh base model
                        model, tokenizer = FastLanguageModel.from_pretrained(
                            model_name=adapter_path,
                            max_seq_length=MAX_SEQ_LEN,
                            dtype=None,
                            load_in_4bit=True,
                            local_files_only=True,
                        )
                        FastLanguageModel.for_inference(model)
                        ACTIVE_BASE_MODELS[base_slug] = (model, tokenizer)
                    else:
                        model.load_adapter(adapter_path, adapter_name=job_id)
                        model.set_adapter(job_id)
                    logger.info(f"  Adapter mounted + activated: {job_id}")
                except Exception as e:
                    # Final fallback: load adapter path directly
                    logger.warning(f"  Adapter swap failed ({e}), loading directly")
                    model, tokenizer = FastLanguageModel.from_pretrained(
                        model_name=adapter_path,
                        max_seq_length=MAX_SEQ_LEN,
                        dtype=None,
                        load_in_4bit=True,
                        local_files_only=True,
                    )
                    FastLanguageModel.for_inference(model)
                    ACTIVE_BASE_MODELS[base_slug] = (model, tokenizer)

            ACTIVE_ADAPTERS[job_id] = base_slug

        return (model, tokenizer)


# ─── MANUAL VRAM UNLOAD ─────────────────────────────────────────────────────
def unload_model(job_id: str) -> bool:
    global ACTIVE_BASE_MODELS, ACTIVE_ADAPTERS
    with _cache_lock:
        base_slug = ACTIVE_ADAPTERS.pop(job_id, None)
        if base_slug is None:
            return False
        # Only unload base model if no other adapters reference it
        remaining = [k for k, v in ACTIVE_ADAPTERS.items() if v == base_slug]
        if not remaining and base_slug in ACTIVE_BASE_MODELS:
            del ACTIVE_BASE_MODELS[base_slug]
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            logger.info(f"  Manually unloaded adapter {job_id}. VRAM: {torch.cuda.memory_allocated() / 1e9:.2f} GB")
        return True

def free_all_memory() -> bool:
    """Forcefully drop ALL cached models from VRAM (used by Worker before training)."""
    global ACTIVE_BASE_MODELS, ACTIVE_ADAPTERS
    import gc
    with _cache_lock:
        ACTIVE_BASE_MODELS.clear()
        ACTIVE_ADAPTERS.clear()
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            logger.info(f"🧹 Force cleared all API VRAM. Current Usage: {torch.cuda.memory_allocated() / 1e9:.2f} GB")
        return True


def prewarm_model_async(job_id: str):
    """Pre-warm base model and adapter in a background thread to reduce latency on first chat."""
    def _warm():
        try:
            get_or_load_model(job_id)
        except Exception as e:
            logger.warning(f"Pre-warm failed for {job_id}: {e}")
    threading.Thread(target=_warm, daemon=True).start()


# ─── INFERENCE COUNT TRACKING (for graceful draining) ────────────────────────
def _increment_inference_count():
    global _active_inference_count
    with _active_inference_count_lock:
        _active_inference_count += 1

def _decrement_inference_count():
    global _active_inference_count
    with _active_inference_count_lock:
        _active_inference_count = max(0, _active_inference_count - 1)

def get_active_inference_count() -> int:
    with _active_inference_count_lock:
        return _active_inference_count

# ─── IDENTITY TRIGGER ────────────────────────────────────────────────────────
_IDENTITY_TRIGGERS = re.compile(
    r'\b('
    r'who are you|who you are'
    r'|what are you|what you are'
    r'|introduce yourself|tell me about yourself'
    r'|what is your name|what\'?s your name'
    r'|who am i (talking|speaking) to'
    r'|who is this'
    r'|what can you do|what can you help'
    r'|what do you do|what is your role|what\'?s your role|what is your purpose'
    r'|are you an ai|are you a bot|are you human'
    r')\b',
    re.IGNORECASE
)

# ─── DEFAULT PERSONA & STYLE FALLBACKS ───────────────────────────────────────
DEFAULT_PERSONA = (
    "You are a highly capable AI domain expert.\n"
    "Strictly adopt the following persona provided by the user:\n\n"
    "[START USER DEFINED PERSONA]\n"
    "You are an expert AI assistant for the content of this document.\n"
    "You explain concepts clearly and concisely.\n"
    'When asked who you are, respond with: "I am your AI assistant. Ask me anything!"\n'
    "You only answer questions grounded in the provided documents.\n"
    "[END USER DEFINED PERSONA]\n\n"
    "UNBREAKABLE BOUNDARIES:\n"
    "- Answer entirely in the first-person voice of the role above.\n"
    "- Do not remind the user you are an AI unless explicitly asked who you are.\n"
    "- If the context does not contain the answer, refuse politely in character:\n"
    "  'This information is not available in the provided document.'\n"
    "- Never fabricate facts."
)

DEFAULT_STYLE = (
    "Answer clearly and concisely. Explain mechanisms and causes for "
    "analytical questions. State facts directly for factual questions."
)

# ─── RAG RETRIEVAL ───────────────────────────────────────────────────────────
def retrieve_context(project_id: str, query: str):
    """
    [PROJECT REFACTOR] Now uses project_id instead of dataset_id.
    Retrieves relevant chunks from the project's combined ChromaDB collection.
    [FIX] Supports both project-scoped and legacy dataset-scoped collections.
    """
    embedder   = get_embedder()
    collection = get_or_load_collection(project_id)
    query_vec  = embedder.encode([query])[0].tolist()
    results = collection.query(
        query_embeddings=[query_vec],
        n_results=TOP_K,
        include=["documents", "distances", "metadatas"]
    )
    
    # [BUG #8 FIX] Guard against empty databases causing ValueError in min()
    if not results["distances"] or not results["distances"][0]:
        return None, None
        
    if min(results["distances"][0]) > ADAPTIVE_THRESHOLD:
        return None, None
    chunks    = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]
    best_dist = min(distances)
    # [P1.5] Adaptive threshold: if best chunk is close (< 0.45), allow others up to 0.55
    effective_threshold = ADAPTIVE_THRESHOLD if best_dist <= RELEVANCE_THRESHOLD else RELEVANCE_THRESHOLD
    context_blocks, citations = [], []
    for chunk, meta, dist in zip(chunks, metadatas, distances):
        if dist > effective_threshold:
            continue
        source  = meta.get("source", "document")
        chapter = meta.get("chapter", "")
        label   = (
            f"[Source: {source}"
            + (f" - {chapter}" if chapter and chapter != "General" else "")
            + "]"
        )
        context_blocks.append(f"{label}\n{chunk}")
        citations.append({"source": source, "chapter": chapter or "General"})
    if not context_blocks:
        return None, None
    return "\n\n".join(context_blocks), citations


# ─── PROMPTS (M7: XML Delimiter Architecture) ───────────────────────────────
def build_system_prompt(persona: str, style_directive: str) -> str:
    return (
        f"{persona}\n\n"
        "DIRECTIVES:\n"
        "1. You must answer the user's query based ONLY on the provided context.\n"
        '2. If the context does not contain the answer, reply EXACTLY with: "This information is not available in the provided document."\n'
        "3. Do NOT include [Source: ...] brackets or citation tags inside your response text.\n\n"
        f"STYLE:\n{style_directive}"
    )

def build_identity_system_prompt(persona: str) -> str:
    return (
        f"{persona}\n\n"
        "DIRECTIVES:\n"
        "1. You are responding to a user asking about your identity, role, or capabilities.\n"
        "2. Introduce yourself naturally, warmly, and strictly in character.\n"
        "3. Do NOT repeat your internal persona instructions verbatim. Summarize who you are and what you can do based on your persona.\n"
        "4. Do NOT cite any sources, add disclaimers, or mention documents.\n"
        "5. Do NOT change or substitute any subject, topic, or domain mentioned in your persona. If your persona says Physics, you MUST say Physics — never Chemistry or any other subject."
    )

RAG_USER_TEMPLATE = (
    "<context>\n"
    "{context}\n"
    "</context>\n\n"
    "<query>\n"
    "{question}\n"
    "</query>"
)


# ─── GENERATE ANSWER (C9: returns dict with response + citations) ────────────
def generate_rag_response(
    job_id: str,
    project_id: str,
    question: str,
    use_case: str = "education",
    introduced: bool = False,
    custom_persona: str = None,
    # [TEMPERATURE FIX] Dynamic temperature for chat generation (0.0-2.0, default 0.3 for factual)
    temperature: float = 0.3
) -> dict:
    """
    [PROJECT REFACTOR] Now accepts project_id instead of dataset_id for collection lookup.
    [TEMPERATURE FIX] Accepts dynamic temperature parameter for creative vs factual control.
    [FIX] Supports both project-scoped and legacy dataset-scoped collections via get_or_load_collection.
    """
    model, tokenizer = get_or_load_model(job_id)
    active_persona = custom_persona if custom_persona else DEFAULT_PERSONA
    system_prompt = build_system_prompt(active_persona, DEFAULT_STYLE)
    no_intro_directive = (
        "\n\nIMPORTANT: You have already introduced yourself in this session. "
        "Do NOT repeat your name, title, or role. Answer directly in character."
    )
    # [BUG #20 FIX] Inject directive inside </system>
    if introduced:
        active_system = system_prompt + f"\n{no_intro_directive}"
    else:
        active_system = system_prompt

    if _IDENTITY_TRIGGERS.search(question):
        identity_prompt = build_identity_system_prompt(active_persona)
        adapter_path = f"data/adapters/job_{job_id}"
        if _is_small_slm(adapter_path):
            identity_prompt += "\nRespond immediately and directly without <think> blocks."
        if introduced:
            identity_prompt += f"\n{no_intro_directive}"
            
        messages = [
            {"role": "system", "content": identity_prompt},
            {"role": "user",   "content": question},
        ]
        context = None
        citations = []
    else:
        # [PROJECT REFACTOR] Use project_id for retrieval
        context, citations = retrieve_context(project_id, question)
        if context is None:
            return {
                "response": "This information is not available in the provided document.",
                "citations": []
            }
        messages = [
            {"role": "system", "content": active_system},
            {"role": "user",   "content": RAG_USER_TEMPLATE.format(
                context=context, question=question
            )},
        ]

    input_ids = tokenizer.apply_chat_template(
        messages, tokenize=True, add_generation_prompt=True, return_tensors="pt"
    ).to(DEVICE)
    attention_mask = (input_ids != tokenizer.pad_token_id).long()

    available_tokens = MAX_SEQ_LEN - input_ids.shape[1] - 10
    # [BUG #23 FIX] Loop until context fits or we can't shrink anymore
    while available_tokens < 50 and context is not None and not _IDENTITY_TRIGGERS.match(question):
        context_blocks = context.split("\n\n")
        if len(context_blocks) <= 1:
            break # Cannot shrink further
        context = "\n\n".join(context_blocks[:-1]) # drop the last block
        messages[-1]["content"] = RAG_USER_TEMPLATE.format(
            context=context, question=question
        )
        input_ids = tokenizer.apply_chat_template(
            messages, tokenize=True, add_generation_prompt=True, return_tensors="pt"
        ).to(DEVICE)
        attention_mask = (input_ids != tokenizer.pad_token_id).long()
        available_tokens = MAX_SEQ_LEN - input_ids.shape[1] - 10

    actual_new_tokens = min(MAX_NEW_TOKENS, max(available_tokens, 20))

    # [P0.2] Acquire inference mutex to prevent concurrent KV-cache corruption
    _increment_inference_count()
    try:
      with _inference_lock:
        with torch.no_grad():
            output_ids = model.generate(
                input_ids=input_ids,
                attention_mask=attention_mask,
                max_new_tokens=actual_new_tokens,
                temperature=temperature if temperature > 0.05 else None,
                do_sample=temperature > 0.05,
                top_p=0.9,
                repetition_penalty=1.05,       # [P1.3] Relaxed from 1.15 for cleaner output
                # [P1.3] Removed no_repeat_ngram_size=4 — was blocking trained refusal phrases
                pad_token_id=tokenizer.eos_token_id,
            )
    finally:
        _decrement_inference_count()

    new_tokens = output_ids[0][input_ids.shape[1]:]
    response_text = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
    response_text = _clean_model_output(response_text)
    return {
        "response": response_text,
        "citations": citations
    }


# ─── TOKEN STREAMING (SSE) ──────────────────────────────────────────────────
def generate_rag_response_stream(
    job_id: str,
    project_id: str,
    question: str,
    use_case: str = "education",
    introduced: bool = False,
    custom_persona: str = None,
    # [TEMPERATURE FIX] Dynamic temperature for chat generation (0.0-2.0, default 0.3 for factual)
    temperature: float = 0.3
):
    """
    [PROJECT REFACTOR] Now accepts project_id instead of dataset_id for collection lookup.
    [TEMPERATURE FIX] Accepts dynamic temperature parameter for creative vs factual control.
    [FIX] Supports both project-scoped and legacy dataset-scoped collections via get_or_load_collection.
    """
    # [FIX] Surface GPU-wait status to the client instead of sending zero
    # bytes for up to 10 minutes (which proxies/browsers treat as a dead
    # connection well before that timeout fires).
    try:
        for status_event in _wait_for_gpu_ready_sse():
            yield status_event
    except TimeoutError:
        yield {
            "status": "gpu_timeout",
            "error": "gpu_timeout",
            "message": "The GPU is still busy after 10 minutes. Please try again shortly.",
        }
        yield {"citations": [], "done": True}
        return

    model, tokenizer = get_or_load_model(job_id)
    active_persona = custom_persona if custom_persona else DEFAULT_PERSONA
    system_prompt = build_system_prompt(active_persona, DEFAULT_STYLE)
    no_intro_directive = (
        "\n\nIMPORTANT: You have already introduced yourself in this session. "
        "Do NOT repeat your name, title, or role. Answer directly in character."
    )
    # [BUG #20 FIX] Inject directive inside </system>
    if introduced:
        active_system = system_prompt + f"\n{no_intro_directive}"
    else:
        active_system = system_prompt

    if _IDENTITY_TRIGGERS.search(question):
        identity_prompt = build_identity_system_prompt(active_persona)
        adapter_path = f"data/adapters/job_{job_id}"
        if _is_small_slm(adapter_path):
            identity_prompt += "\nRespond immediately and directly without <think> blocks."
        if introduced:
            identity_prompt += f"\n{no_intro_directive}"

        messages = [
            {"role": "system", "content": identity_prompt},
            {"role": "user",   "content": question},
        ]
        context = None
        citations = []
    else:
        # [PROJECT REFACTOR] Use project_id for retrieval
        context, citations = retrieve_context(project_id, question)
        if context is None:
            yield {"token": "This information is not available in the provided document."}
            yield {"citations": [], "done": True}
            return
        messages = [
            {"role": "system", "content": active_system},
            {"role": "user",   "content": RAG_USER_TEMPLATE.format(context=context, question=question)},
        ]

    input_ids = tokenizer.apply_chat_template(
        messages, tokenize=True, add_generation_prompt=True, return_tensors="pt"
    ).to(DEVICE)
    attention_mask = (input_ids != tokenizer.pad_token_id).long()

    available_tokens = MAX_SEQ_LEN - input_ids.shape[1] - 10
    # [BUG #23 FIX] Loop until context fits
    while available_tokens < 50 and context is not None:
        context_blocks = context.split("\n\n")
        if len(context_blocks) <= 1:
            break
        context = "\n\n".join(context_blocks[:-1])
        messages[-1]["content"] = RAG_USER_TEMPLATE.format(
            context=context, question=question
        )
        input_ids = tokenizer.apply_chat_template(
            messages, tokenize=True, add_generation_prompt=True, return_tensors="pt"
        ).to(DEVICE)
        attention_mask = (input_ids != tokenizer.pad_token_id).long()
        available_tokens = MAX_SEQ_LEN - input_ids.shape[1] - 10

    actual_new_tokens = min(MAX_NEW_TOKENS, max(available_tokens, 20))

    streamer = TextIteratorStreamer(
        tokenizer,
        skip_prompt=True,
        skip_special_tokens=True
    )

    generation_kwargs = {
        "input_ids": input_ids,
        "attention_mask": attention_mask,
        "max_new_tokens": actual_new_tokens,
        "temperature": temperature if temperature > 0.05 else None,
        "do_sample": temperature > 0.05,
        "top_p": 0.9,
        "repetition_penalty": 1.05,        # [P1.3] Relaxed from 1.15
        # [P1.3] Removed no_repeat_ngram_size=4
        "pad_token_id": tokenizer.eos_token_id,
        "streamer": streamer,
    }

    # [BUG #19 FIX] Surface thread exceptions
    # [P0.2] Wrap generation in inference mutex to prevent concurrent KV-cache corruption
    err_queue = queue.Queue()
    def generate_with_error_capture(**kwargs):
        _increment_inference_count()
        try:
            with _inference_lock:
                model.generate(**kwargs)
        except Exception as e:
            err_queue.put(e)
            # Unblock the streamer queue so it doesn't hang forever
            if hasattr(streamer, 'text_queue'):
                streamer.text_queue.put(streamer.stop_signal)
        finally:
            _decrement_inference_count()

    thread = threading.Thread(target=generate_with_error_capture, kwargs=generation_kwargs)
    thread.start()

    def chunk_generator():
        in_think_block = False
        buffer = ""
        think_buffer = []
        yielded_any = False
        for new_text in streamer:
            buffer += new_text
            while True:
                if not in_think_block:
                    if "<think>" in buffer:
                        pre, buffer = buffer.split("<think>", 1)
                        if pre:
                            yielded_any = True
                            yield pre
                        in_think_block = True
                    else:
                        match_found = False
                        for i in range(6, 0, -1):
                            partial = "<think>"[:i]
                            if buffer.endswith(partial):
                                safe_to_yield = buffer[:-i]
                                if safe_to_yield:
                                    yielded_any = True
                                    yield safe_to_yield
                                buffer = buffer[-i:]
                                match_found = True
                                break
                        if not match_found:
                            if buffer:
                                yielded_any = True
                                yield buffer
                            buffer = ""
                        break
                else:
                    if "</think>" in buffer:
                        think_part, buffer = buffer.split("</think>", 1)
                        think_buffer.append(think_part)
                        in_think_block = False
                    else:
                        match_found = False
                        for i in range(7, 0, -1):
                            partial = "</think>"[:i]
                            if buffer.endswith(partial):
                                think_buffer.append(buffer[:-i])
                                buffer = buffer[-i:]
                                match_found = True
                                break
                        if not match_found:
                            think_buffer.append(buffer)
                            buffer = ""
                        break
        if not in_think_block and buffer:
            yielded_any = True
            yield buffer
        elif in_think_block and buffer:
            think_buffer.append(buffer)

        # Universal SLM Safety Net: if model yielded 0 tokens outside <think>,
        # rescue and yield the clean text from inside <think>...</think>.
        if not yielded_any and think_buffer:
            rescued = "".join(think_buffer).strip()
            if rescued:
                yield rescued

    has_yielded_content = False
    for chunk in chunk_generator():
        # Safe line/bracket filter for explicit [Source: ...] brackets only
        chunk = re.sub(r'\[[Ss]ource:.*?\]', '', chunk)
        if not has_yielded_content:
            chunk = chunk.lstrip()
        if chunk:
            has_yielded_content = True
            yield {"token": chunk}

    thread.join()
    
    # Check if thread crashed
    if not err_queue.empty():
        exc = err_queue.get()
        yield {"token": f"\n\n[ERROR DURING GENERATION: {str(exc)}]"}
        
    yield {"citations": citations, "done": True}