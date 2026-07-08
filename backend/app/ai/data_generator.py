import os
import re
import json
import time
import logging
from groq import Groq
import chromadb
from typing import List, Dict

# ─── USE CASE PROFILES (FROM AI TEAM) ────────────────────────────────────────
USE_CASE_PROFILES = {
    "education": {
        "data_mix": (
            "Generate a mix of:\n"
            "- Theoretical recall (definitions, facts)\n"
            "- Analytical 'why/how' questions explaining mechanisms and cause-effect\n"
            "- Process questions (step-by-step sequences)\n"
            "- Comparative questions (contrast two concepts)\n"
            "At least 50% must be analytical, process, or comparative."
        ),
        "style_directive": (
            "When answering analytical questions, explain the mechanism or consequence "
            "in detail. For theoretical questions, define precisely and give significance. "
            "Structure complex answers in 2-3 clear sentences."
        ),
    },
    "business": {
        "data_mix": (
            "Generate a mix of:\n"
            "- Strategic analysis (decisions, trade-offs)\n"
            "- Process and operational questions\n"
            "- Definition questions (key business terms)\n"
            "- Cause-effect questions\n"
            "Prioritize questions that require reasoning over recall."
        ),
        "style_directive": (
            "Answer in a professional, structured tone. Explain rationale for strategic "
            "questions. Describe sequences clearly for process questions."
        ),
    },
    "finance": {
        "data_mix": (
            "Generate a mix of:\n"
            "- Definition questions (instruments, ratios, regulations)\n"
            "- Methodology questions (calculations, valuations)\n"
            "- Risk/return analysis\n"
            "- Regulatory and compliance questions\n"
            "- Comparative questions between instruments\n"
            "Explain numerical concepts by mechanism, not just formula."
        ),
        "style_directive": (
            "Be precise with financial terminology. Explain logic step by step for "
            "calculations. Name specific risk factors. Note jurisdiction-specific limits."
        ),
    },
    "medical": {
        "data_mix": (
            "Generate a mix of:\n"
            "- Clinical definitions\n"
            "- Mechanism questions (how drugs/processes work)\n"
            "- Symptom and diagnostic questions\n"
            "- Treatment rationale\n"
            "- Contraindication and safety questions\n"
            "All answers grounded strictly in the chunk."
        ),
        "style_directive": (
            "Use precise medical terminology. Describe biological/pharmacological "
            "processes for mechanism questions. Always append: consult a qualified "
            "healthcare professional before making any medical decisions."
        ),
    },
    "legal": {
        "data_mix": (
            "Generate a mix of:\n"
            "- Legal definitions\n"
            "- Principle explanation (rationale behind a rule)\n"
            "- Procedural questions (steps to follow)\n"
            "- Application questions (how a rule applies)\n"
            "- Jurisdictional boundary questions\n"
            "Every answer grounded exactly in the chunk."
        ),
        "style_directive": (
            "Be exact with legal definitions. Enumerate procedural steps clearly. "
            "Note jurisdictional limits explicitly. Always append: consult a qualified "
            "legal professional for advice specific to your situation."
        ),
    },
    "general": {
        "data_mix": (
            "Generate a balanced mix of:\n"
            "- Factual recall\n"
            "- Explanatory 'what/how/why' questions\n"
            "- Simple analytical questions"
        ),
        "style_directive": (
            "Answer clearly and concisely. Give the key reason or mechanism for "
            "explanatory questions. State facts directly for factual questions."
        ),
    },
}

# ─── SYSTEM INSTRUCTIONS & REGEX (FROM AI TEAM) ──────────────────────────────
SYSTEM_INSTRUCTION = """\
You are an expert Data Engineer creating high-quality instruction-tuning datasets \nfor a Small Language Model (SLM).\n\n
Extract knowledge from the DOCUMENT CHUNK and generate accurate, diverse Q&A pairs.\n\n
TARGET PERSONA FOR THE SLM:\n
{persona}\n\n
DOMAIN-SPECIFIC DATA MIX:\n
{data_mix}\n\n
UNIVERSAL RULES:\n
1. CONTAINMENT: Incoherent or fragmented chunk? Return empty data array.\n
2. ANTI-HALLUCINATION: Only generate questions answerable from this chunk alone.\n
   Do not use any knowledge beyond what is explicitly stated in the chunk.\n
3. CLEAN CITATIONS (CRITICAL): DO NOT output any pre-existing academic reference numbers or footnotes found inside the raw text (e.g., [1], (Author, 2020)).\n   Instead, you MUST explicitly append the label `[Source: document chunk]` to the facts you synthesize.\n
4. ANTI-CIRCULAR: Answers must NEVER restate the question. Add specific mechanisms,\n
   reasons, or consequences not already present in the question.\n
5. NEGATIVE EXAMPLE: Exactly ONE pair where a plausible topic is absent from the chunk.\n
   Answer must be exactly: "This information is not available in the provided document."\n
6. FORCED ROLEPLAY (CRITICAL): Write every "output" in the first-person voice of the\n
   TARGET PERSONA. Embed tone, vocabulary, and style into every answer.\n
   The SLM must learn to BE the persona, not just answer correctly.\n
7. ANALYTICAL DEPTH: Minimum 2-4 sentences per answer (except the negative example).\n
   Explain context, mechanism, or significance — never give 1-word answers.\n
8. TONE (CRITICAL): DO NOT start any output with a greeting or self-introduction.\n
   Never begin with "I am [name]", "As [role]", "Hello", or any preamble.\n
   Start every answer with the actual content immediately.\n\n
TARGET: Generate {n} pairs total (including the one negative example).\n\n
OUTPUT FORMAT:\n
Return a single JSON object containing:\n
{{"data": [{{"instruction": "...", "output": "..."}}]}}\n
No markdown. No introductory text. The word "json" is lowercase.\n
"""

_REF_PATTERN = re.compile(
    r'\[\d+\]|arXiv|et al\.|In Proceedings|pp\. \d+|doi:|ISBN|vol\. \d+',
    re.IGNORECASE
)

# ─── HELPER FUNCTIONS (FROM AI TEAM) ─────────────────────────────────────────

def _is_circular(instruction: str, output: str) -> bool:
    stop = {"the","and","for","are","was","were","that","this",
            "with","from","have","has","had","been","its","not"}
    inst_w = {w.lower().strip(".,?!\"'") for w in instruction.split()
              if len(w) > 3 and w.lower() not in stop}
    out_w  = [w.lower().strip(".,?!\"'") for w in output.split()
              if len(w) > 3 and w.lower() not in stop]
    if not out_w:
        return True
    return (sum(1 for w in out_w if w in inst_w) / len(out_w)) > 0.60

def _is_grounded(chunk: str, output: str) -> bool:
    NEGATIVE_ANSWER = "This information is not available in the provided document."
    if output.strip() == NEGATIVE_ANSWER:
        return True

    stop = {"the","and","for","are","was","were","that","this","with","from",
            "have","has","had","been","its","not","also","their","they","which",
            "will","more","such","each","been","into","than","these","those"}

    chunk_words = {w.lower().strip(".,?!\"'()[]") for w in chunk.split() 
                   if len(w) > 4 and w.lower() not in stop}
    output_words = [w.lower().strip(".,?!\"'()[]") for w in output.split() 
                    if len(w) > 4 and w.lower() not in stop]

    if not output_words:
        return False

    overlap = sum(1 for w in output_words if w in chunk_words)
    word_overlap_pass = (overlap / len(output_words)) > 0.40 and overlap >= 2

    if not word_overlap_pass:
        return False

    # [P2.1] Embedding-based semantic grounding check (§3.3)
    # Reuses the already-loaded SentenceTransformer — zero additional VRAM cost
    try:
        from app.ai.rag_inference import get_embedder
        embedder = get_embedder()
        embeddings = embedder.encode([chunk[:1000], output], normalize_embeddings=True)
        cosine_sim = float(embeddings[0] @ embeddings[1])
        if cosine_sim < 0.5:
            logging.getLogger(__name__).debug(
                f"Grounding filter: cosine_sim={cosine_sim:.3f} < 0.5 — rejected paraphrased hallucination"
            )
            return False
    except Exception:
        pass  # If embedder unavailable, fall back to word-overlap result only

    return True

def dynamic_pair_count(chunk: str) -> int:
    words = len(chunk.split())
    base  = max(2, min(10, words // 50))
    return base

def assemble_final_persona(user_input: str = None) -> str:
    """Wraps the user's custom persona in the AI team's strict guardrails."""
    if not user_input:
        user_input = (
            "You are an expert AI assistant for the content of this document.\n"
            "You explain concepts clearly and concisely."
        )

    return (
        "You are a highly capable AI domain expert.\n"
        "Strictly adopt the following persona provided by the user:\n\n"
        "[START USER DEFINED PERSONA]\n"
        f"{user_input.strip()}\n"
        "[END USER DEFINED PERSONA]\n\n"
        "UNBREAKABLE BOUNDARIES:\n"
        "- Answer entirely in the first-person voice of the role above.\n"
        "- Never break character or remind the user you are an AI.\n"
        "- If the context does not contain the answer, refuse politely in character:\n"
        "  'This information is not available in the provided document.'\n"
        "- Never fabricate facts."
    )

def generate_pairs_from_chunk(
    chunk: str,
    chunk_index: int,
    persona: str,
    data_mix: str,
    groq_client,
    few_shot_examples: List[Dict[str, str]] = None,
    retries: int = 4
) -> list:
    n = dynamic_pair_count(chunk)

    # ─── Format few-shot examples for the prompt ─────────────────────────────
    few_shot_text = ""
    if few_shot_examples:
        few_shot_text = "\n\nEXAMPLES OF DESIRED STYLE (follow this tone and format exactly):\n\n"
        for example_dict in few_shot_examples:
            for question, answer in example_dict.items():
                few_shot_text += f"USER: {question}\nASSISTANT: {answer}\n\n"

    system_content = SYSTEM_INSTRUCTION.format(
        persona=persona,
        data_mix=data_mix,
        n=n
    ) + few_shot_text  # Append examples to system prompt

    for attempt in range(retries):
        try:
            response = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system_content},
                    {"role": "user",   "content": f"DOCUMENT CHUNK:\n{chunk}"}
                ],
                response_format={"type": "json_object"},
                temperature=0.65,
            )

            raw  = response.choices[0].message.content
            data = json.loads(raw)

            if isinstance(data, dict):
                pairs = data.get("data") or next((v for v in data.values() if isinstance(v, list)), [])
            elif isinstance(data, list):
                pairs = data
            else:
                raise ValueError(f"Unexpected JSON structure: {type(data)}")

            valid = []
            for p in pairs:
                if not (isinstance(p, dict) and isinstance(p.get("instruction"), str) and 
                        isinstance(p.get("output"), str) and len(p["instruction"].strip()) > 5 and 
                        len(p["output"].strip()) > 10):
                    continue
                if _REF_PATTERN.search(p["output"]):
                    continue
                if _is_circular(p["instruction"], p["output"]):
                    continue
                if not _is_grounded(chunk, p["output"]):
                    continue   

                valid.append({
                    "context":     chunk.strip(),
                    "instruction": p["instruction"].strip(),
                    "output":      p["output"].strip(),
                })

            print(f"  Chunk {chunk_index+1} ({len(chunk.split())} words → target {n}): {len(valid)} valid pairs.")
            return valid

        except Exception as e:
            wait = 2 ** (attempt + 1)
            print(f"  ⚠️  Chunk {chunk_index+1} attempt {attempt+1} failed: {e}. Retry in {wait}s…")
            time.sleep(wait)

    print(f"  ❌ Chunk {chunk_index+1} permanently failed. Skipping.")
    return []

# ─── MAIN BACKEND ROUTER ─────────────────────────────────────────────────────

def generate_finetuning_data(
    project_id: str,
    job_id: str,
    use_case: str,
    persona: str = None,
    few_shot_examples: List[Dict[str, str]] = None,
    **kwargs
):
    """
    Backend Entry Point for Phase 2.
    [PROJECT REFACTOR] Now accepts project_id instead of dataset_id for project-scoped collection lookup.
    Added **kwargs defensively to absorb any extra variables tasks.py might pass.
    """
    print(f"\n🎯 Generating fine-tuning data [use_case={use_case}] via Groq...")

    # 1. Setup API & DB Clients
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY not set in .env file")
    groq_client = Groq(api_key=api_key)

    use_case_lower = (use_case or "general").lower()
    profile = USE_CASE_PROFILES.get(use_case_lower, USE_CASE_PROFILES["general"])

    # Apply the custom persona passed from the frontend UI
    wrapped_persona = assemble_final_persona(persona)

    # [PROJECT REFACTOR] Use project-scoped collection path
    chroma_dir = f"data/vector_stores/project_{project_id}"
    if not os.path.exists(chroma_dir):
        raise FileNotFoundError(f"Vector directory {chroma_dir} not found. Ingest a document first.")

    client = chromadb.PersistentClient(path=chroma_dir)
    collection = client.get_collection(name=f"docs_{project_id}")
    db_data = collection.get(include=["documents"])
    all_chunks = db_data.get("documents", [])

    if not all_chunks:
        raise ValueError(f"No documents found in vector store docs_{project_id}")

    # 2. Dynamic Sampling (AI Team Logic)
    valid_chunks = [
        chunk for chunk in all_chunks
        if len(chunk.split()) >= 100
        and (sum(c.isalpha() for c in chunk) / max(len(chunk), 1)) > 0.40
    ]
    target_chunks = max(50, min(250, int(len(valid_chunks) * 0.25)))

    if len(valid_chunks) > target_chunks:
        step = len(valid_chunks) / target_chunks
        ft_chunks = [valid_chunks[int(i * step)] for i in range(target_chunks)]
    else:
        ft_chunks = valid_chunks

    print(f"   Total valid chunks (≥100 words): {len(valid_chunks)}")
    print(f"   Sampled for training           : {len(ft_chunks)} (25% even sample)\n")

    # 3. Generation Loop
    all_pairs = []
    for i, chunk in enumerate(ft_chunks):  # ← INDENT THIS LINE + EVERYTHING BELOW IT
        pairs = generate_pairs_from_chunk(
            chunk, i, wrapped_persona, profile["data_mix"],
            groq_client, few_shot_examples=few_shot_examples
        )
        all_pairs.extend(pairs)
        time.sleep(0.5)

    # 4. Deduplicate
    seen, unique = set(), []
    for p in all_pairs:
        key = p["instruction"].lower()
        if key not in seen:
            seen.add(key)
            unique.append(p)

    # 5. Save Output
    output_dir = f"data/processed/job_{job_id}"
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, "train.jsonl")

    with open(output_file, "w", encoding="utf-8") as f:
        for entry in unique:
            json.dump(entry, f, ensure_ascii=False)
            f.write("\n")

    print(f"\n✅ Saved {len(unique)} unique training pairs to '{output_file}'.")