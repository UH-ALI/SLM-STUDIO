import os
import shutil
import uuid
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from app.database import get_db
from app import models, schemas
from app.worker.tasks import train_model_task, ingest_document_task
from app.core.deps import get_current_user
from app.core.config import settings
from app.core.rate_limit import _redis
from app.services import email_service
from app.services.upload_helpers import UPLOAD_DIR

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
@router.post("", response_model=schemas.ProjectResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
@router.post("/", response_model=schemas.ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    project: schemas.ProjectCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Creates a new Project (the user's "AI assistant") — Step 1 of the wizard."""
    few_shot = _transform_few_shot_examples(project.few_shot_examples)

    from app.ai.finetune import MODEL_CONFIGS
    from app.ai.rag_inference import DEFAULT_TEMPERATURE_BY_USE_CASE
    use_case_lower = (project.use_case or "general").lower()
    default_model_name = MODEL_CONFIGS.get(use_case_lower, MODEL_CONFIGS["general"])
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
@router.get("", response_model=List[schemas.ProjectResponse], include_in_schema=False)
@router.get("/", response_model=List[schemas.ProjectResponse])
def list_projects(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    # [PERF FIX] limit/offset are optional and default to unbounded — the
    # Dashboard currently expects every project back in one call, so adding
    # a default page size here would silently truncate existing users'
    # project lists. Pass ?limit=20 explicitly to opt into pagination.
    limit: Optional[int] = Query(default=None, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    """Returns projects owned by the current user. Used by the Dashboard."""
    query = (
        db.query(models.Project)
        # [PERF FIX] N+1 fix: Project.datasets is lazy-loaded, so returning N
        # projects previously issued 1 query for the list + 1 more per
        # project to fetch its datasets. joinedload folds that into a single
        # query via a LEFT JOIN. No response shape change.
        .options(joinedload(models.Project.datasets))
        .filter(models.Project.user_id == current_user.id)
        .order_by(models.Project.created_at.desc())
    )
    if offset:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)
    # Note: legacy db.query(...).all() (as used here) auto-deduplicates
    # parent rows when joinedload'ing a collection, unlike the 2.0-style
    # db.execute(select(...)) API which requires an explicit .unique() call.
    return query.all()


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


# ─── RENAME PROJECT ─────────────────────────────────────────────────────────
# [FEATURE] Was a frontend-only stub that showed "Rename coming soon".
@router.patch("/{project_id}", response_model=schemas.ProjectResponse)
def rename_project(
    project_id: str,
    payload: schemas.ProjectRenameRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Renames a project. Currently the only mutable field this endpoint supports."""
    project = (
        db.query(models.Project)
        .filter(models.Project.id == project_id, models.Project.user_id == current_user.id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found or unauthorized")

    project.name = payload.name
    db.commit()
    db.refresh(project)
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

    base_data = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
    for pattern in [
        f"adapters/job_{project_id}",
        f"vector_stores/project_{project_id}",
        f"vector_stores/dataset_{project_id}",
    ]:
        folder_path = os.path.join(base_data, pattern)
        if os.path.exists(folder_path):
            shutil.rmtree(folder_path, ignore_errors=True)

    project.datasets.clear()
    db.flush()

    db.delete(project)
    db.commit()
    return None


# [REMOVED — item 10] upload_project_datasets() used to live here at
# POST /{project_id}/datasets, but datasets.py's identical-path
# POST /api/v1/projects/{project_id}/datasets is registered first in
# main.py's router mounting order and always wins the match, making this
# copy permanently unreachable dead code. Confirmed no other code imported
# or called it directly. The live version — with the same dedup logic — is
# datasets.py's upload_project_datasets().


# ─── ATTACH EXISTING DATASETS TO PROJECT ────────────────────────────────────
# [FEATURE] Lets a project reuse one of the user's already-uploaded datasets
# instead of forcing a fresh upload every time — the dataset row and its
# file on disk are shared, but ingestion still runs per-project since each
# project gets its own vector collection (see ingest_document_task).
@router.post("/{project_id}/datasets/attach", response_model=List[schemas.DatasetResponse])
def attach_existing_datasets(
    project_id: str,
    payload: schemas.AttachDatasetsRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    project = (
        db.query(models.Project)
        .filter(models.Project.id == project_id, models.Project.user_id == current_user.id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found or unauthorized")

    if not payload.dataset_ids:
        raise HTTPException(status_code=400, detail="No datasets specified.")

    already_linked_ids = {str(d.id) for d in project.datasets}
    attached = []

    for dataset_id in payload.dataset_ids:
        dataset = (
            db.query(models.Dataset)
            .filter(models.Dataset.id == dataset_id, models.Dataset.user_id == current_user.id)
            .first()
        )
        if not dataset:
            raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found or unauthorized")

        if str(dataset.id) not in already_linked_ids:
            project.datasets.append(dataset)
            db.commit()
            ingest_document_task.delay(str(project_id), str(dataset.id))

        attached.append(dataset)

    return attached


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
    """Initiates training asynchronously without blocking the client during background ingestion runs."""
    project = (
        db.query(models.Project)
        .filter(models.Project.id == project_id, models.Project.user_id == current_user.id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found or unauthorized")

    # [FIX] Verification existed (is_email_verified column, /auth/verify-email,
    # the verify-email-sent page) but nothing actually gated on it — an
    # unverified account could hit "Continue to dashboard" and start training
    # same as anyone else. Enforced here specifically (not at login) so this
    # doesn't lock existing users out of the app entirely, just out of the
    # one action — starting a training run — that verification is meant to
    # gate. 403 rather than 401: the user IS authenticated, they just haven't
    # completed this one extra step yet.
    #
    # [FEATURE] Rather than just telling the user to go dig up (or manually
    # resend) the verification email, fire one automatically right here —
    # same Redis-token mechanism as /auth/resend-verification, and the same
    # 60s rate limit key, so hammering "start training" repeatedly can't
    # spam their inbox either.
    if not current_user.is_email_verified:
        resend_rate_key = f"resend_rate:{current_user.email.strip().lower()}"
        if not _redis.exists(resend_rate_key):
            try:
                token = str(uuid.uuid4())
                _redis.setex(f"verify_token:{token}", 24 * 60 * 60, str(current_user.id))
                _redis.setex(resend_rate_key, 60, "1")
                email_service.send_verification_email(current_user.email, token)
            except Exception as e:
                print(f"Warning: failed to auto-send verification email: {e}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your email address before starting training. We just sent (or recently sent) a verification link to your inbox.",
        )

    # If no tracking records exist in PostgreSQL, prevent ungrounded runs safely
    if not project.datasets:
        raise HTTPException(
            status_code=400, 
            detail="Project has no datasets. Please upload a document first to initiate the workspace pipeline."
        )

    # 🚀 INPUT SANITIZATION SHIELD: Intercept any broken frontend selections
    input_model = request.base_model_name or ""
    if "Qwen3" in input_model or "bnb-4bit" not in input_model or not input_model:
        sanitized_model = "unsloth/Qwen2.5-3B-Instruct-bnb-4bit"
    else:
        sanitized_model = input_model

    project.base_model_name = sanitized_model
    project.hyperparameters = request.hyperparameters
    
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
        base_model_name=sanitized_model,  # 🚀 Safe model passed to the training engine
        hyperparameters=project.hyperparameters,
        status=models.JobStatus.PENDING,
    )
    db.add(new_job)
    db.commit()
    db.refresh(new_job)

    if settings.EXECUTION_MODE == "distributed":
        try:
            result = train_model_task.delay(str(project.id), str(new_job.id))
            # [FEATURE] Store the real Celery task id — required for the
            # cancel endpoint to actually revoke this task later. Without
            # this, cancel can only reset DB status while the GPU keeps
            # training underneath (there was previously nothing valid to
            # revoke: an earlier version passed the TrainingJob's own UUID,
            # which is not a Celery task id, and never worked).
            new_job.task_id = result.id
            db.commit()
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


# ─── CANCEL TRAINING ─────────────────────────────────────────────────────────
# [FEATURE] True cancel via Celery revoke. Previously this only reset DB
# status and cleared the gpu:state Redis key without actually stopping the
# running task (there was nothing valid to revoke — see TrainingJob.task_id).
# The GPU would keep training underneath a "cancelled" job.
@router.post("/{project_id}/cancel", response_model=schemas.ProjectStatusResponse)
def cancel_project_training(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
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

    # Update database tracking records instantly
    project.status = models.JobStatus.FAILED
    project.error_message = "Training was cancelled by the user."
    if latest_job:
        latest_job.status = models.JobStatus.FAILED
        latest_job.error_message = "Training was cancelled by the user."

    db.commit()
    db.refresh(project)

    # Snapshot the plain values we need before backgrounding anything.
    # [FIX] SQLAlchemy sessions/ORM instances aren't thread-safe, and
    # db.commit() above expires every attribute on objects in this session
    # (including latest_job) — the *next* access of latest_job.id/.task_id
    # would silently trigger a fresh SELECT on this same session. Doing
    # that from a background thread after this request has already
    # returned (and its session torn down by the get_db dependency) is
    # exactly the kind of thing that hangs or errors unpredictably. So:
    # read these two plain values now, on the main thread, while the
    # session is still alive, and never touch `latest_job` again below.
    _latest_job_id = latest_job.id if latest_job else None
    _latest_job_task_id = latest_job.task_id if latest_job else None

    # 🚀 SYSTEM SHIELD: Mark the active job as cancelled in Redis & Revoke Celery
    #
    # [FIX #1] redis.Redis.from_url() and celery_app.control.revoke() had no
    # timeouts, so a TLS/network hiccup against Upstash could hang forever —
    # freezing the whole single-worker API process behind it.
    #
    # [FIX #2 — the actual remaining bug] The previous fix ran this in a
    # `with ThreadPoolExecutor(...) as _pool:` block and called
    # future.result(timeout=8) to "abandon" a stuck call. That only stops
    # *waiting* on the future — it does NOT stop the thread. Exiting a
    # ThreadPoolExecutor context manager calls shutdown(wait=True) by
    # default, which then blocks on that same still-running thread anyway.
    # So the request was hanging a second time, right after logging that it
    # had "moved on". The DB status is already committed above and doesn't
    # need this cleanup to finish — so this now truly fires-and-forgets on a
    # daemon thread that's never joined. Worst case if Redis is having a bad
    # day: the gpu:state key and Celery revoke lag a few seconds behind the
    # DB, which already reads as cancelled either way.
    def _cleanup_redis_and_celery():
        try:
            import redis
            redis_url = settings.CELERY_BROKER_URL
            if "?" in redis_url:
                redis_url = redis_url.split("?")[0]

            _REDIS_TIMEOUT = 3
            if redis_url.startswith("rediss://"):
                _redis_client = redis.Redis.from_url(
                    redis_url, decode_responses=True, ssl_cert_reqs=None,
                    socket_connect_timeout=_REDIS_TIMEOUT, socket_timeout=_REDIS_TIMEOUT,
                )
            else:
                _redis_client = redis.Redis.from_url(
                    redis_url, decode_responses=True,
                    socket_connect_timeout=_REDIS_TIMEOUT, socket_timeout=_REDIS_TIMEOUT,
                )

            if _latest_job_id:
                # Flip the execution loop cancel flag — this is the *only*
                # cancel mechanism that's safe here. The training loop
                # already checks this flag at multiple checkpoints and
                # raises TrainingCancelledError cleanly on its own (see
                # worker/tasks.py, _is_cancel_requested).
                _redis_client.setex(f"job:{_latest_job_id}:cancel", 600, "1")
                print(f"🚀 Set cooperative cancel flag for job: {_latest_job_id}")

                # [FIX — CRITICAL] Previously also called
                # celery_app.control.revoke(task_id, terminate=True,
                # signal="SIGTERM"). This worker runs worker_pool="solo"
                # (see celery_app.py) — a single process with no forked
                # child to signal. Celery has no choice but to deliver that
                # SIGTERM to the *worker process itself*, killing the
                # entire worker, not just the task. That's why every
                # cancel required `docker compose restart` before another
                # training run would go through: cancel was committing
                # worker-process suicide. The cooperative flag above is
                # sufficient and safe — it's already how the loop exits on
                # cancel today (see the "Training cancellation sequence
                # initiated" log line right after every successful cancel).
                # If you ever move off worker_pool="solo" to a real
                # multiprocessing/prefork pool, terminate=True becomes
                # safe again (it kills the child process, not the parent)
                # and can be re-added for a faster/harder stop.

            _redis_client.delete("gpu:state")
            print("🚀 GPU runtime state lock released cleanly via cancel action route.")
        except Exception as e:
            print(f"Warning: background Redis/Celery cleanup after cancel failed: {e}")

    import threading
    threading.Thread(
        target=_cleanup_redis_and_celery,
        name=f"cancel-cleanup-{project_id}",
        daemon=True,
    ).start()

    # 🚀 FIX: Return the project model instance directly to fulfill the response schema
    # without trying to call path routing dependencies out of context.
    return project


# ─── GET PROJECT STATUS (RICH) ──────────────────────────────────────────────
@router.get("/{project_id}/status", response_model=schemas.ProjectStatusResponse)
def get_project_status(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Returns rich status for the training dashboard: progress, epoch, metrics, and logs."""
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
@router.get("/{project_id}/logs", response_model=List[schemas.JobLogResponse])
def get_project_logs(
    project_id: str,
    after: Optional[str] = None,
    limit: int = 200,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Returns log lines for the project's latest training job, optionally filtered by timestamp."""
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