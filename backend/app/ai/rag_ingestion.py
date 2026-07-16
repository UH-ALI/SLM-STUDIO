import os
import re
import logging
from pathlib import Path
import chromadb
from sentence_transformers import SentenceTransformer
import pymupdf4llm
from markitdown import MarkItDown

logger = logging.getLogger(__name__)

# ─── CONFIG & REGEX (From AI Team) ───────────────────────────────────────────
CHUNK_SIZE    = 1500   # soft target in characters
CHUNK_OVERLAP = 2      # sentences to carry into next chunk (sentence-mode fallback)

_HEADER_PATTERN = re.compile(r'^(#{1,4})\s+(.+)$', re.MULTILINE)
_SENTENCE_END   = re.compile(r'(?<=[.!?])\s+')
_TABLE_ROW      = re.compile(r'^\s*\|')
_REF_PATTERN    = re.compile(
    r'\[\d+\]|arXiv|et al\.|In Proceedings|pp\. \d+|doi:|ISBN|vol\. \d+',
    re.IGNORECASE
)

# ─── HYBRID CHUNKER LOGIC (From AI Team) ─────────────────────────────────────

def _sentence_split(text: str, current_header: str) -> list:
    sentences  = _SENTENCE_END.split(text.strip())
    sentences  = [s.strip() for s in sentences if s.strip()]
    chunks, current, cur_len = [], [], 0
    prefix     = f"{current_header}\n\n" if current_header else ""
    prefix_len = len(prefix)

    for sentence in sentences:
        slen = len(sentence) + 1
        if cur_len + slen > CHUNK_SIZE - prefix_len and current:
            chunks.append(prefix + " ".join(current))
            carry   = current[-CHUNK_OVERLAP:] if CHUNK_OVERLAP > 0 else []
            current = carry
            cur_len = sum(len(s) + 1 for s in current)
        current.append(sentence)
        cur_len += slen

    if current:
        chunks.append(prefix + " ".join(current))
    return chunks


def _table_safe_split(text: str, current_header: str) -> list:
    lines    = text.split('\n')
    result   = []
    buffer   = []
    in_table = False

    for line in lines:
        is_table_line = bool(_TABLE_ROW.match(line))
        if is_table_line:
            in_table = True
            buffer.append(line)
        else:
            if in_table:
                in_table = False
                result.append(('table', '\n'.join(buffer)))
                buffer = []
            buffer.append(line)

    if buffer:
        result.append(('text', '\n'.join(buffer)))

    final_chunks = []
    for kind, block in result:
        if kind == 'table':
            prefix = f"{current_header}\n\n" if current_header else ""
            final_chunks.append(prefix + block)
        else:
            final_chunks.extend(_sentence_split(block, current_header))

    return final_chunks


def hybrid_chunk_markdown(md_text: str) -> list:
    headers = list(_HEADER_PATTERN.finditer(md_text))

    if not headers:
        chunks = _table_safe_split(md_text, "")
        return [(c, "") for c in chunks if c.strip()]

    sections = []
    for i, match in enumerate(headers):
        header_name  = match.group(2).strip()
        start        = match.start()
        end          = headers[i + 1].start() if i + 1 < len(headers) else len(md_text)
        section_body = md_text[start:end]
        sections.append((header_name, section_body))

    result = []
    for header_name, section_body in sections:
        if len(section_body) <= CHUNK_SIZE:
            if section_body.strip():
                result.append((section_body.strip(), header_name))
        else:
            sub_chunks = _table_safe_split(section_body, f"## {header_name}")
            for sub in sub_chunks:
                if sub.strip():
                    result.append((sub.strip(), header_name))

    return result


def is_reference_chunk(chunk: str) -> bool:
    lines     = [l.strip() for l in chunk.split('\n') if l.strip()]
    if not lines:
        return True
    ref_lines = sum(1 for l in lines if _REF_PATTERN.search(l))
    return (ref_lines / len(lines)) > 0.35


# ─── MAIN BACKEND ROUTER ─────────────────────────────────────────────────────

def process_and_ingest_document(project_id: str, dataset_id: str, file_path: str):
    """
    Backend Entry Point for Phase 1.
    Extracts text, chunks it using AI team logic, and saves to persistent ChromaDB.

    [PROJECT REFACTOR] Now accepts project_id for project-scoped collection naming.
    Collection path: data/vector_stores/project_{project_id}
    Collection name: docs_{project_id}

    [MULTI-FILE FIX] Chunk IDs include dataset_id to prevent collisions
    when multiple files with the same name are uploaded to the same project.

    If project_id is None, falls back to legacy dataset-scoped naming for backward compatibility.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Cannot find {file_path}")

    # 1. Extract Markdown (format-aware)
    print(f"Extracting Markdown from: {path.name}")
    try:
        if path.suffix.lower() == ".pdf":
            md_text = pymupdf4llm.to_markdown(str(path))
            word_count = len(md_text.split())
            if word_count < 80:
                raise ValueError(
                    f"'{path.name}' appears to be a scanned/image-only PDF "
                    f"(extracted only {word_count} words). "
                    "Please upload a text-layer PDF or convert it to DOCX first."
                )
        else:
            md = MarkItDown()
            result = md.convert(str(path))
            md_text = result.text_content
    except Exception as e:
        raise ValueError(f"Failed to extract text from {path.name}: {str(e)}")

    # 2. Hybrid Chunking
    chunk_tuples = hybrid_chunk_markdown(md_text)
    usable_chunks = [
        (text, chapter) for text, chapter in chunk_tuples
        if len(text) > 120
        and not is_reference_chunk(text)
        and (sum(c.isalpha() for c in text) / len(text)) > 0.40
    ]

    docs, metadatas, ids = [], [], []
    for i, (text, chapter) in enumerate(usable_chunks):
        docs.append(text)
        metadatas.append({
            "source": path.name,
            "chapter": chapter or "General",
            "file_type": path.suffix.lower()
        })
        # [MULTI-FILE FIX] Include dataset_id in chunk ID to guarantee uniqueness
        # across multiple files with the same name in the same project collection.
        ids.append(f"{dataset_id}_{path.stem}_chunk_{i}")

    if not docs:
        raise ValueError("No usable chunks extracted from document.")

    # 3. Vectorization & Storage
    print(f"Embedding {len(docs)} chunks for Dataset {dataset_id}")
    embedder = SentenceTransformer("BAAI/bge-small-en-v1.5")
    embeddings = embedder.encode(docs, show_progress_bar=False, batch_size=64)

    # [PROJECT REFACTOR] Use project-scoped collection naming
    if project_id:
        chroma_dir = f"data/vector_stores/project_{project_id}"
        collection_name = f"docs_{project_id}"
    else:
        # Legacy fallback for backward compatibility
        chroma_dir = f"data/vector_stores/dataset_{dataset_id}"
        collection_name = f"docs_{dataset_id}"

    os.makedirs(chroma_dir, exist_ok=True)

    client = chromadb.PersistentClient(path=chroma_dir)
    collection = client.get_or_create_collection(name=collection_name, metadata={"hnsw:space": "cosine"})

    # upsert (not add): if this exact file is re-ingested, its chunk IDs overwrite
    # the old entries instead of raising a duplicate-ID error or creating duplicates.
    collection.upsert(
        documents=docs,
        embeddings=embeddings.tolist(),
        metadatas=metadatas,
        ids=ids
    )

    MAX_CHUNKS_PER_PROJECT = 2500  # ~350-500 pages of dense text
    total = collection.count()
    if total > MAX_CHUNKS_PER_PROJECT:
        # [P2.3] Surface as proper warning instead of silent print
        logger.warning(
            f"Project has {total} chunks (limit: {MAX_CHUNKS_PER_PROJECT}). "
            "Consider splitting into multiple projects for optimal retrieval quality."
        )

    logger.info(f"Vector store ready — {len(docs)} chunks saved to {chroma_dir}.")
    return True


def copy_vectors_across_projects(source_project_id: str, target_project_id: str, dataset_id: str):
    """
    Zero-compute vector reuse: copies existing embeddings from one project's
    ChromaDB collection into another project's collection, skipping the entire
    SentenceTransformer encode pipeline.

    Used when the same Dataset is linked to multiple projects — instead of
    re-running pymupdf4llm extraction + bge-small-en-v1.5 encoding (~30s),
    this copies the pre-computed vectors in < 50ms.

    Returns True if vectors were copied, False if source had no matching chunks.
    """
    source_dir = f"data/vector_stores/project_{source_project_id}"
    source_name = f"docs_{source_project_id}"

    if not os.path.exists(source_dir):
        logger.warning(f"Source vector store not found: {source_dir}")
        return False

    try:
        source_client = chromadb.PersistentClient(path=source_dir)
        source_collection = source_client.get_or_create_collection(
            name=source_name, metadata={"hnsw:space": "cosine"}
        )

        # Fetch only chunks belonging to this specific dataset
        # (chunk IDs are prefixed with dataset_id: "{dataset_id}_{stem}_chunk_{i}")
        all_data = source_collection.get(
            where=None,
            include=["documents", "embeddings", "metadatas"]
        )

        if not all_data["ids"]:
            logger.info("Source collection is empty — nothing to copy.")
            return False

        # Filter to only the chunks belonging to this dataset_id
        matching_indices = [
            i for i, chunk_id in enumerate(all_data["ids"])
            if chunk_id.startswith(f"{dataset_id}_")
        ]

        if not matching_indices:
            logger.info(f"No chunks found for dataset {dataset_id} in source collection.")
            return False

        # Extract matched data
        ids = [all_data["ids"][i] for i in matching_indices]
        docs = [all_data["documents"][i] for i in matching_indices]
        embeddings = [all_data["embeddings"][i] for i in matching_indices]
        metadatas = [all_data["metadatas"][i] for i in matching_indices]

        # Upsert into target project's collection
        target_dir = f"data/vector_stores/project_{target_project_id}"
        target_name = f"docs_{target_project_id}"
        os.makedirs(target_dir, exist_ok=True)

        target_client = chromadb.PersistentClient(path=target_dir)
        target_collection = target_client.get_or_create_collection(
            name=target_name, metadata={"hnsw:space": "cosine"}
        )

        target_collection.upsert(
            documents=docs,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids
        )

        logger.info(
            f"Zero-compute copy complete: {len(ids)} chunks copied "
            f"from project {source_project_id} → {target_project_id}."
        )
        return True

    except Exception as e:
        logger.error(f"Failed to copy vectors: {type(e).__name__}: {e}")
        return False