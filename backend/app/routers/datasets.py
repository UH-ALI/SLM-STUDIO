import os
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
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
    before a project exists yet. New wizard flows should prefer
    POST /projects/{project_id}/datasets instead, which is the same logic with
    a guaranteed project link. Validation and persistence are shared via
    app.services.upload_helpers so this and the project-scoped endpoint never
    drift out of sync with each other again.

    All-or-nothing: if any file in the batch fails validation, every file in
    the batch is rejected and any already-saved files are deleted, rather than
    silently committing the ones that passed. A wizard step where the user
    expects "upload succeeded" to mean *all* their files are there.
    """
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    if not files:
        raise HTTPException(status_code=400, detail="No files provided.")

    valid_files_info = []
    errors = []

    # PASS 1: validate and save every file, collecting errors without committing anything
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
        # Roll back any files that were saved before the failure was hit
        for info in valid_files_info:
            if os.path.exists(info["file_location"]):
                os.remove(info["file_location"])
        raise HTTPException(status_code=400, detail=f"Validation failed for some files: {'; '.join(errors)}")

    # PASS 2: every file passed — now create DB records and dispatch ingestion
    created_datasets = []
    for info in valid_files_info:
        # file_location is uuid-prefixed for uniqueness — not a display name.
        dataset_name = name or info["filename"]
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
