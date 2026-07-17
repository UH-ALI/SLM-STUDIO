import logging
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
logger = logging.getLogger(__name__)


def _discard_upload(file_location: str) -> None:
    """
    Removes a just-saved upload that turned out to be unnecessary.

    Only ever call this with a path returned by validate_file() for the current
    request. Those are uuid-prefixed and therefore unique to this upload, so this
    can never remove a file an existing Dataset row still points at.
    """
    try:
        if file_location and os.path.exists(file_location):
            os.remove(file_location)
    except OSError:
        pass


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
    use_case_lower = (project.use_case or "general").lower()
    default_model_name = MODEL_CONFIGS.get(use_case_lower, MODEL_CONFIGS["general"])

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
        inference_temperature=0.3,
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
    force: bool = False,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Deletes a project from the database and removes disk files.
    Use ?force=true to delete a project that is stuck in processing/training.
    Database deletion happens FIRST; disk cleanup follows only on success.
    """
    project = (
        db.query(models.Project)
        .filter(models.Project.id == project_id, models.Project.user_id == current_user.id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found or unauthorized")

    # Block deletion of actively running projects unless force=true
    if project.status in (models.JobStatus.PROCESSING, models.JobStatus.TRAINING) and not force:
        raise HTTPException(
            status_code=409,
            detail="Project is currently processing/training. Use ?force=true to force delete, or cancel the project first.",
        )

    # Collect disk paths to clean up AFTER successful DB deletion
    base_data = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
    job_ids = [str(j.id) for j in project.jobs]
    disk_paths = [
        os.path.join(base_data, f"vector_stores/project_{project_id}"),
        os.path.join(base_data, f"vector_stores/dataset_{project_id}"),
    ]
    for jid in job_ids:
        disk_paths.append(os.path.join(base_data, f"adapters/job_{jid}"))
        disk_paths.append(os.path.join(base_data, f"processed/job_{jid}"))

    # Step 1: Database deletion (cascading FKs handle jobs, artifacts, logs, usage)
    project.datasets.clear()
    db.flush()
    db.delete(project)
    db.commit()

    # Step 2: Disk cleanup (only runs if DB commit succeeded)
    for folder_path in disk_paths:
        if os.path.exists(folder_path):
            shutil.rmtree(folder_path, ignore_errors=True)

    # Step 3: Evict VRAM and collection caches (best-effort)
    try:
        from app.ai.rag_inference import ACTIVE_COLLECTIONS, unload_model
        ACTIVE_COLLECTIONS.pop(project_id, None)
        for jid in job_ids:
            unload_model(jid)
    except Exception:
        pass

    return None


# ─── CANCEL / UNLOCK STUCK PROJECT ──────────────────────────────────────────
@router.post("/{project_id}/cancel", response_model=schemas.ProjectResponse)
def cancel_project(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Unlocks a project stuck in processing/training so it can be retried or deleted.

    This resets state; it does NOT kill a running task. Doing that needs the Celery
    task id, which is generated by .delay() and never stored — the previous code passed
    the TrainingJob's own UUID to revoke(), which silently matched nothing while
    appearing to work. Rather than pretend, this marks the job failed, releases the GPU
    lock, and tells the caller the worker may still be finishing.

    To make this a true cancel later: add TrainingJob.task_id, save the AsyncResult id
    at dispatch, and revoke that id here.
    """
    project = (
        db.query(models.Project)
        .filter(models.Project.id == project_id, models.Project.user_id == current_user.id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found or unauthorized")

    if project.status not in (models.JobStatus.PROCESSING, models.JobStatus.TRAINING):
        raise HTTPException(
            status_code=400,
            detail=f"Project is not stuck — current status is '{project.status.value}'. Cancel is only available for processing/training projects.",
        )

    # 1. Mark the latest job failed so the UI stops waiting on it.
    latest_job = (
        db.query(models.TrainingJob)
        .filter(models.TrainingJob.project_id == project_id)
        .order_by(models.TrainingJob.version.desc())
        .first()
    )
    if latest_job:
        latest_job.status = models.JobStatus.FAILED
        latest_job.error_message = "Unlocked by user"

    # 2. Reset project status so it's unlocked
    project.status = models.JobStatus.FAILED
    project.error_message = "Unlocked by user"
    db.commit()

    # 3. Clear GPU state locks in Redis
    try:
        import redis
        _redis = redis.Redis.from_url(settings.CELERY_BROKER_URL, decode_responses=True)
        _redis.delete("gpu:state")
    except Exception:
        pass

    db.refresh(project)
    return project


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

    import hashlib

    valid_files_info = []
    errors = []

    # PASS 1: validate, save, and compute SHA-256 hash for every file
    for file in files:
        try:
            file_ext, file_location = validate_file(file)
            save_file(file, file_location)
            validate_format_specific(file_ext, file_location, file.filename)

            # Compute SHA-256 hash of the saved file for deduplication
            sha256 = hashlib.sha256()
            with open(file_location, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    sha256.update(chunk)

            valid_files_info.append({
                "file_ext": file_ext,
                "file_location": file_location,
                "filename": file.filename,
                "file_hash": sha256.hexdigest(),
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

    # PASS 2: dedup check + create DB records, link to project, dispatch ingestion
    created_datasets = []
    for info in valid_files_info:
        # The stored path is uuid-prefixed for uniqueness, so it is not a display
        # name — use the filename the user actually uploaded.
        dataset_name = name or info["filename"]
        file_hash = info["file_hash"]

        # ── Dedup Check 1: identical content already in THIS project ──
        # Hash only. Also matching on name would reject a genuinely different document
        # that merely shares a filename.
        if any(ds.file_hash == file_hash for ds in project.datasets if ds.file_hash):
            _discard_upload(info["file_location"])
            errors.append(f"'{dataset_name}' is already attached to this project.")
            continue

        # ── Same filename, content not proven identical ──
        same_name = [ds for ds in project.datasets if ds.name == dataset_name]
        if same_name:
            _discard_upload(info["file_location"])
            if any(ds.file_hash is None for ds in same_name):
                # Predates hashing, so the two can't be compared. Assume it's the same
                # document — telling the user to rename a file they already uploaded is
                # the worse guess.
                errors.append(f"'{dataset_name}' is already attached to this project.")
            else:
                # Hashes exist and differ: genuinely a different document.
                errors.append(
                    f"A different document named '{dataset_name}' is already in this "
                    "project. Rename the file and upload it again."
                )
            continue

        # ── Dedup Check 2: identical content in ANOTHER project — reuse the row ──
        existing_dataset = (
            db.query(models.Dataset)
            .filter(
                models.Dataset.user_id == current_user.id,
                models.Dataset.file_hash == file_hash,
            )
            .first()
        ) if file_hash else None

        if existing_dataset:
            # The content is provably identical, so reuse the stored file and row.
            # Safe to drop the upload: paths are uuid-prefixed, so this is never the
            # path the existing row points at.
            _discard_upload(info["file_location"])

            project.datasets.append(existing_dataset)
            db.commit()

            # Reuse embeddings from a project that already has them, if any.
            source_project = next(
                (sp for sp in existing_dataset.projects if str(sp.id) != str(project_id)),
                None,
            )

            copied = False
            if source_project:
                try:
                    from app.ai.rag_ingestion import copy_vectors_across_projects
                    copied = bool(copy_vectors_across_projects(
                        source_project_id=str(source_project.id),
                        target_project_id=str(project_id),
                        dataset_id=str(existing_dataset.id),
                    ))
                except Exception:
                    copied = False

            # The copy reports failure by returning False, not by raising. Ignoring the
            # return value left the project with no vectors and no ingestion queued —
            # permanently stuck behind the "still processing" guard. Always fall back.
            if not copied:
                ingest_document_task.delay(str(project_id), str(existing_dataset.id))

            created_datasets.append(existing_dataset)
        else:
            # Brand new file — create fresh Dataset record with hash
            new_dataset = create_dataset_record(
                db, dataset_name, info["file_location"], info["file_ext"], current_user.id
            )
            new_dataset.file_hash = file_hash
            db.flush()

            project.datasets.append(new_dataset)
            db.commit()

            ingest_document_task.delay(str(project_id), str(new_dataset.id))
            created_datasets.append(new_dataset)

    # If ALL files were duplicates, raise error
    if errors and not created_datasets:
        raise HTTPException(status_code=400, detail="; ".join(errors))

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


# ─── INGESTION STATUS (which documents actually made it into the model) ─────
@router.get("/{project_id}/ingestion_status")
def get_project_ingestion_status(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Reports, per document, whether it was successfully parsed into the vector store.

    Ingestion runs per-document in the background, so one unreadable file leaves the
    rest working and the assistant quietly answers from a subset of what was uploaded.
    This makes that visible instead of leaving the user to infer it from bad answers.
    """
    project = (
        db.query(models.Project)
        .filter(models.Project.id == project_id, models.Project.user_id == current_user.id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found or unauthorized")

    from app.ai.rag_ingestion import get_ingested_sources
    ingested = get_ingested_sources(project_id)

    documents = [
        {
            "name": ds.name,
            "chunks": ingested.get(ds.name, 0),
            "ingested": ingested.get(ds.name, 0) > 0,
        }
        for ds in project.datasets
    ]
    ready = [d for d in documents if d["ingested"]]

    return {
        "documents": documents,
        "totalChunks": sum(ingested.values()),
        "readyCount": len(ready),
        "totalCount": len(documents),
        # Still ingesting vs. actually failed is indistinguishable from here, so let
        # the caller phrase it — this flag only says "not everything is in yet".
        "allReady": len(ready) == len(documents) and len(documents) > 0,
    }


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
    # Every failure here used to be reported as "still processing", so a project whose
    # ingestion had already died silently told the user to keep waiting — forever.
    # Each cause now gets its own message, and the caller is told what to do about it.
    from app.ai.rag_inference import get_or_load_collection
    from app.ai.rag_ingestion import get_ingested_sources

    # Ingestion is asynchronous, so "no vectors yet" genuinely means either "still
    # running" or "already failed" — and nothing here can tell those apart. Say so,
    # instead of asserting one of them the way the old catch-all asserted "processing".
    try:
        collection = get_or_load_collection(project_id)
        vector_count = collection.count()
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="This project has no searchable documents yet. Ingestion may still be "
                   "running — wait a few seconds and try again. If it keeps failing, the "
                   "document could not be read; re-upload it or try a different file.",
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Could not read this project's document index ({type(e).__name__}). "
                   "The ingestion may have been interrupted — try re-uploading the document.",
        )

    if vector_count == 0:
        raise HTTPException(
            status_code=400,
            detail="This project has no searchable documents yet. Ingestion may still be "
                   "running — wait a few seconds and try again. If it keeps failing, the "
                   "document may have no readable text.",
        )

    # Training on a subset is valid, so don't block on it — but record which documents
    # are missing. The Playground surfaces the same information via /ingestion_status;
    # silently training on a subset is what makes the assistant look like it forgot things.
    missing = [ds.name for ds in project.datasets if ds.name not in get_ingested_sources(project_id)]
    if missing:
        logger.warning(
            f"Project {project_id} is training without {len(missing)} document(s) that "
            f"produced no searchable text: {missing}"
        )

    project.base_model_name = request.base_model_name
    project.hyperparameters = request.hyperparameters
    project.inference_temperature = request.inference_temperature or 0.3
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
