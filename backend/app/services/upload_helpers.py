"""
Shared file-upload validation and persistence helpers.

This module exists because routers/datasets.py and routers/projects.py both
implemented near-identical file validation/upload logic (same size limits,
same per-format checks, same Dataset-record creation). Consolidated here so
there is exactly one implementation to maintain.
"""
import csv
import os
import shutil
import uuid
import zipfile
from typing import Optional

import fitz  # PyMuPDF
from docx import Document
from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session
from werkzeug.utils import secure_filename

from app import models

# ─── UNIVERSAL LIMITS (apply to all formats) ────────────────────────────────
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB — PDF, DOCX, TXT, CSV

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".csv"}

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
UPLOAD_DIR = os.path.join(BASE_DIR, "data", "raw")


def validate_file(file: UploadFile) -> tuple[str, str]:
    """Validates size, filename, and extension. Returns (file_ext, file_location)."""
    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File '{file.filename}' too large. Max size: {MAX_FILE_SIZE // (1024 * 1024)}MB",
        )

    safe_filename = secure_filename(file.filename)
    if not safe_filename:
        raise HTTPException(status_code=400, detail=f"Invalid filename after sanitization: {file.filename}")

    file_ext = os.path.splitext(safe_filename)[1].lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{file_ext}' for file '{file.filename}'. "
                   f"Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    # Store under a uuid-prefixed name. Keying storage on the bare filename made two
    # uploads of "handbook.pdf" resolve to one path, so a second upload silently
    # overwrote the first file — across projects and across users — and the dedup
    # cleanup then deleted the original out from under the row that still referenced
    # it. A unique path per upload makes that class of bug impossible; the original
    # filename is preserved separately as Dataset.name for display.
    unique_filename = f"{uuid.uuid4().hex}_{safe_filename}"
    file_location = os.path.join(UPLOAD_DIR, unique_filename)
    return file_ext, file_location


def save_file(file: UploadFile, file_location: str) -> None:
    with open(file_location, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)


def _validate_pdf(file_location: str, filename: str) -> None:
    try:
        doc = fitz.open(file_location)
        doc.close()
    except HTTPException:
        raise
    except Exception as e:
        if os.path.exists(file_location):
            os.remove(file_location)
        raise HTTPException(status_code=400, detail=f"Invalid or corrupted PDF file '{filename}'. Error: {str(e)}")


def _validate_docx(file_location: str, filename: str) -> None:
    try:
        with zipfile.ZipFile(file_location, "r") as z:
            if "word/document.xml" not in z.namelist():
                raise ValueError("Invalid DOCX structure")
        doc = Document(file_location)
        total_words = sum(len(p.text.split()) for p in doc.paragraphs)
        if total_words > 150_000:
            os.remove(file_location)
            raise HTTPException(status_code=413, detail=f"Document '{filename}' too large. Max words: 150,000.")
    except HTTPException:
        raise
    except Exception as e:
        if os.path.exists(file_location):
            os.remove(file_location)
        raise HTTPException(status_code=400, detail=f"Invalid or corrupted DOCX file '{filename}'. Error: {str(e)}")


def _validate_txt(file_location: str, filename: str) -> None:
    try:
        with open(file_location, "r", encoding="utf-8") as f:
            lines = f.readlines()
            if len(lines) > 50_000:
                os.remove(file_location)
                raise HTTPException(
                    status_code=413,
                    detail=f"Text file '{filename}' too long. Max lines: 50,000. Your file has {len(lines)} lines.",
                )
    except HTTPException:
        raise
    except Exception as e:
        if os.path.exists(file_location):
            os.remove(file_location)
        raise HTTPException(status_code=400, detail=f"Invalid text file '{filename}'. Error: {str(e)}")


def _validate_csv(file_location: str, filename: str) -> None:
    try:
        with open(file_location, "r", encoding="utf-8") as f:
            row_count = sum(1 for _ in csv.reader(f))
            if row_count > 100_000:
                os.remove(file_location)
                raise HTTPException(
                    status_code=413,
                    detail=f"CSV '{filename}' too large. Max rows: 100,000. Your file has {row_count} rows.",
                )
    except HTTPException:
        raise
    except Exception as e:
        if os.path.exists(file_location):
            os.remove(file_location)
        raise HTTPException(status_code=400, detail=f"Invalid CSV file '{filename}'. Error: {str(e)}")


def validate_format_specific(file_ext: str, file_location: str, filename: str) -> None:
    """Routes to format-specific validation (page/word/line/row-count limits, corruption checks)."""
    if file_ext == ".pdf":
        _validate_pdf(file_location, filename)
    elif file_ext == ".docx":
        _validate_docx(file_location, filename)
    elif file_ext == ".txt":
        _validate_txt(file_location, filename)
    elif file_ext == ".csv":
        _validate_csv(file_location, filename)


def create_dataset_record(
    db: Session,
    name: str,
    file_location: str,
    file_ext: str,
    user_id: str,
) -> models.Dataset:
    """Creates and commits a Dataset row. dataset_type is inferred from the extension (M1 fix)."""
    if file_ext in {".pdf", ".docx", ".txt"}:
        dataset_type = models.DatasetType.UNSTRUCTURED
    elif file_ext == ".csv":
        dataset_type = models.DatasetType.STRUCTURED
    else:
        dataset_type = models.DatasetType.UNSTRUCTURED

    new_dataset = models.Dataset(
        name=name,
        file_path=file_location,
        user_id=user_id,
        dataset_type=dataset_type,
    )
    db.add(new_dataset)
    db.commit()
    db.refresh(new_dataset)
    return new_dataset
