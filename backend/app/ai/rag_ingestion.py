import os
import re
import logging
from pathlib import Path
import chromadb
from sentence_transformers import SentenceTransformer
import pdfplumber
from markitdown import MarkItDown

logger = logging.getLogger("slm_worker")

CHUNK_SIZE    = 1500
CHUNK_OVERLAP = 2

_HEADER_PATTERN = re.compile(r'^(#{1,4})\s+(.+)$', re.MULTILINE)
_SENTENCE_END   = re.compile(r'(?<=[.!?])\s+')
_TABLE_ROW      = re.compile(r'^\s*\|')
_REF_PATTERN    = re.compile(r'\[\d+\]|arXiv|et al\.|In Proceedings|doi:', re.IGNORECASE)


def _sentence_split(text: str, current_header: str) -> list:
    sentences = _SENTENCE_END.split(text.strip())
    sentences = [s.strip() for s in sentences if s.strip()]
    chunks, current, cur_len = [], [], 0
    prefix = f"{current_header}\n\n" if current_header else ""
    prefix_len = len(prefix)

    for sentence in sentences:
        slen = len(sentence) + 1
        if cur_len + slen > CHUNK_SIZE - prefix_len and current:
            chunks.append(prefix + " ".join(current))
            carry = current[-CHUNK_OVERLAP:] if CHUNK_OVERLAP > 0 else []
            current = carry
            cur_len = sum(len(s) + 1 for s in current)
        current.append(sentence)
        cur_len += slen

    if current:
        chunks.append(prefix + " ".join(current))
    return chunks


def _table_safe_split(text: str, current_header: str) -> list:
    lines = text.split('\n')
    result, buffer, in_table = [], [], False

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
        header_name = match.group(2).strip()
        start = match.start()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(md_text)
        sections.append((header_name, md_text[start:end]))

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
    lines = [l.strip() for l in chunk.split('\n') if l.strip()]
    if not lines:
        return True
    ref_lines = sum(1 for l in lines if _REF_PATTERN.search(l))
    return (ref_lines / len(lines)) > 0.35


# ─── EXTRACTION & CHARACTER CHECK CLEANUP ────────────────────────────────────

def process_and_ingest_document(project_id: str, dataset_id: str, file_path: str):
    """Layout-aware extraction and vector store ingestion engine."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File payload missing at reference index: {file_path}")

    logger.info(f"Extracting text from: {path.name}")
    md_text = ""

    try:
        if path.suffix.lower() == ".pdf":
            extracted_pages = []
            with pdfplumber.open(path) as pdf:
                for page in pdf.pages:
                    # Clean up double spacing to protect character density calculations
                    text = page.extract_text()
                    if text:
                        # Normalize irregular whitespace margins typical in government documents
                        clean_text = "\n".join([line.strip() for line in text.split("\n") if line.strip()])
                        extracted_pages.append(clean_text)
            
            md_text = "\n\n".join(extracted_pages)
            word_count = len(md_text.split())
            
            if word_count < 40:
                raise ValueError(
                    f"'{path.name}' contains no readable digital text layers."
                )
        else:
            md = MarkItDown()
            md_text = md.convert(str(path)).text_content
    except Exception as e:
        raise ValueError(f"Extraction layer failure on file {path.name}: {str(e)}")

    chunk_tuples = hybrid_chunk_markdown(md_text)
    usable_chunks = []
    
    for text, chapter in chunk_tuples:
        stripped_text = text.strip()
        if len(stripped_text) < 100:
            continue
        if is_reference_chunk(stripped_text):
            continue
            
        # Strip spaces out BEFORE calculating density so format styling doesn't trigger false rejections
        no_spaces = "".join(stripped_text.split())
        if no_spaces:
            alpha_density = sum(c.isalpha() for c in no_spaces) / len(no_spaces)
            if alpha_density > 0.35:
                usable_chunks.append((stripped_text, chapter))

    docs, metadatas, ids = [], [], []
    for i, (text, chapter) in enumerate(usable_chunks):
        docs.append(text)
        metadatas.append({
            "source": path.name,
            "chapter": chapter or "General Domain",
            "file_type": path.suffix.lower()
        })
        ids.append(f"{dataset_id}_{path.stem}_chunk_{i}")

    if not docs:
        raise ValueError("Document text extraction returned 0 usable semantic chunks.")

    # Vector store population
    embedder = SentenceTransformer("BAAI/bge-small-en-v1.5")
    embeddings = embedder.encode(docs, show_progress_bar=False, batch_size=64)

    chroma_dir = f"data/vector_stores/project_{project_id}" if project_id else f"data/vector_stores/dataset_{dataset_id}"
    collection_name = f"docs_{project_id}" if project_id else f"docs_{dataset_id}"

    os.makedirs(chroma_dir, exist_ok=True)
    client = chromadb.PersistentClient(path=chroma_dir)
    collection = client.get_or_create_collection(name=collection_name, metadata={"hnsw:space": "cosine"})

    collection.upsert(documents=docs, embeddings=embeddings.tolist(), metadatas=metadatas, ids=ids)
    logger.info(f"💾 Vector store populated successfully: saved {len(docs)} chunks inside {collection_name}")
    return True