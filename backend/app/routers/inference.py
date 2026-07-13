import json
import os
import random
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.ai.rag_inference import generate_rag_response, generate_rag_response_stream, unload_model, free_all_memory, prewarm_model_async

from app.core.deps import get_current_user
from app.core.config import settings

router = APIRouter()


# ─── LEGACY ENDPOINTS (Backward Compatibility) ────────────────────────────────
# These endpoints use the old job_id + dataset_id contract.
# They are preserved so existing frontend code continues to work during transition.
# [FIX] For new jobs with project_id, RAG uses project-scoped collection.
# For old jobs without project_id, falls back to dataset-scoped collection.

@router.post("/chat", response_model=schemas.ChatResponse)
def chat_with_model(
    request: schemas.ChatRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Synchronous chat endpoint (legacy — uses job_id + dataset_id)."""

    job = db.query(models.TrainingJob).filter(
        models.TrainingJob.id == request.job_id,
        models.TrainingJob.user_id == current_user.id
    ).first()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found or unauthorized."
        )

    if job.status != models.JobStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot chat yet. Model status is: {job.status}"
        )

    # Validate dataset ownership (for legacy jobs)
    dataset = db.query(models.Dataset).filter(
        models.Dataset.id == request.dataset_id,
        models.Dataset.user_id == current_user.id
    ).first()

    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found or unauthorized."
        )

    custom_persona = job.persona

    # [FIX] For new jobs: use project_id for project-scoped RAG collection
    # For old jobs: fall back to dataset_id for legacy dataset-scoped collection
    project_id_for_rag = str(job.project_id) if job.project_id else str(request.dataset_id)

    try:
        result = generate_rag_response(
            job_id=str(job.id),
            project_id=project_id_for_rag,
            question=request.message,
            use_case=job.use_case,
            introduced=request.introduced,
            custom_persona=custom_persona,
            # [TEMPERATURE FIX] Use per-chat override if provided, else default 0.3
            temperature=request.temperature or 0.3
        )
        return {
            "response": result["response"],
            "citations": result["citations"]
        }

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        print(f"Inference Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during inference."
        )


@router.post("/chat/stream")
def chat_with_model_stream(
    request: schemas.ChatRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """SSE streaming chat endpoint (legacy — uses job_id + dataset_id)."""

    job = db.query(models.TrainingJob).filter(
        models.TrainingJob.id == request.job_id,
        models.TrainingJob.user_id == current_user.id
    ).first()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found or unauthorized."
        )

    if job.status != models.JobStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot chat yet. Model status is: {job.status}"
        )

    dataset = db.query(models.Dataset).filter(
        models.Dataset.id == request.dataset_id,
        models.Dataset.user_id == current_user.id
    ).first()

    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found or unauthorized."
        )

    custom_persona = job.persona

    # [FIX] For new jobs: use project_id for project-scoped RAG collection
    # For old jobs: fall back to dataset_id for legacy dataset-scoped collection
    project_id_for_rag = str(job.project_id) if job.project_id else str(request.dataset_id)

    def event_stream():
        try:
            for event in generate_rag_response_stream(
                job_id=str(job.id),
                project_id=project_id_for_rag,
                question=request.message,
                use_case=job.use_case,
                introduced=request.introduced,
                custom_persona=custom_persona,
                # [TEMPERATURE FIX] Use per-chat override if provided, else default 0.3
                temperature=request.temperature or 0.3
            ):
                yield f"data: {json.dumps(event)}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )


# ─── PROJECT-BASED INFERENCE ENDPOINTS (New) ──────────────────────────────
# [PROJECT REFACTOR] New endpoints that resolve job_id + dataset_id from project_id.
# The user thinks "chat with my Admission Bot" — the backend finds the latest
# successful TrainingJob and the project's combined dataset collection.

@router.post("/projects/{project_id}/chat", response_model=schemas.ChatResponse)
def chat_with_project(
    project_id: str,
    request: schemas.ProjectChatRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Synchronous chat endpoint for a project.
    Backend resolves the latest successful TrainingJob and uses the project's
    combined dataset collection (project_{project_id}).

    [TEMPERATURE FIX] Uses project's stored inference_temperature by default.
    User can override per-chat via request.temperature (hybrid approach).
    """
    # Verify project ownership
    project = db.query(models.Project).filter(
        models.Project.id == project_id,
        models.Project.user_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found or unauthorized."
        )

    # Resolve latest successful TrainingJob
    latest_job = db.query(models.TrainingJob).filter(
        models.TrainingJob.project_id == project_id,
        models.TrainingJob.status == models.JobStatus.COMPLETED
    ).order_by(models.TrainingJob.version.desc()).first()

    if not latest_job:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No trained model found for this project. Please train first."
        )

    # [TEMPERATURE FIX] Hybrid: per-chat override > project default > fallback 0.3
    temperature = request.temperature or project.inference_temperature or 0.3

    try:
        result = generate_rag_response(
            job_id=str(latest_job.id),
            project_id=project_id,
            question=request.message,
            use_case=project.use_case,
            introduced=request.introduced,
            custom_persona=project.persona,
            temperature=temperature
        )
        return {
            "response": result["response"],
            "citations": result["citations"]
        }

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        print(f"Inference Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during inference."
        )


@router.post("/projects/{project_id}/chat/stream")
def chat_with_project_stream(
    project_id: str,
    request: schemas.ProjectChatRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    SSE streaming chat endpoint for a project.
    Resolves latest successful TrainingJob automatically.

    [TEMPERATURE FIX] Uses project's stored inference_temperature by default.
    User can override per-chat via request.temperature (hybrid approach).
    """
    # Verify project ownership
    project = db.query(models.Project).filter(
        models.Project.id == project_id,
        models.Project.user_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found or unauthorized."
        )

    # Resolve latest successful TrainingJob
    latest_job = db.query(models.TrainingJob).filter(
        models.TrainingJob.project_id == project_id,
        models.TrainingJob.status == models.JobStatus.COMPLETED
    ).order_by(models.TrainingJob.version.desc()).first()

    if not latest_job:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No trained model found for this project. Please train first."
        )

    # [TEMPERATURE FIX] Hybrid: per-chat override > project default > fallback 0.3
    temperature = request.temperature or project.inference_temperature or 0.3

    def event_stream():
        try:
            for event in generate_rag_response_stream(
                job_id=str(latest_job.id),
                project_id=project_id,
                question=request.message,
                use_case=project.use_case,
                introduced=request.introduced,
                custom_persona=project.persona,
                temperature=temperature
            ):
                yield f"data: {json.dumps(event)}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )


# ─── H8: MANUAL VRAM UNLOAD ─────────────────────────────────────────────────
@router.post("/jobs/{job_id}/unload")
def unload_job_model(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Manually evicts a job's model from the VRAM cache, if it's loaded.
    Ownership is verified — a user can only unload their own models.
    """
    job = db.query(models.TrainingJob).filter(
        models.TrainingJob.id == job_id,
        models.TrainingJob.user_id == current_user.id
    ).first()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found or unauthorized."
        )

    was_loaded = unload_model(str(job.id))

    return {
        "job_id": str(job.id),
        "unloaded": was_loaded,
        "message": (
            "Model unloaded from VRAM."
            if was_loaded
            else "Model was not in the VRAM cache (already unloaded or never loaded)."
        )
    }

@router.delete("/system/vram", tags=["System"])
def clear_all_vram(secret: str):
    """
    Force clear ALL cached models from VRAM.
    Used by the Celery Worker before starting a memory-intensive training job.
    """
    if secret != settings.SECRET_KEY:
        raise HTTPException(status_code=401, detail="Invalid internal secret")
    
    free_all_memory()
    return {"message": "All API VRAM cleared successfully."}

@router.get("/projects/{project_id}/sample_prompts")
def get_sample_prompts(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Returns 3 sample prompts based on the actual training data (train.jsonl)
    for the latest successful training job of the project.
    - Factual question (from train.jsonl)
    - Out-of-context question (from train.jsonl)
    - Persona question
    """
    # Verify project ownership
    project = db.query(models.Project).filter(
        models.Project.id == project_id,
        models.Project.user_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    # Get latest successful job
    latest_job = db.query(models.TrainingJob).filter(
        models.TrainingJob.project_id == project_id,
        models.TrainingJob.status == 'completed'
    ).order_by(models.TrainingJob.created_at.desc()).first()

    if not latest_job:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No trained model found for this project."
        )

    job_dir = f"data/processed/job_{latest_job.id}"
    train_file = os.path.join(job_dir, "train.jsonl")

    factual_questions = []
    negative_questions = []

    if os.path.exists(train_file):
        with open(train_file, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip(): continue
                try:
                    data = json.loads(line)
                    instruction = data.get("instruction", "")
                    output = data.get("output", "")
                    if "This information is not available" in output:
                        negative_questions.append(instruction)
                    else:
                        factual_questions.append(instruction)
                except Exception:
                    continue

    factual = random.choice(factual_questions) if factual_questions else "What is the main topic of the document?"
    negative = random.choice(negative_questions) if negative_questions else "What does the author say about space travel?"
    
    persona_questions = [
        "Who are you?",
        "Who are you and what is your role?",
        "What is your role as an assistant?",
        "Introduce yourself.",
        "What can you help me with?"
    ]
    persona = random.choice(persona_questions)

    return {
        "factual": factual,
        "negative": negative,
        "persona": persona
    }


@router.post("/projects/{project_id}/prewarm", status_code=status.HTTP_202_ACCEPTED)
def prewarm_project_model(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Pre-warm base model and adapter into VRAM when user enters Playground."""
    project = (
        db.query(models.Project)
        .filter(models.Project.id == project_id, models.Project.user_id == current_user.id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    prewarm_model_async(project_id)
    return {"status": "prewarming", "project_id": project_id}