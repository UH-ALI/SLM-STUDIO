import os
import json
import time
from pypdf import PdfReader
from groq import Groq  # <-- Switched from google.genai
from dotenv import load_dotenv

# ─── CONFIG ──────────────────────────────────────────────────────────────────

load_dotenv()
# The variable name in your .env should now be GROQ_API_KEY
api_key = os.getenv("GROQ_API_KEY") 
if not api_key:
    raise RuntimeError("GROQ_API_KEY not set in .env file")

PDF_PATH        = "data.pdf"
OUTPUT_FILE     = "train.jsonl"
CHUNK_SIZE      = 6000   
CHUNK_OVERLAP   = 500    
PAIRS_PER_CHUNK = 15     
MAX_CHUNKS      = 20     

# ─── PDF EXTRACTION ──────────────────────────────────────────────────────────

def extract_pdf_text(filepath: str) -> str:
    reader = PdfReader(filepath)
    pages = [page.extract_text() or "" for page in reader.pages]
    full_text = "\n".join(pages)
    print(f"✅ Extracted {len(full_text):,} characters from {len(pages)} pages.")
    return full_text

# ─── CHUNKING ────────────────────────────────────────────────────────────────

def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    print(f"📦 Split into {len(chunks)} chunks.")
    return chunks

# ─── TEACHER PROMPT ──────────────────────────────────────────────────────────

SYSTEM_INSTRUCTION = """
You are an SLM Training Expert. Generate exactly {n} training examples from the provided text.
Return the output as a JSON array of objects with "instruction" and "output" keys.

REQUIRED MIX:
- 60% FACTUAL: Direct questions grounded in text.
- 20% REFUSAL: Questions about things NOT in text. Response: "This information is not available in the provided document."
- 20% BOUNDARY: Slightly off-topic, redirect back.
"""

# ─── GROQ CALL WITH RETRY ───────────────────────────────────────────────────

client = Groq(api_key=api_key)

def generate_pairs_from_chunk(chunk: str, chunk_index: int, retries: int = 3) -> list[dict]:
    """Call Groq Llama 3 on a single chunk."""
    prompt = f"DOCUMENT CHUNK:\n{chunk}"

    for attempt in range(retries):
        try:
            # Using llama-3.3-70b for high-quality data generation
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": SYSTEM_INSTRUCTION.format(n=PAIRS_PER_CHUNK)},
                    {"role": "user", "content": prompt}
                ],
                # Groq uses response_format for JSON mode
                response_format={"type": "json_object"}
            )
            
            # Groq returns a string in content; we parse it to a list
            raw_content = response.choices[0].message.content
            data = json.loads(raw_content)
            
            # Handle cases where the model wraps the list in a key like {"examples": [...]}
            if isinstance(data, dict):
                for val in data.values():
                    if isinstance(val, list):
                        pairs = val
                        break
            else:
                pairs = data

            print(f"  Chunk {chunk_index+1}: generated {len(pairs)} pairs.")
            return pairs

        except Exception as e:
            wait = 2 ** (attempt + 1)
            print(f"  ⚠️ Attempt {attempt+1} failed: {e}. Retrying in {wait}s...")
            time.sleep(wait)

    return []

# ─── MAIN PIPELINE ───────────────────────────────────────────────────────────

def run_pipeline():
    raw_text = extract_pdf_text(PDF_PATH)
    chunks = chunk_text(raw_text, CHUNK_SIZE, CHUNK_OVERLAP)[:MAX_CHUNKS]
    
    print(f"🎯 Processing {len(chunks)} chunks via Groq (Llama 3)...\n")

    all_pairs = []
    for i, chunk in enumerate(chunks):
        pairs = generate_pairs_from_chunk(chunk, i)
        all_pairs.extend(pairs)
        # Groq is fast, but let's keep a tiny sleep to be safe with rate limits
        time.sleep(0.5) 

    # Deduplicate
    seen = set()
    unique_pairs = []
    for pair in all_pairs:
        # Safety check for malformed pairs
        if "instruction" in pair and "output" in pair:
            key = pair["instruction"].strip().lower()
            if key not in seen:
                seen.add(key)
                unique_pairs.append(pair)

    # Save
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for entry in unique_pairs:
            json.dump(entry, f, ensure_ascii=False)
            f.write("\n")

    print(f"\n✅ DONE. Saved {len(unique_pairs)} training pairs to '{OUTPUT_FILE}'.")

if __name__ == "__main__":
    run_pipeline()