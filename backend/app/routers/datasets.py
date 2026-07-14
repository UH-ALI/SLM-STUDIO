import os
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.core.deps import get_current_user
from app.database import get_db
from app.services.upload_helpers import (
    UPLOAD_DIR,
    create_dataset_record,
    save_file,
    validate_file,
    validate_format_specific,
)
from app.worker.tasks import ingest_document_task

router = APIRouter()


@router.get("/", response_model=List[schemas.DatasetResponse])
def list_datasets(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Returns all datasets owned by the current user.
    Used by the Datasets sidebar page and dataset dropdowns in the wizard.
    """
    datasets = (
        db.query(models.Dataset)
        .filter(models.Dataset.user_id == current_user.id)
        .order_by(models.Dataset.created_at.desc())
        .all()
    )
    return datasets


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
        dataset_name = name or os.path.basename(info["file_location"])
        new_dataset = create_dataset_record(
            db, dataset_name, info["file_location"], info["file_ext"], current_user.id
        )

        # Build many-to-many project dataset linkage
        project.datasets.append(new_dataset)
        db.commit()

        # Trigger Celery asynchronous worker to parse and chunk document
        ingest_document_task.delay(str(project_id), str(new_dataset.id))
        created_datasets.append(new_dataset)

    for ds in created_datasets:
        db.refresh(ds)

    return created_datasets


# ─── 2. STANDALONE UPLOAD ENDPOINT (LEGACY SUPPORT) ──────────────────────────
@router.post("/", response_model=List[schemas.DatasetResponse])
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
        dataset_name = name or os.path.basename(info["file_location"])
        new_dataset = create_dataset_record(
            db, dataset_name, info["file_location"], info["file_ext"], current_user.id
        )

        if project_id:
            project = (
                db.query(models.Project)
                .filter(models.Project.id == project_id, models.Project.user_id == current_user.id)
                .first()
            )
            if project:
                project.datasets.append(new_dataset)
                db.commit()
                ingest_document_task.delay(str(project_id), str(new_dataset.id))
            else:
                ingest_document_task.delay(None, str(new_dataset.id))
        else:
            ingest_document_task.delay(None, str(new_dataset.id))

        created_datasets.append(new_dataset)

    for ds in created_datasets:
        db.refresh(ds)

    return created_datasets