import queue
import os
import re
import torch
import warnings
import logging
import transformers
from collections import OrderedDict
from sentence_transformers import SentenceTransformer
import chromadb
import threading
from transformers import TextIteratorStreamer

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", message=".*max_new_tokens.*max_length.*")
warnings.filterwarnings("ignore", message=".*warmup_ratio.*deprecated.*")
transformers.logging.set_verbosity_error()

# --- HARDWARE DETECTOR ---
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# ─── CONFIG ──────────────────────────────────────────────────────────────────
TOP_K               = 3
MAX_NEW_TOKENS      = 256
MAX_SEQ_LEN         = 4096
RELEVANCE_THRESHOLD = 0.85

# ─── CACHE LIMITS (H2) ─────────────────────────────────────────────────────────
MAX_CACHED_MODELS      = 3
MAX_CACHED_COLLECTIONS = 5

# ─── FASTAPI ACTIVE CACHE (LRU) ───────────────────────────────────────────────
ACTIVE_MODELS      = OrderedDict()  # { job_id: (model, tokenizer) }
ACTIVE_COLLECTIONS = OrderedDict()  # { project_id: collection }
_cache_lock = threading.Lock()
_embedder = None


def get_embedder():
    global _embedder
    if _embedder is None:
        logging.getLogger("sentence_transformers").setLevel(logging.ERROR)
        _embedder = SentenceTransformer("all-MiniLM-L6-v2")
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


def get_or_load_model(job_id: str):
    """LRU cache for fine-tuned models in GPU VRAM."""
    global ACTIVE_MODELS
    with _cache_lock:
        if job_id in ACTIVE_MODELS:
            ACTIVE_MODELS.move_to_end(job_id)
            return ACTIVE_MODELS[job_id]
        if len(ACTIVE_MODELS) >= MAX_CACHED_MODELS:
            oldest_id, _ = ACTIVE_MODELS.popitem(last=False)
            print("  Evicted model cache from VRAM")
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                print(f"  VRAM freed. Current: {torch.cuda.memory_allocated() / 1e9:.2f} GB")
        adapter_path = f"data/adapters/job_{job_id}"
        if not os.path.exists(adapter_path):
            raise ValueError("Adapter not found. Has training completed?")
        print("\n  Loading fine-tuned model into VRAM...")
        try:
            from unsloth import FastLanguageModel
        except ImportError:
            raise RuntimeError('Unsloth is not installed. Please install it with: pip install "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git"')
        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=adapter_path,
            max_seq_length=MAX_SEQ_LEN,
            dtype=None,
            load_in_4bit=True,
            local_files_only=True,
        )
        FastLanguageModel.for_inference(model)
        ACTIVE_MODELS[job_id] = (model, tokenizer)
        print(f"  Model cached. VRAM: {torch.cuda.memory_allocated() / 1e9:.2f} GB")
        return ACTIVE_MODELS[job_id]


# ─── H8: MANUAL VRAM UNLOAD ─────────────────────────────────────────────────
def unload_model(job_id: str) -> bool:
    global ACTIVE_MODELS
    with _cache_lock:
        if job_id not in ACTIVE_MODELS:
            return False
        del ACTIVE_MODELS[job_id]
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            print(f"  Manually unloaded model. VRAM: {torch.cuda.memory_allocated() / 1e9:.2f} GB")
        else:
            print("  Manually unloaded model (CPU mode)")
        return True


# ─── IDENTITY TRIGGER ────────────────────────────────────────────────────────
_IDENTITY_TRIGGERS = re.compile(
    r'^\s*('
    r'who are you|who you are'
    r'|what are you|what you are'
    r'|introduce yourself'
    r"|what is your name|what's your name"
    r'|who am i (talking|speaking) to'
    r'|who is this'
    r'|what can you do|what can you help (?:me )?with'
    r'|what do you do|tell me about yourself'
    r'|are you an ai|are you a bot'
    r')\s*[?!.]*\s*$',
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
        
    if min(results["distances"][0]) > RELEVANCE_THRESHOLD:
        return None, None
    chunks    = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]
    context_blocks, citations = [], []
    for chunk, meta, dist in zip(chunks, metadatas, distances):
        if dist > RELEVANCE_THRESHOLD:
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
    content = (
        f"{persona}\n\n"
        "OPERATIONAL DIRECTIVES:\n"
        "1. PERSONA ADHERENCE: You must fully embody the requested persona in every word. Maintain the requested voice, tone, and perspective throughout your entire response.\n"
        "2. ABSOLUTE GROUNDING: Your answers must be derived EXCLUSIVELY from the provided CONTEXT. You are strictly forbidden from using outside knowledge.\n"
        "3. CONTAINMENT & DENIAL: If the CONTEXT does not contain the specific information needed to answer the question, do not guess or extrapolate. You must output verbatim:\n"
        '   "This information is not available in the provided document."\n'
        "4. CLARITY & SYNTHESIS: Explain concepts using clear, accessible wording. Synthesize the data in your own voice rather than copy-pasting raw text.\n"
        "5. STRICT CITATION RULES:\n"
        "   - YOU MUST append the exact `[Source: ...]` label provided in the context blocks to the facts you state.\n"
        "   - YOU MUST NOT output any pre-existing academic citations, reference numbers, or footnotes (e.g., [1], (Author, 2019)) that are embedded inside the raw document text.\n"
        "6. ANALYTICAL: Never restate the question as your answer. Explain the specific mechanism, cause, or consequence.\n\n"
        f"DOMAIN RESPONSE STYLE:\n{style_directive}\n"
    )
    return f"<system>\n{content}</system>"


RAG_USER_TEMPLATE = (
    "<context>\n"
    "{context}\n"
    "</context>\n\n"
    "<query>\n"
    "{question}\n"
    "</query>\n\n"
    "<instruction>\n"
    "STRICT DIRECTIVE: You are operating in an enclosed RAG environment. "
    "Your response must be formulated EXCLUSIVELY from the data within the CONTEXT block above. "
    'If the data is insufficient, output exactly: "This information is not available in the provided document."\n\n'
    "FINAL CITATION RULES:\n"
    "- DO NOT output any pre-existing academic reference numbers or footnotes found inside the raw text (e.g., [1], (Author, 2020)).\n"
    "- YOU MUST explicitly append the injected `[Source: ...]` label to the facts you synthesize.\n"
    "</instruction>"
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
        active_system = system_prompt.replace("</system>", f"{no_intro_directive}\n</system>")
    else:
        active_system = system_prompt

    if _IDENTITY_TRIGGERS.match(question):
        identity_context = (
            f"The assistant's role and identity is as follows: {active_persona}\n\n"
            f"When asked about their identity, the assistant should introduce themselves "
            f"based on this role description."
        )
        messages = [
            {"role": "system", "content": active_system},
            {"role": "user",   "content": RAG_USER_TEMPLATE.format(
                context=identity_context,
                question="Who are you and what can you help me with?"
            )},
        ]
        context = identity_context
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

    with torch.no_grad():
        output_ids = model.generate(
            input_ids=input_ids,
            attention_mask=attention_mask,
            max_new_tokens=actual_new_tokens,
            # [TEMPERATURE FIX] Use dynamic temperature instead of hardcoded 0.3
            temperature=temperature,
            do_sample=True,
            pad_token_id=tokenizer.eos_token_id,
        )

    new_tokens = output_ids[0][input_ids.shape[1]:]
    response_text = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
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
    model, tokenizer = get_or_load_model(job_id)
    active_persona = custom_persona if custom_persona else DEFAULT_PERSONA
    system_prompt = build_system_prompt(active_persona, DEFAULT_STYLE)
    no_intro_directive = (
        "\n\nIMPORTANT: You have already introduced yourself in this session. "
        "Do NOT repeat your name, title, or role. Answer directly in character."
    )
    # [BUG #20 FIX] Inject directive inside </system>
    if introduced:
        active_system = system_prompt.replace("</system>", f"{no_intro_directive}\n</system>")
    else:
        active_system = system_prompt

    if _IDENTITY_TRIGGERS.match(question):
        identity_context = (
            f"The assistant's role and identity is as follows: {active_persona}\n\n"
            f"When asked about their identity, the assistant should introduce themselves "
            f"based on this role description."
        )
        messages = [
            {"role": "system", "content": active_system},
            {"role": "user",   "content": RAG_USER_TEMPLATE.format(context=identity_context, question="Who are you and what can you help me with?")},
        ]
        context = identity_context
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
        # [TEMPERATURE FIX] Use dynamic temperature instead of hardcoded 0.3
        "temperature": temperature,
        "do_sample": True,
        "pad_token_id": tokenizer.eos_token_id,
        "streamer": streamer,
    }

    # [BUG #19 FIX] Surface thread exceptions
    err_queue = queue.Queue()
    def generate_with_error_capture(**kwargs):
        try:
            model.generate(**kwargs)
        except Exception as e:
            err_queue.put(e)
            # Unblock the streamer queue so it doesn't hang forever
            if hasattr(streamer, 'text_queue'):
                streamer.text_queue.put(streamer.stop_signal)

    thread = threading.Thread(target=generate_with_error_capture, kwargs=generation_kwargs)
    thread.start()

    for new_text in streamer:
        if new_text.strip():
            yield {"token": new_text}

    thread.join()
    
    # Check if thread crashed
    if not err_queue.empty():
        exc = err_queue.get()
        yield {"token": f"\n\n[ERROR DURING GENERATION: {str(exc)}]"}
        
    yield {"citations": citations, "done": True}