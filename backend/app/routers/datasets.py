import os
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.core.deps import get_current_user
from app.database import get_db
from app.services.upload_helpers import (
    UPLOAD_DIR,
    compute_file_hash,
    create_dataset_record,
    find_dataset_by_hash,
    save_file,
    validate_file,
    validate_format_specific,
)
from app.worker.tasks import ingest_document_task

router = APIRouter()


# [FIX] This router is mounted at prefix "/api/v1" (not "/api/v1/datasets") because
# the other routes in this file already spell out their own full sub-paths
# (see PROJECT-SCOPED UPLOAD ENDPOINT below). This route was registered at "/",
# which meant its real path was "/api/v1/" — not "/api/v1/datasets" — so the
# frontend's api.get('/datasets') call (-> /api/v1/datasets) could never match
# it at all, trailing slash or not. Registered at both "/datasets" and
# "/datasets/" now, matching what the frontend actually requests.
@router.get("/datasets", response_model=List[schemas.DatasetResponse], include_in_schema=False)
@router.get("/datasets/", response_model=List[schemas.DatasetResponse])
def list_datasets(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    # [PERF FIX] Optional, unbounded by default — see same note in
    # projects.py's list_projects. Pass ?limit=20 to opt into pagination.
    limit: Optional[int] = Query(default=None, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    """
    Returns datasets owned by the current user.
    Used by the Datasets sidebar page and dataset dropdowns in the wizard.
    """
    query = (
        db.query(models.Dataset)
        .filter(models.Dataset.user_id == current_user.id)
        .order_by(models.Dataset.created_at.desc())
    )
    if offset:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)
    return query.all()


# ─── 1. PROJECT-SCOPED UPLOAD ENDPOINT (FIXES DATASET UPLOAD BUG) ───────────
@router.post("/projects/{project_id}/datasets", response_model=List[schemas.DatasetResponse], status_code=status.HTTP_201_CREATED)
@router.post("/projects/{project_id}/datasets/", response_model=List[schemas.DatasetResponse], status_code=status.HTTP_201_CREATED)
def upload_project_datasets(
    project_id: str,
    files: List[UploadFile] = File(..., description="One or more files to upload (PDF, DOCX, TXT, CSV)"),
    name: Optional[str] = Form(None, description="Optional name for datasets. Defaults to filename."),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Handles file uploads specifically linked to an active project. 
    Accepts both slash and no-slash paths to prevent browser-blocked redirects.
    """
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    # Verify project exists and belongs to the current user
    project = (
        db.query(models.Project)
        .filter(models.Project.id == project_id, models.Project.user_id == current_user.id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found or access denied.")

    if not files:
        raise HTTPException(status_code=400, detail="No files provided.")

    valid_files_info = []
    errors = []

    # PASS 1: Validate and temporarily save files to check integrity
    for file in files:
        try:
            file_ext, file_location = validate_file(file)
            save_file(file, file_location)
            validate_format_specific(file_ext, file_location, file.filename)
            valid_files_info.append({
                "file_ext": file_ext,
                "file_location": file_location,
                "filename": file.filename,
            })
        except HTTPException as e:
            errors.append(f"{file.filename}: {e.detail}")
        except Exception as e:
            errors.append(f"Failed to process '{file.filename}': {str(e)}")

    if errors:
        # Roll back any files that were saved before the failure occurred
        for info in valid_files_info:
            if os.path.exists(info["file_location"]):
                os.remove(info["file_location"])
        raise HTTPException(
            status_code=400, 
            detail=f"Validation failed for some files: {'; '.join(errors)}"
        )

    # PASS 2: All files validated — Commit records and trigger ingestion workers
    created_datasets = []
    for info in valid_files_info:
        # [FEATURE] Dedup: if this exact file's content was already uploaded
        # by this user, reuse that dataset row + file on disk instead of
        # creating a duplicate. Ingestion still runs if this particular
        # project hasn't seen this dataset before (each project has its own
        # vector collection), just skips re-creating the DB/file record.
        file_hash = compute_file_hash(info["file_location"])
        existing = find_dataset_by_hash(db, current_user.id, file_hash)

        if existing:
            os.remove(info["file_location"])
            new_dataset = existing
            if new_dataset not in project.datasets:
                project.datasets.append(new_dataset)
                db.commit()
                ingest_document_task.delay(str(project_id), str(new_dataset.id))
        else:
            dataset_name = name or os.path.basename(info["file_location"])
            new_dataset = create_dataset_record(
                db, dataset_name, info["file_location"], info["file_ext"], current_user.id,
                file_hash=file_hash,
            )
            project.datasets.append(new_dataset)
            db.commit()
            ingest_document_task.delay(str(project_id), str(new_dataset.id))

        created_datasets.append(new_dataset)

    for ds in created_datasets:
        db.refresh(ds)

    return created_datasets


# ─── 2. STANDALONE UPLOAD ENDPOINT (LEGACY SUPPORT) ──────────────────────────
# [FIX] Same root-path mismatch as list_datasets above — was unreachable at
# its intended URL. Not currently called from the frontend (project-scoped
# upload below is what the wizard uses), but fixed for any external/legacy
# client relying on it, and for consistency with the rest of the file.
@router.post("/datasets", response_model=List[schemas.DatasetResponse], include_in_schema=False)
@router.post("/datasets/", response_model=List[schemas.DatasetResponse])
def upload_datasets(
    files: List[UploadFile] = File(..., description="One or more files to upload (PDF, DOCX, TXT, CSV)"),
    name: Optional[str] = Form(None, description="Optional name for datasets. Defaults to filename."),
    project_id: Optional[str] = Form(None, description="Optional project to link the datasets to."),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Legacy / standalone upload endpoint — kept for clients that upload a dataset
    before a project exists yet.
    """
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    if not files:
        raise HTTPException(status_code=400, detail="No files provided.")

    valid_files_info = []
    errors = []

    for file in files:
        try:
            file_ext, file_location = validate_file(file)
            save_file(file, file_location)
            validate_format_specific(file_ext, file_location, file.filename)
            valid_files_info.append({
                "file_ext": file_ext,
                "file_location": file_location,
                "filename": file.filename,
            })
        except HTTPException as e:
            errors.append(f"{file.filename}: {e.detail}")
        except Exception as e:
            errors.append(f"Failed to process '{file.filename}': {str(e)}")

    if errors:
        for info in valid_files_info:
            if os.path.exists(info["file_location"]):
                os.remove(info["file_location"])
        raise HTTPException(status_code=400, detail=f"Validation failed for some files: {'; '.join(errors)}")

    created_datasets = []
    for info in valid_files_info:
        file_hash = compute_file_hash(info["file_location"])
        existing = find_dataset_by_hash(db, current_user.id, file_hash)

        if existing:
            os.remove(info["file_location"])
            new_dataset = existing
        else:
            dataset_name = name or os.path.basename(info["file_location"])
            new_dataset = create_dataset_record(
                db, dataset_name, info["file_location"], info["file_ext"], current_user.id,
                file_hash=file_hash,
            )

        if project_id:
            project = (
                db.query(models.Project)
                .filter(models.Project.id == project_id, models.Project.user_id == current_user.id)
                .first()
            )
            if project:
                if new_dataset not in project.datasets:
                    project.datasets.append(new_dataset)
                    db.commit()
                    ingest_document_task.delay(str(project_id), str(new_dataset.id))
            else:
                ingest_document_task.delay(None, str(new_dataset.id))
        elif not existing:
            # Only trigger project-less ingestion for a genuinely new dataset —
            # a reused existing dataset with no project_id has nothing new to ingest.
            ingest_document_task.delay(None, str(new_dataset.id))

        created_datasets.append(new_dataset)

    for ds in created_datasets:
        db.refresh(ds)

    return created_datasets