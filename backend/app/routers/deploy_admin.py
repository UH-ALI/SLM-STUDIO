import secrets
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.core.deps import get_current_user
from app.core.config import settings

router = APIRouter()


# ─── HELPERS ─────────────────────────────────────────────────────────────────

def _owned_project(project_id: str, db: Session, user: models.User) -> models.Project:
    """Verify project ownership — reused across all endpoints."""
    project = db.query(models.Project).filter(
        models.Project.id == project_id,
        models.Project.user_id == user.id
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found or unauthorized")
    return project


def _build_response(project: models.Project) -> dict:
    """Build a standardized deploy config response."""
    base_url = settings.PUBLIC_API_BASE_URL.rstrip("/")
    embed_script = None
    public_chat_url = None

    if project.is_public and project.deploy_key:
        embed_script = (
            f'<script src="{base_url}/static/widget.js" '
            f'data-deploy-key="{project.deploy_key}"></script>'
        )
        public_chat_url = f"{base_url}/deploy/{project.deploy_key}/chat"

    return {
        "is_public": project.is_public,
        "deploy_key": project.deploy_key,
        "embed_script": embed_script,
        "public_chat_url": public_chat_url,
        "widget_config": project.widget_config,
        "allowed_origins": project.allowed_origins,
        "created_at": project.deploy_key_created_at,
    }


# ─── ENDPOINTS ───────────────────────────────────────────────────────────────

@router.get("/{project_id}/deploy", response_model=schemas.DeployConfigResponse)
def get_deploy_config(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Get the current deployment configuration for a project."""
    project = _owned_project(project_id, db, current_user)
    return _build_response(project)


@router.post("/{project_id}/deploy", response_model=schemas.DeployConfigResponse)
def enable_deploy(
    project_id: str,
    config: schemas.DeployConfigUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Enable or update deployment for a project.
    Generates a deploy key on first call.
    Requires at least one completed training job before going public.
    """
    project = _owned_project(project_id, db, current_user)

    # Guard: require a completed training before going public
    if config.is_public:
        has_completed = db.query(models.TrainingJob).filter(
            models.TrainingJob.project_id == project_id,
            models.TrainingJob.status == models.JobStatus.COMPLETED
        ).first()
        if not has_completed:
            raise HTTPException(
                status_code=400,
                detail="Train this project at least once before making it public."
            )

    # Generate deploy key on first activation
    if project.deploy_key is None:
        project.deploy_key = f"slm_{secrets.token_urlsafe(24)}"
        project.deploy_key_created_at = datetime.now(timezone.utc)

    # Apply config updates
    if config.is_public is not None:
        project.is_public = config.is_public
    if config.widget_config is not None:
        project.widget_config = config.widget_config.model_dump(by_alias=True)
    if config.allowed_origins is not None:
        project.allowed_origins = config.allowed_origins

    db.commit()
    db.refresh(project)
    return _build_response(project)


@router.delete("/{project_id}/deploy", response_model=schemas.DeployConfigResponse)
def disable_deploy(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Disable deployment — sets is_public to False."""
    project = _owned_project(project_id, db, current_user)
    project.is_public = False
    db.commit()
    db.refresh(project)
    return _build_response(project)


@router.post("/{project_id}/deploy/rotate", response_model=schemas.DeployConfigResponse)
def rotate_deploy_key(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Rotate deploy key — invalidates old key immediately, old widgets stop working."""
    project = _owned_project(project_id, db, current_user)
    project.deploy_key = f"slm_{secrets.token_urlsafe(24)}"
    project.deploy_key_created_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(project)
    return _build_response(project)


@router.get("/{project_id}/deploy/usage")
def get_deploy_usage(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Get the last 30 days of message usage for a deployed project."""
    project = _owned_project(project_id, db, current_user)
    rows = db.query(models.DeploymentUsage).filter(
        models.DeploymentUsage.project_id == project.id
    ).order_by(models.DeploymentUsage.usage_date.desc()).limit(30).all()
    return [{"date": r.usage_date.isoformat(), "messages": r.message_count} for r in rows]
