import json
import os
import random
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.ai.rag_inference import (
    generate_rag_response, 
    generate_rag_response_stream, 
    unload_model, 
    free_all_memory, 
    prewarm_model_async
)

from app.core.deps import get_current_user
from app.core.config import settings

router = APIRouter()


# ─── LEGACY ENDPOINTS (Backward Compatibility) ────────────────────────────────

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
    project_id_for_rag = str(job.project_id) if job.project_id else str(request.dataset_id)

    try:
        from app.ai.rag_inference import DEFAULT_TEMPERATURE_BY_USE_CASE
        default_temp = DEFAULT_TEMPERATURE_BY_USE_CASE.get((job.use_case or "general").lower(), 0.3)
        result = generate_rag_response(
            job_id=str(job.id),
            project_id=project_id_for_rag,
            question=request.message,
            use_case=job.use_case,
            introduced=request.introduced,
            custom_persona=custom_persona,
            temperature=request.temperature or default_temp
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
    project_id_for_rag = str(job.project_id) if job.project_id else str(request.dataset_id)

    from app.ai.rag_inference import DEFAULT_TEMPERATURE_BY_USE_CASE
    default_temp = DEFAULT_TEMPERATURE_BY_USE_CASE.get((job.use_case or "general").lower(), 0.3)

    def event_stream():
        try:
            for event in generate_rag_response_stream(
                job_id=str(job.id),
                project_id=project_id_for_rag,
                question=request.message,
                use_case=job.use_case,
                introduced=request.introduced,
                custom_persona=custom_persona,
                temperature=request.temperature or default_temp
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


# ─── PROJECT-BASED INFERENCE ENDPOINTS ───────────────────────────────────────

@router.post("/projects/{project_id}/chat", response_model=schemas.ChatResponse)
@router.post("/projects/{project_id}/chat/", response_model=schemas.ChatResponse)
def chat_with_project(
    project_id: str,
    request: schemas.ProjectChatRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Synchronous chat endpoint for a project."""
    project = db.query(models.Project).filter(
        models.Project.id == project_id,
        models.Project.user_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found or unauthorized."
        )

    latest_job = db.query(models.TrainingJob).filter(
        models.TrainingJob.project_id == project_id,
        models.TrainingJob.status == models.JobStatus.COMPLETED
    ).order_by(models.TrainingJob.version.desc()).first()

    if not latest_job:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No trained model found for this project. Please train first."
        )

    from app.ai.rag_inference import DEFAULT_TEMPERATURE_BY_USE_CASE
    _domain_default = DEFAULT_TEMPERATURE_BY_USE_CASE.get((project.use_case or "general").lower(), 0.3)
    temperature = request.temperature or project.inference_temperature or _domain_default

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
@router.post("/projects/{project_id}/chat/stream/")
def chat_with_project_stream(
    project_id: str,
    request: schemas.ProjectChatRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """SSE streaming chat endpoint for a project (Supports Playground UI)."""
    project = db.query(models.Project).filter(
        models.Project.id == project_id,
        models.Project.user_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found or unauthorized."
        )

    latest_job = db.query(models.TrainingJob).filter(
        models.TrainingJob.project_id == project_id,
        models.TrainingJob.status == models.JobStatus.COMPLETED
    ).order_by(models.TrainingJob.version.desc()).first()

    if not latest_job:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No trained model found for this project. Please train first."
        )

    from app.ai.rag_inference import DEFAULT_TEMPERATURE_BY_USE_CASE
    _domain_default = DEFAULT_TEMPERATURE_BY_USE_CASE.get((project.use_case or "general").lower(), 0.3)
    temperature = request.temperature or project.inference_temperature or _domain_default

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


# ─── VRAM LOGISTICS MANAGEMENT ───────────────────────────────────────────────

@router.post("/jobs/{job_id}/unload")
@router.post("/jobs/{job_id}/unload/")
def unload_job_model(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Manually evicts a job's model from the VRAM cache, if it's loaded."""
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
        "message": "Model unloaded from VRAM." if was_loaded else "Model was not loaded."
    }


@router.delete("/system/vram", tags=["System"])
def clear_all_vram(secret: str):
    """Force clear ALL cached models from VRAM before training runs."""
    if secret != settings.SECRET_KEY:
        raise HTTPException(status_code=401, detail="Invalid internal secret")
    free_all_memory()
    return {"message": "All API VRAM cleared successfully."}


# ─── SAMPLE PROMPTS & PREWARMING ──────────────────────────────────────────────

@router.get("/projects/{project_id}/sample_prompts")
@router.get("/projects/{project_id}/sample_prompts/")
def get_sample_prompts(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Fetches sample prompt options for UI presentation."""
    project = db.query(models.Project).filter(
        models.Project.id == project_id,
        models.Project.user_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

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
        "Who are you?", "Who are you and what is your role?", 
        "What is your role as an assistant?", "Introduce yourself."
    ]
    persona = random.choice(persona_questions)

    return {
        "factual": factual,
        "negative": negative,
        "persona": persona
    }


@router.post("/projects/{project_id}/prewarm", status_code=status.HTTP_202_ACCEPTED)
@router.post("/projects/{project_id}/prewarm/", status_code=status.HTTP_202_ACCEPTED)
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
        
    try:
        prewarm_model_async(project_id)
    except Exception as e:
        print(f"⚠️ Prewarm execution bypassed internal exceptions: {e}")
        
    return {"status": "prewarming", "project_id": project_id}