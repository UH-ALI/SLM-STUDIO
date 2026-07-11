import json
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.ai.rag_inference import generate_rag_response, generate_rag_response_stream
from app.core.rate_limit import check_rate_limit

router = APIRouter()


# ─── DEPENDENCIES ────────────────────────────────────────────────────────────

def get_project_by_deploy_key(deploy_key: str, db: Session = Depends(get_db)) -> models.Project:
    """Validate deploy key and return the associated project."""
    project = db.query(models.Project).filter(
        models.Project.deploy_key == deploy_key,
        models.Project.is_public == True,  # noqa: E712
    ).first()
    if not project:
        raise HTTPException(status_code=401, detail="Invalid or disabled deploy key")
    return project


def _check_origin(project: models.Project, request: Request):
    """Per-deployment CORS origin lock — validates the caller's origin."""
    if not project.allowed_origins:
        return  # No restriction configured
    origin = request.headers.get("origin") or request.headers.get("referer", "")
    if not any(origin.startswith(allowed) for allowed in project.allowed_origins):
        raise HTTPException(status_code=403, detail="This origin is not authorized for this deploy key")


def _resolve_latest_job(project: models.Project, db: Session) -> models.TrainingJob:
    """Find the latest completed training job for a project."""
    latest_job = db.query(models.TrainingJob).filter(
        models.TrainingJob.project_id == project.id,
        models.TrainingJob.status == models.JobStatus.COMPLETED,
    ).order_by(models.TrainingJob.version.desc()).first()
    if not latest_job:
        raise HTTPException(status_code=503, detail="This assistant isn't ready yet. Please check back soon.")
    return latest_job


def _track_usage(project_id, db: Session):
    """Upsert today's usage counter."""
    today = date.today()
    usage = db.query(models.DeploymentUsage).filter(
        models.DeploymentUsage.project_id == project_id,
        models.DeploymentUsage.usage_date == today,
    ).first()
    if usage:
        usage.message_count += 1
    else:
        db.add(models.DeploymentUsage(project_id=project_id, usage_date=today, message_count=1))
    db.commit()


# ─── ENDPOINTS ───────────────────────────────────────────────────────────────

@router.get("/{deploy_key}/config", response_model=schemas.PublicWidgetConfigResponse)
def get_public_widget_config(deploy_key: str, db: Session = Depends(get_db)):
    """Called by widget.js on load to fetch branding. No rate limit — cheap read."""
    project = get_project_by_deploy_key(deploy_key, db)
    cfg = project.widget_config or {}
    return {
        "title": cfg.get("title") or project.name,
        "greeting": cfg.get("greeting", "Hi! Ask me anything."),
        "primaryColor": cfg.get("primaryColor", "#4F46E5"),
        "bodyColor": cfg.get("bodyColor", "#F8F9FB"),
        "dotsColor": cfg.get("dotsColor", "#9CA3AF"),
        "botMessageColor": cfg.get("botMessageColor", "#FFFFFF"),
        "userMessageColor": cfg.get("userMessageColor", ""),
        "chatInputColor": cfg.get("chatInputColor", "#FFFFFF"),
        "position": cfg.get("position", "bottom-right"),
    }


@router.post("/{deploy_key}/chat", response_model=schemas.PublicChatResponse)
def public_chat(
    deploy_key: str,
    request_body: schemas.PublicChatRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Synchronous chat endpoint — for curl/developer integrations (Path B)."""
    project = get_project_by_deploy_key(deploy_key, db)
    _check_origin(project, request)
    check_rate_limit(key=f"deploy:{deploy_key}")

    latest_job = _resolve_latest_job(project, db)

    try:
        result = generate_rag_response(
            job_id=str(latest_job.id),
            project_id=str(project.id),
            question=request_body.message,
            use_case=project.use_case,
            introduced=False,
            custom_persona=project.persona,
            temperature=project.inference_temperature or 0.3,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Something went wrong generating a response. Please try again.")

    _track_usage(project.id, db)

    return {"response": result["response"], "citations": result["citations"]}


@router.post("/{deploy_key}/chat/stream")
def public_chat_stream(
    deploy_key: str,
    request_body: schemas.PublicChatRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    SSE streaming chat endpoint — for the widget (Path A).
    Tokens appear in real-time, same as the Playground chat.
    """
    project = get_project_by_deploy_key(deploy_key, db)
    _check_origin(project, request)
    check_rate_limit(key=f"deploy:{deploy_key}")

    latest_job = _resolve_latest_job(project, db)

    def event_stream():
        try:
            for event in generate_rag_response_stream(
                job_id=str(latest_job.id),
                project_id=str(project.id),
                question=request_body.message,
                use_case=project.use_case,
                introduced=False,
                custom_persona=project.persona,
                temperature=project.inference_temperature or 0.3,
            ):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception:
            yield f'data: {json.dumps({"error": "Something went wrong. Please try again."})}\n\n'

    _track_usage(project.id, db)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )
