"""
data_generator_v2.py
No-Code SLM Studio — Teacher Model Pipeline
Fixes: chunking, volume, retry logic, progress tracking
"""

import os
import json
import time
from pypdf import PdfReader
from google import genai
from google.genai import types
from dotenv import load_dotenv

# ─── CONFIG ──────────────────────────────────────────────────────────────────

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise RuntimeError("GOOGLE_API_KEY not set in .env file")

PDF_PATH       = "data.pdf"
OUTPUT_FILE    = "train.jsonl"
CHUNK_SIZE     = 6000   # characters per chunk (~1500 tokens) — safe for Gemini
CHUNK_OVERLAP  = 500    # overlap so context isn't lost at boundaries
PAIRS_PER_CHUNK = 15    # Q&A pairs to generate per chunk
MAX_CHUNKS     = 20     # cap at 20 chunks = 300 pairs max (more than enough)

# ─── PDF EXTRACTION ──────────────────────────────────────────────────────────

def extract_pdf_text(filepath: str) -> str:
    reader = PdfReader(filepath)
    pages = [page.extract_text() or "" for page in reader.pages]
    full_text = "\n".join(pages)
    print(f"✅ Extracted {len(full_text):,} characters from {len(pages)} pages.")
    return full_text

# ─── CHUNKING ────────────────────────────────────────────────────────────────

def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split text into overlapping chunks. Never truncates — processes everything."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap  # slide forward with overlap
    print(f"📦 Split into {len(chunks)} chunks ({chunk_size} chars each, {overlap} overlap).")
    return chunks

# ─── TEACHER PROMPT ──────────────────────────────────────────────────────────

SYSTEM_INSTRUCTION = """
You are an SLM Training Expert. Your job is to generate high-quality fine-tuning
data from a document chunk. Generate exactly {n} training examples.

REQUIRED MIX:
- 60% FACTUAL: Direct questions with answers grounded strictly in the text.
- 20% REFUSAL: Questions about things NOT in the text.
  Response MUST be exactly: "This information is not available in the provided document."
- 20% BOUNDARY: Slightly off-topic questions. Response redirects back to what IS available.

STRICT RULES:
- Never fabricate facts. If it's not in the text, refuse.
- Answers must be concise and direct — no "Based on the text..." preambles.
- Questions must sound like what a real user would actually ask.
- Vary question phrasing: What, How, Why, Explain, List, Compare.
"""

# ─── GEMINI CALL WITH RETRY ──────────────────────────────────────────────────

client = genai.Client(api_key=api_key)

def generate_pairs_from_chunk(chunk: str, chunk_index: int, retries: int = 3) -> list[dict]:
    """Call Gemini on a single chunk. Retries on failure."""
    prompt = SYSTEM_INSTRUCTION.format(n=PAIRS_PER_CHUNK) + f"\n\nDOCUMENT CHUNK:\n{chunk}"

    for attempt in range(retries):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",  # Flash is free tier, fast, and sufficient
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema={
                        "type": "ARRAY",
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "instruction": {"type": "STRING"},
                                "output": {"type": "STRING"}
                            },
                            "required": ["instruction", "output"]
                        }
                    }
                )
            )
            pairs = json.loads(response.text)
            print(f"  Chunk {chunk_index+1}: generated {len(pairs)} pairs.")
            return pairs

        except Exception as e:
            wait = 2 ** attempt  # exponential backoff: 1s, 2s, 4s
            print(f"  ⚠️  Chunk {chunk_index+1} attempt {attempt+1} failed: {e}. Retrying in {wait}s...")
            time.sleep(wait)

    print(f"  ❌ Chunk {chunk_index+1} failed after {retries} attempts. Skipping.")
    return []

# ─── MAIN PIPELINE ───────────────────────────────────────────────────────────

def run_pipeline():
    # Step 1: Extract
    raw_text = extract_pdf_text(PDF_PATH)

    # Step 2: Chunk — process the WHOLE document, not just first 40k chars
    chunks = chunk_text(raw_text, CHUNK_SIZE, CHUNK_OVERLAP)
    chunks = chunks[:MAX_CHUNKS]  # cap total if document is enormous
    print(f"🎯 Processing {len(chunks)} chunks → target ~{len(chunks) * PAIRS_PER_CHUNK} pairs.\n")

    # Step 3: Generate pairs from each chunk
    all_pairs = []
    for i, chunk in enumerate(chunks):
        pairs = generate_pairs_from_chunk(chunk, i)
        all_pairs.extend(pairs)
        time.sleep(1)  # respect Gemini free tier rate limit (15 req/min)

    # Step 4: Deduplicate by instruction text
    seen = set()
    unique_pairs = []
    for pair in all_pairs:
        key = pair["instruction"].strip().lower()
        if key not in seen:
            seen.add(key)
            unique_pairs.append(pair)

    # Step 5: Save as JSONL
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for entry in unique_pairs:
            json.dump(entry, f, ensure_ascii=False)
            f.write("\n")

    print(f"\n✅ DONE. Saved {len(unique_pairs)} unique training pairs to '{OUTPUT_FILE}'.")
    print(f"   (Removed {len(all_pairs) - len(unique_pairs)} duplicates.)")

    # Step 6: Quick sanity check — print 3 examples
    print("\n── Sample examples ──────────────────────────────────")
    for pair in unique_pairs[:3]:
        print(f"Q: {pair['instruction']}")
        print(f"A: {pair['output'][:120]}...")
        print()

if __name__ == "__main__":
    run_pipeline()
