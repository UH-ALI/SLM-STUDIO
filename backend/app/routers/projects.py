import os
import shutil
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, schemas
from app.worker.tasks import train_model_task, ingest_document_task
from app.core.deps import get_current_user
from app.core.config import settings
from app.services.upload_helpers import (
    UPLOAD_DIR,
    create_dataset_record,
    save_file,
    validate_file,
    validate_format_specific,
)

router = APIRouter()


def _transform_few_shot_examples(examples: Optional[List[Dict[str, str]]]) -> Optional[List[Dict[str, str]]]:
    """
    [PROJECT REFACTOR] Transform frontend format [{input, output}] to backend format [{question: answer}].
    Handles both formats for backward compatibility.
    """
    if not examples:
        return None
    result = []
    for ex in examples:
        if "input" in ex and "output" in ex:
            result.append({ex["input"]: ex["output"]})
        else:
            result.append(ex)
    return result


# [STATUS FIX] 'training' is now a real, first-class status the frontend
# understands (Project.status, TrainingStatus type unions, the training-page
# mapping useEffect, and the live progress components all branch on it
# explicitly). Earlier this function mapped "training" -> "processing" at the
# API boundary because the frontend didn't know the value yet — that mapping
# would now hide the live-training UI instead of the opposite, so the
# function is kept (call sites may still want a single point of control) but
# is now a passthrough. If a future status needs masking, do it here.
def _map_status_for_frontend(status: str) -> str:
    return status


def _transform_logs(logs: List[models.JobLog]) -> List[Dict[str, str]]:
    """[PROJECT REFACTOR] Transform JobLog objects to frontend format {time, level, message}."""
    return [
        {
            "time": log.created_at.isoformat(),
            "level": log.level.lower(),
            "message": log.message,
        }
        for log in logs
    ]


# ─── CREATE PROJECT ───────────────────────────────────────────────────────────
# [PROJECT REFACTOR] Replaces old POST /jobs/ — creates a Project entity
@router.post("/", response_model=schemas.ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    project: schemas.ProjectCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Creates a new Project (the user's "AI assistant") — Step 1 of the wizard.
    Accepts name/useCase/persona/fewShotExamples. base_model_name is resolved
    here from the use-case's default in MODEL_CONFIGS rather than left null,
    since TrainingJob.base_model_name is NOT NULL and /train falls back to a
    hardcoded default otherwise — resolving it at creation time means the
    project's displayed "model" is accurate even before the user picks one
    explicitly in Step 3.
    """
    few_shot = _transform_few_shot_examples(project.few_shot_examples)

    from app.ai.finetune import MODEL_CONFIGS
    from app.ai.rag_inference import DEFAULT_TEMPERATURE_BY_USE_CASE
    use_case_lower = (project.use_case or "general").lower()
    default_model_name = MODEL_CONFIGS.get(use_case_lower, MODEL_CONFIGS["general"])
    # [FIX] DEFAULT_TEMPERATURE_BY_USE_CASE was defined in rag_inference.py but
    # never actually consulted anywhere — every code path hardcoded 0.3
    # regardless of domain, so medical/legal projects got the same creativity
    # budget as a general chatbot instead of the intended low-temperature
    # (0.15) factual behavior.
    default_temperature = DEFAULT_TEMPERATURE_BY_USE_CASE.get(use_case_lower, 0.3)

    new_project = models.Project(
        user_id=current_user.id,
        name=project.name,
        use_case=project.use_case,
        persona=project.persona,
        few_shot_examples=few_shot,
        base_model_name=default_model_name,
        status=models.JobStatus.PENDING,
        progress=0,
        epoch=0,
        inference_temperature=default_temperature,
    )
    db.add(new_project)
    db.commit()
    db.refresh(new_project)
    return new_project


# ─── LIST ALL USER'S PROJECTS ───────────────────────────────────────────────
@router.get("/", response_model=List[schemas.ProjectResponse])
def list_projects(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Returns all projects owned by the current user. Used by the Dashboard."""
    projects = (
        db.query(models.Project)
        .filter(models.Project.user_id == current_user.id)
        .order_by(models.Project.created_at.desc())
        .all()
    )
    return projects


# ─── GET SINGLE PROJECT ────────────────────────────────────────────────────
@router.get("/{project_id}", response_model=schemas.ProjectResponse)
def get_project(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Returns a single project by ID. Verifies ownership."""
    project = (
        db.query(models.Project)
        .filter(models.Project.id == project_id, models.Project.user_id == current_user.id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found or unauthorized")
    return project


# ─── DELETE SINGLE PROJECT ──────────────────────────────────────────────────
@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Deletes a project from the database and removes disk files (adapters, vector stores, datasets)."""
    project = (
        db.query(models.Project)
        .filter(models.Project.id == project_id, models.Project.user_id == current_user.id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found or unauthorized")

    job_ids = [
        job_id
        for (job_id,) in db.query(models.TrainingJob.id)
        .filter(models.TrainingJob.project_id == project_id)
        .all()
    ]

    if job_ids:
        db.query(models.JobLog).filter(models.JobLog.job_id.in_(job_ids)).delete(synchronize_session=False)
        db.query(models.ModelArtifact).filter(models.ModelArtifact.job_id.in_(job_ids)).delete(
            synchronize_session=False
        )
        db.query(models.TrainingJob).filter(models.TrainingJob.id.in_(job_ids)).delete(
            synchronize_session=False
        )

    # Clean up disk folders (adapters use job_<project_id>, vector stores use project_<project_id>)
    base_data = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
    for pattern in [
        f"adapters/job_{project_id}",
        f"vector_stores/project_{project_id}",
        f"vector_stores/dataset_{project_id}",
    ]:
        folder_path = os.path.join(base_data, pattern)
        if os.path.exists(folder_path):
            shutil.rmtree(folder_path, ignore_errors=True)

    # Clear M:M association before deleting (avoids FK constraint on project_datasets)
    project.datasets.clear()
    db.flush()

    db.delete(project)
    db.commit()
    return None


# ─── UPLOAD DATASETS TO PROJECT ──────────────────────────────────────────────
@router.post("/{project_id}/datasets", response_model=List[schemas.DatasetResponse])
def upload_project_datasets(
    project_id: str,
    files: List[UploadFile] = File(..., description="One or more files to upload (PDF, DOCX, TXT, CSV)"),
    name: Optional[str] = Form(None, description="Optional name for datasets. Defaults to filename."),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Uploads one or more dataset files and links them to a project.
    Validates all files before committing any to the database.

    Ownership is checked before any file is written to disk — an earlier
    version checked ownership only at the link step, after files were already
    saved, so an unauthorized project_id would still leave orphaned files
    behind before the 404 fired.

    All-or-nothing: if any file in the batch fails validation, every file is
    rejected and any already-saved files are rolled back.
    """
    project = (
        db.query(models.Project)
        .filter(models.Project.id == project_id, models.Project.user_id == current_user.id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found or unauthorized")

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
        for info in valid_files_info:
            if os.path.exists(info["file_location"]):
                os.remove(info["file_location"])
        raise HTTPException(status_code=400, detail=f"Validation failed for some files: {'; '.join(errors)}")

    # PASS 2: every file passed — now create DB records, link to project, dispatch ingestion
    created_datasets = []
    for info in valid_files_info:
        dataset_name = name or os.path.basename(info["file_location"])
        new_dataset = create_dataset_record(
            db, dataset_name, info["file_location"], info["file_ext"], current_user.id
        )

        project.datasets.append(new_dataset)
        db.commit()

        ingest_document_task.delay(str(project_id), str(new_dataset.id))
        created_datasets.append(new_dataset)

    for ds in created_datasets:
        db.refresh(ds)

    return created_datasets


# ─── LIST PROJECT DATASETS ─────────────────────────────────────────────────
@router.get("/{project_id}/datasets", response_model=List[schemas.DatasetResponse])
def list_project_datasets(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Returns all datasets linked to a project."""
    project = (
        db.query(models.Project)
        .filter(models.Project.id == project_id, models.Project.user_id == current_user.id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found or unauthorized")
    return project.datasets


# ─── START TRAINING ─────────────────────────────────────────────────────────
@router.post("/{project_id}/train", response_model=schemas.ProjectResponse)
def train_project(
    project_id: str,
    request: schemas.ProjectTrainRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Initiates training for a project.
    1. Updates project's mutable config (base_model_name, hyperparameters, inference_temperature)
    2. Creates TrainingJob vN (auto-increment version)
    3. Copies all config from Project to TrainingJob
    4. Dispatches train_model_task to Celery worker
    """
    project = (
        db.query(models.Project)
        .filter(models.Project.id == project_id, models.Project.user_id == current_user.id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found or unauthorized")

    if not project.datasets:
        raise HTTPException(status_code=400, detail="Project has no datasets. Upload at least one document.")

    # [BUG 18 FIX] Check that ChromaDB ingestion has actually completed before
    # starting training, by checking the collection's vector count. Without
    # this, /train could race ahead of the Celery ingestion task and start
    # training against an empty collection — not a crash, just a silently
    # ungrounded model with zero retrieval context.
    try:
        from app.ai.rag_inference import get_or_load_collection
        collection = get_or_load_collection(project_id)
        if collection.count() == 0:
            raise HTTPException(
                status_code=400,
                detail="Datasets are still processing (0 vectors found). Please wait for ingestion to complete.",
            )
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(
            status_code=400, detail="Datasets are still processing. Please wait for ingestion to complete."
        )

    project.base_model_name = request.base_model_name
    project.hyperparameters = request.hyperparameters
    # [FIX] Same DEFAULT_TEMPERATURE_BY_USE_CASE fix as project creation —
    # only fall back to the domain default when the user didn't explicitly
    # set one, instead of always flattening to 0.3.
    if request.inference_temperature is not None:
        project.inference_temperature = request.inference_temperature
    else:
        from app.ai.rag_inference import DEFAULT_TEMPERATURE_BY_USE_CASE
        use_case_lower = (project.use_case or "general").lower()
        project.inference_temperature = DEFAULT_TEMPERATURE_BY_USE_CASE.get(use_case_lower, 0.3)
    project.status = models.JobStatus.PENDING
    project.progress = 0
    project.epoch = 0
    project.metrics = None
    project.error_message = None
    db.commit()

    latest_job = (
        db.query(models.TrainingJob)
        .filter(models.TrainingJob.project_id == project_id)
        .order_by(models.TrainingJob.version.desc())
        .first()
    )
    next_version = (latest_job.version + 1) if latest_job else 1

    # [FIX] Fallback defaults ensure DB non-nullable constraints are never violated
    base_model = project.base_model_name or "unsloth/Qwen2.5-1.5B-Instruct-bnb-4bit"
    persona = project.persona or (
        "You are a highly capable AI domain expert.\n"
        "You are an expert AI assistant for the content of this document.\n"
        "You explain concepts clearly and concisely.\n"
        "You only answer questions grounded in the provided documents."
    )

    new_job = models.TrainingJob(
        project_id=project.id,
        user_id=current_user.id,
        version=next_version,
        name=f"{project.name} v{next_version}",
        use_case=project.use_case,
        persona=persona,
        few_shot_examples=project.few_shot_examples,
        base_model_name=base_model,
        hyperparameters=project.hyperparameters,
        status=models.JobStatus.PENDING,
    )
    db.add(new_job)
    db.commit()
    db.refresh(new_job)

    if settings.EXECUTION_MODE == "distributed":
        try:
            train_model_task.delay(str(project.id), str(new_job.id))
        except Exception as e:
            print(f"Error dispatching training task: {e}")
            project.status = models.JobStatus.FAILED
            new_job.status = models.JobStatus.FAILED
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to dispatch training task to the queue.",
            )
    else:
        print(f"Local/Fallback mode: skipping distributed queue dispatch for project {project.id}")

    db.refresh(project)
    return project


# ─── GET PROJECT STATUS (RICH) ──────────────────────────────────────────────
@router.get("/{project_id}/status", response_model=schemas.ProjectStatusResponse)
def get_project_status(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Returns rich status for the training dashboard: progress, epoch, metrics,
    and logs from the latest training job. Frontend polls this every ~2s.
    """
    project = (
        db.query(models.Project)
        .filter(models.Project.id == project_id, models.Project.user_id == current_user.id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found or unauthorized")

    latest_job = (
        db.query(models.TrainingJob)
        .filter(models.TrainingJob.project_id == project_id)
        .order_by(models.TrainingJob.version.desc())
        .first()
    )

    logs = []
    if latest_job:
        job_logs = (
            db.query(models.JobLog)
            .filter(models.JobLog.job_id == latest_job.id)
            .order_by(models.JobLog.created_at.asc())
            .all()
        )
        logs = _transform_logs(job_logs)

    return schemas.ProjectStatusResponse(
        id=project.id,
        name=project.name,
        status=_map_status_for_frontend(project.status.value),
        model_name=project.base_model_name,
        use_case=project.use_case,
        progress=project.progress if project.progress else 0,
        epoch=project.epoch or 0,
        metrics=project.metrics,
        logs=logs,
        inference_temperature=project.inference_temperature or 0.3,
        created_at=project.created_at,
        error_message=project.error_message,
    )


# ─── INCREMENTAL LOG STREAMING ───────────────────────────────────────────────
# Dedicated endpoint for polling just the log tail, so a client doesn't have to
# re-fetch the full status payload (project metadata + metrics + all logs) on
# every poll tick just to check for new log lines. /status already embeds the
# full log list for clients that only need one request (this is what the
# current frontend actually uses — see hooks/useJobs.ts); this endpoint is for
# future clients that want cheap incremental polling instead.
#
# Cursor is an ISO timestamp, not a row ID: JobLogResponse deliberately omits
# `id`/`job_id` (a real privacy decision — don't leak internal DB identifiers
# in a response that doesn't need them), so there's no ID for the client to
# echo back as a cursor. created_at already gives a strictly-increasing,
# per-job-scoped ordering that works just as well for "give me what's new".
@router.get("/{project_id}/logs", response_model=List[schemas.JobLogResponse])
def get_project_logs(
    project_id: str,
    after: Optional[str] = None,
    limit: int = 200,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Returns log lines for the project's latest training job, optionally only
    those created after a given ISO-8601 timestamp (`after`), capped at `limit`.
    """
    project = (
        db.query(models.Project)
        .filter(models.Project.id == project_id, models.Project.user_id == current_user.id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found or unauthorized")

    latest_job = (
        db.query(models.TrainingJob)
        .filter(models.TrainingJob.project_id == project_id)
        .order_by(models.TrainingJob.version.desc())
        .first()
    )
    if not latest_job:
        return []

    query = db.query(models.JobLog).filter(models.JobLog.job_id == latest_job.id)
    if after:
        try:
            from datetime import datetime
            after_dt = datetime.fromisoformat(after)
            query = query.filter(models.JobLog.created_at > after_dt)
        except ValueError:
            raise HTTPException(status_code=400, detail="`after` must be an ISO-8601 timestamp")

    logs = query.order_by(models.JobLog.created_at.asc()).limit(limit).all()
    return logs


# ─── LIST TRAINING JOB HISTORY ──────────────────────────────────────────────
@router.get("/{project_id}/jobs", response_model=List[schemas.JobResponse])
def list_project_jobs(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Returns all training jobs (versions) for a project, e.g. v1, v2, v3..."""
    project = (
        db.query(models.Project)
        .filter(models.Project.id == project_id, models.Project.user_id == current_user.id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found or unauthorized")

    jobs = (
        db.query(models.TrainingJob)
        .filter(models.TrainingJob.project_id == project_id)
        .order_by(models.TrainingJob.version.asc())
        .all()
    )
    return jobs
