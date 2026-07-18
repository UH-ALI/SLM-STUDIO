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

# Suppress noisy runtime warning variants
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", message=".*max_new_tokens.*max_length.*")
warnings.filterwarnings("ignore", message=".*warmup_ratio.*deprecated.*")
transformers.logging.set_verbosity_error()

logger = logging.getLogger(__name__)

# ─── QWEN3 REASONING & STRUCTURED OUTPUT CLEANING ───────────────────────────
_THINK_BLOCK = re.compile(r'<think>.*?</think>', re.DOTALL)

def _clean_model_output(text: str) -> str:
    """
    Strip Qwen3 <think> reasoning blocks, source tags, 
    and normalize whitespace anomalies.
    """
    text = _THINK_BLOCK.sub('', text)
    # Strip in-text Source/citation tags like [Source: ...], source:[], Source: [...]
    text = re.sub(r'\[?[Ss]ources?:?\s*(\[.*?\]|[^.\n\]]+\]?)', '', text)
    # Fix merged words: insert space before uppercase letters that follow lowercase
    text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
    # Collapse multiple spaces
    text = re.sub(r' {2,}', ' ', text)
    return text.strip()

# --- HARDWARE ACCELERATION DETECTION ---
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# ─── REDIS SHARED CONNECTION STATE LAYER ────────────────────────────────────
# Strips query string configurations to prevent redis-py parsing collisions
redis_url = settings.CELERY_BROKER_URL.split("?")[0] if "?" in settings.CELERY_BROKER_URL else settings.CELERY_BROKER_URL
_redis_client = redis.Redis.from_url(redis_url, decode_responses=True)

# ─── PARAMETRIC LOGISTICS BOUNDARIES ────────────────────────────────────────
TOP_K               = 5
MAX_NEW_TOKENS      = 512
MAX_SEQ_LEN         = 3072           # Aligned with context window size boundaries
RELEVANCE_THRESHOLD = 0.45
ADAPTIVE_THRESHOLD  = 0.55           # Upper bound window margin for borderline chunks

# ─── DOMAIN-AWARE INFERENCE CONFIGURATIONS ─────────────────────────────────
DEFAULT_TEMPERATURE_BY_USE_CASE = {
    "medical":   0.15,
    "legal":     0.15,
    "finance":   0.2,
    "business":  0.3,
    "education": 0.35,
    "general":   0.3,
}

# ─── TWO-TIER VRAM POOL LIMITS ──────────────────────────────────────────────
MAX_CACHED_COLLECTIONS = 5
MAX_CACHED_BASE_MODELS = int(os.environ.get("MAX_CACHED_BASE_MODELS", "1"))

# ─── TWO-TIER STATE REGISTRIES ──────────────────────────────────────────────
ACTIVE_BASE_MODELS = OrderedDict()   # { base_model_slug: (model, tokenizer) }
ACTIVE_ADAPTERS    = {}              # { job_id: base_model_slug }
ACTIVE_COLLECTIONS = OrderedDict()   # { project_id: collection }
_cache_lock = threading.Lock()
_embedder = None

# ─── MUTEX RESOURCE COORDINATION LOCKS ──────────────────────────────────────
_inference_lock = threading.Lock()
_active_inference_count = 0
_active_inference_count_lock = threading.Lock()


def get_embedder():
    global _embedder
    if _embedder is None:
        logging.getLogger("sentence_transformers").setLevel(logging.ERROR)
        _embedder = SentenceTransformer("BAAI/bge-small-en-v1.5")
    return _embedder


def get_or_load_collection(project_id: str):
    """LRU caching layer for disk-persistent ChromaDB collections."""
    global ACTIVE_COLLECTIONS
    with _cache_lock:
        if project_id in ACTIVE_COLLECTIONS:
            ACTIVE_COLLECTIONS.move_to_end(project_id)
            return ACTIVE_COLLECTIONS[project_id]
        if len(ACTIVE_COLLECTIONS) >= MAX_CACHED_COLLECTIONS:
            ACTIVE_COLLECTIONS.popitem(last=False)

        chroma_dir = f"data/vector_stores/project_{project_id}"
        if not os.path.exists(chroma_dir):
            chroma_dir = f"data/vector_stores/dataset_{project_id}"
            if not os.path.exists(chroma_dir):
                raise ValueError(f"Vector store not found for reference ID: {project_id}")
        
        client = chromadb.PersistentClient(path=chroma_dir)
        collection = client.get_or_create_collection(name=f"docs_{project_id}", metadata={"hnsw:space": "cosine"})
        ACTIVE_COLLECTIONS[project_id] = collection
        return collection


def _read_adapter_base_model(adapter_path: str) -> str:
    """Extract parent foundation target properties from adapter configs."""
    config_path = os.path.join(adapter_path, "adapter_config.json")
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            return json.load(f).get("base_model_name_or_path", "")
    return ""


def _is_small_slm(adapter_path: str) -> bool:
    """Detect if target model is a micro matrix structure."""
    base_slug = _read_adapter_base_model(adapter_path).lower()
    return any(tag in base_slug for tag in ["1.5b", "1.7b", "0.5b", "1b"])


GPU_WAIT_MAX_SECONDS = 600      
GPU_WAIT_POLL_SECONDS = 2.0     
GPU_WAIT_HEARTBEAT_SECONDS = 6  


def _wait_for_gpu_ready_sse():
    """
    Generator polling variant for GPU readiness coordination.
    Yields heartbeat updates to prevent browser/proxy connection drops.
    """
    waited = 0
    last_heartbeat = -GPU_WAIT_HEARTBEAT_SECONDS

    while waited < GPU_WAIT_MAX_SECONDS:
        gpu_state = _redis_client.get("gpu:state")
        if gpu_state in (None, "idle", ""):
            return

        if waited - last_heartbeat >= GPU_WAIT_HEARTBEAT_SECONDS:
            last_heartbeat = waited
            friendly = "training" if gpu_state == "training" else "updating"
            logger.info(f"GPU Resource active ({gpu_state}), queuing stream window context ({waited}s)")
            yield {
                "status": "waiting_for_gpu",
                "message": f"Assistant is currently {friendly} with new data. Your response will begin shortly...",
                "waited_seconds": int(waited),
            }

        time.sleep(GPU_WAIT_POLL_SECONDS)
        waited += GPU_WAIT_POLL_SECONDS

    raise TimeoutError("GPU compute block availability limit threshold exceeded.")


def _wait_for_gpu_ready():
    """Blocking consumer wrapper for synchronous invocation contexts."""
    for _ in _wait_for_gpu_ready_sse():
        pass
    return True


def get_or_load_model(job_id: str):
    """
    Two-Tier VRAM cache layer management routine.
    Loads foundations once, swapping dynamic adapter weights in <50ms.
    """
    global ACTIVE_BASE_MODELS, ACTIVE_ADAPTERS
    _wait_for_gpu_ready()

    adapter_path = f"data/adapters/job_{job_id}"
    if not os.path.exists(adapter_path):
        raise ValueError("Adapter artifacts missing. Has project training completed?")

    try:
        from unsloth import FastLanguageModel
    except ImportError:
        raise RuntimeError('Unsloth dependency missing inside active worker context.')

    with _cache_lock:
        base_slug = _read_adapter_base_model(adapter_path) or adapter_path

        # --- Tier 1: Foundation Baseline Validations ---
        if base_slug in ACTIVE_BASE_MODELS:
            model, tokenizer = ACTIVE_BASE_MODELS[base_slug]
            ACTIVE_BASE_MODELS.move_to_end(base_slug)
            logger.info(f"VRAM Cache Hit for Foundation: {base_slug}")
        else:
            while len(ACTIVE_BASE_MODELS) >= MAX_CACHED_BASE_MODELS:
                evicted_slug, _ = ACTIVE_BASE_MODELS.popitem(last=False)
                for jid in [jid for jid, slug in ACTIVE_ADAPTERS.items() if slug == evicted_slug]:
                    del ACTIVE_ADAPTERS[jid]
                logger.info(f"Evicted structural weights from cache window: {evicted_slug}")
                
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

            logger.info(f"Loading un-cached weights directly to memory matrix: {base_slug}")
            model, tokenizer = FastLanguageModel.from_pretrained(
                model_name=adapter_path,
                max_seq_length=MAX_SEQ_LEN,
                dtype=None,
                load_in_4bit=True,
                local_files_only=True,
            )
            FastLanguageModel.for_inference(model)
            ACTIVE_BASE_MODELS[base_slug] = (model, tokenizer)

        # --- Tier 2: Dynamic LoRA Matrix Swaps ---
        if ACTIVE_ADAPTERS.get(job_id) != base_slug:
            try:
                model.set_adapter(job_id)
                logger.info(f"Fast adapter swap completed: {job_id}")
            except (ValueError, KeyError):
                try:
                    from peft import PeftModel
                    if not isinstance(model, PeftModel):
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
                    logger.info(f"Dynamically mapped adapter parameters: {job_id}")
                except Exception as e:
                    logger.warning(f"Adapter context injection mismatch ({e}), clearing mapping layer cascades...")
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


def unload_model(job_id: str) -> bool:
    """Evict a specific adapter from VRAM allocation."""
    global ACTIVE_BASE_MODELS, ACTIVE_ADAPTERS
    with _cache_lock:
        base_slug = ACTIVE_ADAPTERS.pop(job_id, None)
        if base_slug is None:
            return False
        remaining = [k for k, v in ACTIVE_ADAPTERS.items() if v == base_slug]
        if not remaining and base_slug in ACTIVE_BASE_MODELS:
            del ACTIVE_BASE_MODELS[base_slug]
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            logger.info(f"Evicted active reference parameters for: {job_id}")
        return True


def free_all_memory() -> bool:
    """Purge entire VRAM cache allocation table before training runs."""
    global ACTIVE_BASE_MODELS, ACTIVE_ADAPTERS
    import gc
    with _cache_lock:
        ACTIVE_BASE_MODELS.clear()
        ACTIVE_ADAPTERS.clear()
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            logger.info("Cleared VRAM allocation metrics.")
        return True


def prewarm_model_async(job_id: str):
    """Background threading hook to pre-load project base weights."""
    def _warm():
        try:
            get_or_load_model(job_id)
        except Exception as e:
            logger.warning(f"Prewarm baseline generation caught exception: {e}")
    threading.Thread(target=_warm, daemon=True).start()


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


# ─── SYSTEM OVERRIDE IDENTITY RECOGNITION TRIGGERS ──────────────────────────
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

# ─── XML METADATA STRUCTURAL WRAPPERS ────────────────────────────────────────
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
    "- Never break character or remind the user you are an AI.\n"
    "- If the context does not contain the answer, refuse politely in character:\n"
    "  'This information is not available in the provided document.'\n"
    "- Never fabricate facts."
)

DEFAULT_STYLE = (
    "Answer clearly and concisely. Explain mechanisms and causes for "
    "analytical questions. State facts directly for factual questions."
)

RAG_USER_TEMPLATE = (
    "<context>\n"
    "{context}\n"
    "</context>\n\n"
    "<query>\n"
    "{question}\n"
    "</query>"
)


def retrieve_context(project_id: str, query: str):
    """Query context embeddings and filter using adaptive bounds."""
    embedder   = get_embedder()
    collection = get_or_load_collection(project_id)
    query_vec  = embedder.encode([query])[0].tolist()
    
    results = collection.query(
        query_embeddings=[query_vec],
        n_results=TOP_K,
        include=["documents", "distances", "metadatas"]
    )
    
    if not results["distances"] or not results["distances"][0]:
        return None, None
        
    best_dist = min(results["distances"][0])
    if best_dist > ADAPTIVE_THRESHOLD:
        return None, None
        
    effective_threshold = ADAPTIVE_THRESHOLD if best_dist <= RELEVANCE_THRESHOLD else RELEVANCE_THRESHOLD
    context_blocks, citations = [], []
    
    for chunk, meta, dist in zip(results["documents"][0], results["metadatas"][0], results["distances"][0]):
        if dist > effective_threshold:
            continue
        source  = meta.get("source", "document")
        chapter = meta.get("chapter", "")
        label   = f"[Source: {source}" + (f" - {chapter}" if chapter and chapter != "General" else "") + "]"
        context_blocks.append(f"{label}\n{chunk}")
        citations.append({"source": source, "chapter": chapter or "General"})
        
    return ("\n\n".join(context_blocks), citations) if context_blocks else (None, None)


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
        "5. Do NOT change or substitute any subject, topic, or domain mentioned in your persona."
    )


# ─── CORE EXECUTIVE PATHWAYS ───────────────────────────────────────────────

def generate_rag_response(job_id: str, project_id: str, question: str, use_case: str = "education", introduced: bool = False, custom_persona: str = None, temperature: float = 0.3) -> dict:
    """Synchronous inference context processor mapping pathway."""
    model, tokenizer = get_or_load_model(job_id)
    active_persona = custom_persona if custom_persona else DEFAULT_PERSONA
    system_prompt = build_system_prompt(active_persona, DEFAULT_STYLE)
    
    no_intro_directive = (
        "\n\nIMPORTANT: You have already introduced yourself in this session. "
        "Do NOT repeat your name, title, or role. Answer directly in character."
    )
    
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
        context, citations = retrieve_context(project_id, question)
        if context is None:
            return {
                "response": "This information is not available in the provided document.",
                "citations": []
            }
        messages = [
            {"role": "system", "content": active_system},
            {"role": "user",   "content": RAG_USER_TEMPLATE.format(context=context, question=question)},
        ]

    input_ids = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True, return_tensors="pt").to(DEVICE)
    attention_mask = (input_ids != tokenizer.pad_token_id).long()

    # Dynamic sliding context size sequence truncation loop
    available_tokens = MAX_SEQ_LEN - input_ids.shape[1] - 10
    while available_tokens < 50 and context is not None and not _IDENTITY_TRIGGERS.match(question):
        context_blocks = context.split("\n\n")
        if len(context_blocks) <= 1:
            break
        context = "\n\n".join(context_blocks[:-1])
        messages[-1]["content"] = RAG_USER_TEMPLATE.format(context=context, question=question)
        input_ids = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True, return_tensors="pt").to(DEVICE)
        attention_mask = (input_ids != tokenizer.pad_token_id).long()
        available_tokens = MAX_SEQ_LEN - input_ids.shape[1] - 10

    actual_new_tokens = min(MAX_NEW_TOKENS, max(available_tokens, 20))

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
                    repetition_penalty=1.05,
                    pad_token_id=tokenizer.eos_token_id,
                )
    finally:
        _decrement_inference_count()

    new_tokens = output_ids[0][input_ids.shape[1]:]
    response_text = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
    return {
        "response": _clean_model_output(response_text),
        "citations": citations
    }


def generate_rag_response_stream(job_id: str, project_id: str, question: str, use_case: str = "education", introduced: bool = False, custom_persona: str = None, temperature: float = 0.3):
    """SSE streaming response generator chunk-matrix tracking thread pathway."""
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
        context, citations = retrieve_context(project_id, question)
        if context is None:
            yield {"token": "This information is not available in the provided document."}
            yield {"citations": [], "done": True}
            return
        messages = [
            {"role": "system", "content": active_system},
            {"role": "user",   "content": RAG_USER_TEMPLATE.format(context=context, question=question)},
        ]

    input_ids = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True, return_tensors="pt").to(DEVICE)
    attention_mask = (input_ids != tokenizer.pad_token_id).long()

    available_tokens = MAX_SEQ_LEN - input_ids.shape[1] - 10
    while available_tokens < 50 and context is not None:
        context_blocks = context.split("\n\n")
        if len(context_blocks) <= 1:
            break
        context = "\n\n".join(context_blocks[:-1])
        messages[-1]["content"] = RAG_USER_TEMPLATE.format(context=context, question=question)
        input_ids = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True, return_tensors="pt").to(DEVICE)
        attention_mask = (input_ids != tokenizer.pad_token_id).long()
        available_tokens = MAX_SEQ_LEN - input_ids.shape[1] - 10

    actual_new_tokens = min(MAX_NEW_TOKENS, max(available_tokens, 20))
    streamer = TextIteratorStreamer(tokenizer, skip_prompt=True, skip_special_tokens=True)

    generation_kwargs = {
        "input_ids": input_ids,
        "attention_mask": attention_mask,
        "max_new_tokens": actual_new_tokens,
        "temperature": temperature if temperature > 0.05 else None,
        "do_sample": temperature > 0.05,
        "top_p": 0.9,
        "repetition_penalty": 1.05,
        "pad_token_id": tokenizer.eos_token_id,
        "streamer": streamer,
    }

    err_queue = queue.Queue()
    def generate_with_error_capture(**kwargs):
        _increment_inference_count()
        try:
            with _inference_lock:
                model.generate(**kwargs)
        except Exception as e:
            err_queue.put(e)
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

        if not yielded_any and think_buffer:
            rescued = "".join(think_buffer).strip()
            if rescued:
                yield rescued

    has_yielded_content = False
    for chunk in chunk_generator():
        chunk = re.sub(r'\[[Ss]ource:.*?\]', '', chunk)
        if not has_yielded_content:
            chunk = chunk.lstrip()
        if chunk:
            has_yielded_content = True
            yield {"token": chunk}

    thread.join()
    
    if not err_queue.empty():
        exc = err_queue.get()
        yield {"token": f"\n\n[ERROR DURING GENERATION: {str(exc)}]"}
        
    yield {"citations": citations, "done": True}