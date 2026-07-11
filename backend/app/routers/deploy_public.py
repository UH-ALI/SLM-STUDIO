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

    import urllib.parse

    incoming = request.headers.get("origin") or request.headers.get("referer", "")
    if not incoming:
        raise HTTPException(status_code=403, detail="Missing Origin or Referer header")

    parsed_incoming = urllib.parse.urlparse(incoming)
    if not parsed_incoming.scheme or not parsed_incoming.netloc:
        raise HTTPException(status_code=403, detail="Invalid Origin or Referer header format")

    # Exact match on scheme://netloc — NOT startswith. A prefix check would let
    # "https://example.com.evil.com" pass for an allowed "https://example.com".
    incoming_norm = f"{parsed_incoming.scheme}://{parsed_incoming.netloc}"
    if incoming_norm not in project.allowed_origins:
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
        "bodyColor": cfg.get("bodyColor", "#FFFFFF"),
        "dotsColor": cfg.get("dotsColor", "#9CA3AF"),
        "botMessageColor": cfg.get("botMessageColor", "#2A3441"),
        "userMessageColor": cfg.get("userMessageColor", "#4F46E5"),
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

    # Extract primitives before entering the generator. The generator body
    # runs *after* this function returns (StreamingResponse iterates it
    # lazily), by which point FastAPI may already have torn down the
    # request-scoped `db` session and the ORM objects tied to it — so we
    # pull out plain strings here rather than closing over `project`/`latest_job`.
    job_id_str = str(latest_job.id)
    project_id_str = str(project.id)
    use_case_str = project.use_case
    persona_str = project.persona
    temperature_float = project.inference_temperature or 0.3

    def event_stream():
        success = False
        try:
            for event in generate_rag_response_stream(
                job_id=job_id_str,
                project_id=project_id_str,
                question=request_body.message,
                use_case=use_case_str,
                introduced=False,
                custom_persona=persona_str,
                temperature=temperature_float,
            ):
                yield f"data: {json.dumps(event)}\n\n"
            success = True
        except Exception:
            yield f'data: {json.dumps({"error": "Something went wrong. Please try again."})}\n\n'

        if success:
            # Only count the message if the stream actually completed. Use a
            # fresh session — the original request-scoped `db` is no longer
            # safe to touch from inside a generator running post-response.
            try:
                from app.database import SessionLocal
                with SessionLocal() as session:
                    _track_usage(project_id_str, session)
            except Exception:
                pass  # Usage tracking is non-critical — never break the chat over it

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )
