"""
Automates the manual recovery routine that previously had to be run by hand
after a crashed/bad training run:

  1. `docker compose exec worker celery -A app.worker.tasks purge -f`
  2. a one-off Python script resetting the affected project/job DB rows
  3. `docker compose restart worker api`

All three of those are now automatic: this module runs once at startup
(called from both app/main.py and app/worker/celery_app.py, since either
container might come up first) and:

  - purges any pending tasks sitting in the Celery/Redis queue
  - resets any Project/TrainingJob left in a non-terminal state (PENDING,
    PROCESSING, TRAINING) to FAILED, since a fresh process start means
    whatever was tracking that job is gone — it's orphaned, not actually
    still running
  - normalizes any stored `base_model_name` that references one of the
    known-broken (renamed) HuggingFace repo IDs to the corrected one, so
    existing projects created before the finetune.py fix don't keep
    failing forever

Controlled by AUTO_CLEANUP_STALE_TASKS_ON_STARTUP (default: on). This is
purely additive — it runs once, before anything else touches the queue or
DB, and doesn't change how training/inference/tasks actually work.
"""

import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

# [FIX] Maps old, renamed/broken HuggingFace repo IDs to their corrected
# equivalents (see app/ai/finetune.py for the full explanation). Any
# existing project/job still pointing at one of these gets silently
# corrected on next startup instead of failing forever.
_BROKEN_MODEL_NAME_FIXES = {
    "unsloth/Qwen3-1.7B-bnb-4bit": "unsloth/Qwen3-1.7B-unsloth-bnb-4bit",
    "unsloth/Qwen3-4B-bnb-4bit": "unsloth/Qwen3-4B-unsloth-bnb-4bit",
}


def run_startup_cleanup(purge_queue: bool = True) -> None:
    """
    Call once at process startup. Safe to call from both the API and the
    worker — each does its own independent DB reconciliation pass, and only
    the worker actually needs to (and is able to) purge the Celery queue.
    """
    if not settings.AUTO_CLEANUP_STALE_TASKS_ON_STARTUP:
        return

    if purge_queue:
        _purge_stale_queue()

    _fix_broken_model_names()
    _reset_orphaned_jobs()


def _purge_stale_queue() -> None:
    try:
        # Local import — avoids a circular import between celery_app.py and
        # this module (celery_app.py itself is where `celery_app` lives).
        from app.worker.celery_app import celery_app

        purged = celery_app.control.purge()
        logger.info(f"[Startup Cleanup] Purged {purged or 0} stale task(s) from the queue.")
    except Exception as e:
        logger.error(f"[Startup Cleanup] Failed to purge queue ({type(e).__name__}) — continuing anyway.")


def _fix_broken_model_names() -> None:
    try:
        from app.database import SessionLocal
        from app.models import Project

        db = SessionLocal()
        try:
            fixed_count = 0
            for broken_name, corrected_name in _BROKEN_MODEL_NAME_FIXES.items():
                affected = db.query(Project).filter(Project.base_model_name == broken_name).all()
                for project in affected:
                    project.base_model_name = corrected_name
                    fixed_count += 1
            if fixed_count:
                db.commit()
                logger.info(f"[Startup Cleanup] Corrected {fixed_count} project(s) pointing at a renamed/broken model repo.")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"[Startup Cleanup] Failed to fix broken model names ({type(e).__name__}).")


def _reset_orphaned_jobs() -> None:
    try:
        from app.database import SessionLocal
        from app.models import Project, TrainingJob, JobStatus

        non_terminal = [JobStatus.PENDING, JobStatus.PROCESSING, JobStatus.TRAINING]

        db = SessionLocal()
        try:
            orphaned_projects = db.query(Project).filter(Project.status.in_(non_terminal)).all()
            for project in orphaned_projects:
                project.status = JobStatus.FAILED
                project.error_message = (
                    "Training was interrupted by a container restart and has been "
                    "reset automatically. Please start training again."
                )

            orphaned_jobs = db.query(TrainingJob).filter(TrainingJob.status.in_(non_terminal)).all()
            for job in orphaned_jobs:
                job.status = JobStatus.FAILED

            if orphaned_projects or orphaned_jobs:
                db.commit()
                logger.info(
                    f"[Startup Cleanup] Reset {len(orphaned_projects)} orphaned project(s) "
                    f"and {len(orphaned_jobs)} orphaned job(s) left in a non-terminal state."
                )
        finally:
            db.close()
    except Exception as e:
        logger.error(f"[Startup Cleanup] Failed to reset orphaned jobs ({type(e).__name__}).")
