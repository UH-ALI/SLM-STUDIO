"""
rag_inference.py
No-Code SLM Studio — RAG + Fine-Tuned SLM Inference
This is the MISSING piece that connects your fine-tuned adapter with ChromaDB retrieval.
"""

import torch
import os
from dotenv import load_dotenv

# ─── CONFIG ──────────────────────────────────────────────────────────────────

load_dotenv()

USE_CASE      = "business"                           # must match what you trained
BASE_MODEL    = "unsloth/Qwen2.5-1.5B-Instruct-bnb-4bit"
ADAPTER_PATH  = f"./adapter_{USE_CASE}/lora_adapter"
PDF_PATH      = "data.pdf"
CHROMA_DIR    = f"./chroma_{USE_CASE}"               # persistent ChromaDB storage
COLLECTION    = f"docs_{USE_CASE}"
TOP_K         = 3                                    # number of chunks to retrieve
CHUNK_SIZE    = 400                                  # characters per chunk for RAG
CHUNK_OVERLAP = 50

# ─── STEP 1: BUILD VECTOR STORE (run once per document) ──────────────────────

def build_vector_store():
    """Extract PDF, chunk it, embed it, store in ChromaDB. Run once."""
    import chromadb
    from pypdf import PdfReader

    print("📚 Building vector store from PDF...")

    # Extract text
    reader = PdfReader(PDF_PATH)
    full_text = "\n".join(page.extract_text() or "" for page in reader.pages)

    # Chunk
    chunks = []
    start = 0
    while start < len(full_text):
        end = start + CHUNK_SIZE
        chunks.append(full_text[start:end])
        start += CHUNK_SIZE - CHUNK_OVERLAP
    print(f"   Created {len(chunks)} chunks.")

    # Embed — MiniLM runs on CPU, no GPU needed
    embedder = get_embedder()
    embeddings = embedder.encode(chunks, show_progress_bar=True, batch_size=64)

    # Store in ChromaDB
    client = chromadb.PersistentClient(path=CHROMA_DIR)

    # Delete existing collection if rebuilding
    try:
        client.delete_collection(COLLECTION)
    except Exception:
        pass

    collection = client.create_collection(COLLECTION)
    collection.add(
        documents=chunks,
        embeddings=embeddings.tolist(),
        ids=[f"chunk_{i}" for i in range(len(chunks))]
    )

    print(f"✅ Vector store built. {len(chunks)} chunks stored in '{CHROMA_DIR}'.")

# ─── STEP 2: LOAD FINE-TUNED MODEL ───────────────────────────────────────────

def load_finetuned_model():
    """Load base model + LoRA adapter for inference."""
    from unsloth import FastLanguageModel

    if not os.path.exists(ADAPTER_PATH):
        raise FileNotFoundError(
            f"Adapter not found at '{ADAPTER_PATH}'. Run finetune_v2.py first."
        )

    print(f"\n⏳ Loading fine-tuned model ({USE_CASE})...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=ADAPTER_PATH,   # Unsloth auto-detects: base model + adapter
        max_seq_length=1024,
        dtype=None,
        load_in_4bit=True,
    )
    FastLanguageModel.for_inference(model)  # optimized inference mode
    print("✅ Model loaded.")
    return model, tokenizer

# ─── STEP 3: RAG RETRIEVAL ───────────────────────────────────────────────────

def retrieve_context(query: str, top_k: int = TOP_K) -> str:
    """Retrieve the most relevant chunks from ChromaDB for a given query."""
    import chromadb

    embedder = get_embedder()
    query_embedding = embedder.encode([query])[0].tolist()

    client = chromadb.PersistentClient(path=CHROMA_DIR)
    collection = client.get_collection(COLLECTION)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k
    )

    # Join the top-k retrieved chunks into a single context block
    retrieved_chunks = results["documents"][0]
    context = "\n\n---\n\n".join(retrieved_chunks)
    return context

# ─── STEP 4: GENERATE ANSWER ─────────────────────────────────────────────────

RAG_PROMPT_TEMPLATE = """You are a knowledgeable assistant. Answer the user's question using ONLY the context below.
If the answer is not in the context, say "This information is not available in the provided document."
Do not make up information.

CONTEXT:
{context}

QUESTION:
{question}

ANSWER:"""

# Cached embedder — loaded once, reused for every query
_embedder = None

def get_embedder():
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer
        _embedder = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedder

def answer_question(model, tokenizer, question: str) -> str:
    """Retrieve context and generate an answer using the fine-tuned model."""

    # Retrieve relevant context
    context = retrieve_context(question)

    # Build RAG prompt
    prompt = RAG_PROMPT_TEMPLATE.format(context=context, question=question)

    messages = [{"role": "user", "content": prompt}]
    inputs = tokenizer.apply_chat_template(
        messages,
        tokenize=True,
        add_generation_prompt=True,
        return_tensors="pt"
    ).to("cuda")

    with torch.no_grad():
        output_ids = model.generate(
            input_ids=inputs,
            max_new_tokens=300,
            temperature=0.3,    # lower temp = more factual, less creative
            do_sample=True,
            pad_token_id=tokenizer.eos_token_id,
        )

    # Decode only the new tokens (not the prompt)
    new_tokens = output_ids[0][inputs.shape[1]:]
    answer = tokenizer.decode(new_tokens, skip_special_tokens=True)
    return answer.strip()

# ─── STEP 5: CHAT LOOP ───────────────────────────────────────────────────────

def chat_loop(model, tokenizer):
    print(f"\n🤖 No-Code SLM Studio — {USE_CASE.title()} Assistant")
    print("   Type your question. Type 'quit' to exit.\n")

    while True:
        question = input("You: ").strip()
        if not question or question.lower() in ("quit", "exit", "q"):
            print("Goodbye.")
            break

        answer = answer_question(model, tokenizer, question)
        print(f"\nAssistant: {answer}\n")

# ─── MAIN ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    # Pass --build flag to (re)build vector store from PDF
    if "--build" in sys.argv:
        build_vector_store()
    elif not os.path.exists(CHROMA_DIR):
        print(f"⚠️  Vector store not found at '{CHROMA_DIR}'. Run with --build first.")
        print("   Example: python rag_inference.py --build")
        sys.exit(1)

    model, tokenizer = load_finetuned_model()
    chat_loop(model, tokenizer)
