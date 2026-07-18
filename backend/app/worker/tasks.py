import logging
import os
import uuid
import requests
import redis
import time
from sqlalchemy.orm import Session

from app.worker.celery_app import celery_app
from app.database import SessionLocal
from app.models import TrainingJob, Dataset, JobStatus, ModelArtifact, Project
from app.ai.rag_ingestion import process_and_ingest_document
from app.ai.data_generator import generate_finetuning_data
from app.core.config import settings

logger = logging.getLogger(__name__)

# --- Redis Client Coordination with Upstash Strict TLS Compatibility ---
redis_url = settings.CELERY_BROKER_URL
if "?" in redis_url:
    redis_url = redis_url.split("?")[0]
    
# Configure secure SSL contexts explicitly for Upstash compatibility
if redis_url.startswith("rediss://"):
    _redis_client = redis.Redis.from_url(redis_url, decode_responses=True, ssl_cert_reqs=None)
else:
    _redis_client = redis.Redis.from_url(redis_url, decode_responses=True)


class TrainingCancelledError(Exception):
    """Raised when the user cancels an in-flight training task."""


def _mark_cancel_requested(job_id: str) -> None:
    try:
        _redis_client.setex(f"job:{job_id}:cancel", 600, "1")
    except Exception as exc:
        logger.warning("Failed to mark cancel flag for job %s: %s", job_id, exc)


def _clear_cancel_requested(job_id: str) -> None:
    try:
        _redis_client.delete(f"job:{job_id}:cancel")
    except Exception as exc:
        logger.warning("Failed to clear cancel flag for job %s: %s", job_id, exc)


def _is_cancel_requested(job_id: str) -> bool:
    try:
        return _redis_client.get(f"job:{job_id}:cancel") == "1"
    except Exception as exc:
        logger.warning("Failed to check cancel flag for job %s: %s", job_id, exc)
        return False


def _write_log(db: Session, job_id: str, level: str, message: str):
    """Write an immutable entry to the job logs table."""
    from app.models import JobLog
    log = JobLog(job_id=job_id, level=level, message=message)
    db.add(log)
    db.commit()

from celery.signals import worker_ready

@worker_ready.connect
def bootstrap_cleanup_handler(sender, **kwargs):
    """
    🚀 AUTOMATION HOOK: Runs automatically the exact millisecond the worker connects to the broker.
    Clears out lingering GPU locks and stale cancel keys from Cloud Upstash.
    """
    logger.info("🧹 Running automated cloud infrastructure startup cleanup...")
    try:
        # 1. Clear the global GPU execution state lock
        _redis_client.delete("gpu:state")
        
        # 2. Scan and clear any abandoned cancel indicators
        keys = _redis_client.keys("job:*:cancel")
        if keys:
            for k in keys:
                _redis_client.delete(k)
            logger.info(f"✨ Automated sweep completed: Dropped {len(keys)} dead cancel flags.")
        else:
            logger.info("✨ Automated sweep completed: No lingering cancel flags found.")
            
    except Exception as exc:
        logger.error(f"❌ Automated startup cleanup failed: {exc}")


# ─── TASK 1: THE RAG INGESTION WORKER ────────────────────────────────────────

@celery_app.task(name="ingest_document_task", bind=True)
def ingest_document_task(self, project_id: str, dataset_id: str):
    """Asynchronous document ingestion worker task."""
    logger.info(f"🚀 [Celery Worker] Document ingestion started")
    db = SessionLocal()

    try:
        dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
        if not dataset:
            logger.error("[Celery Worker] Aborted: Target dataset record not found.")
            return

        dataset.status = "processing"
        db.commit()

        process_and_ingest_document(
            project_id=project_id,
            dataset_id=str(dataset.id),
            file_path=dataset.file_path
        )

        db.refresh(dataset)
        dataset.status = "completed"
        db.commit()
        logger.info(f"✨ [Celery Worker] Document ingestion completed")

    except Exception as e:
        logger.error(f"[Celery Worker] Ingestion failed: {type(e).__name__}")
        try:
            db.rollback()
        except Exception:
            pass

        try:
            failed_ds = db.query(Dataset).filter(Dataset.id == dataset_id).first()
            if failed_ds:
                failed_ds.status = "failed"
                failed_ds.error_message = str(e)
                db.commit()
        except Exception as db_err:
            logger.critical(f"Failed to commit dataset error fallback state: {db_err}")
        raise e

    finally:
        try:
            db.close()
        except Exception:
            pass


# ─── TASK 2: THE SLM FINE-TUNING WORKER ──────────────────────────────────────

@celery_app.task(name="train_model_task", bind=True)
def train_model_task(self, project_id: str, job_id: str):
    """QLoRA Fine-Tuning execution pipeline task."""
    from app.ai.finetune import run_finetuning_pipeline
    from celery.exceptions import Ignore
    logger.info(f"🚀 [Celery Worker] Training task started")
    
    # 🚀 FIX: Explicitly clear any stale cancel flags for this job ID right at startup
    _clear_cancel_requested(job_id)
    
    db = SessionLocal()
    try:
        time.sleep(1.0)

        project = db.query(Project).filter(Project.id == project_id).first()
        job = db.query(TrainingJob).filter(TrainingJob.id == job_id).first()

        if not project or not job:
            logger.error("[Celery Worker] Aborted: Associated project or job properties missing from database context.")
            return

        project.status = JobStatus.PROCESSING
        project.progress = 10
        job.status = JobStatus.PROCESSING
        db.commit()
        _write_log(db, job.id, "INFO", "Training task started")

        if _is_cancel_requested(job_id):
            raise TrainingCancelledError("Training was cancelled by the user.")

        persona_string = project.persona or (
            "You are a helpful, professional AI assistant built using SLM Studio.\n"
            "1. For standard greetings, pleasantries, or questions about your identity (e.g., 'hi', 'who are you'), reply naturally, politely, and concisely.\n"
            "2. For factual or domain-specific questions, answer clearly and concisely using only the provided document context.\n"
            "3. If a factual question cannot be answered using the document context, gracefully state that the information is not present in the document."
        )

        _write_log(db, job.id, "INFO", "Phase 2: Generating synthetic training data")
        logger.info("[Celery Worker] Phase 2: Generating synthetic training data")
        project.progress = 30
        db.commit()

        if _is_cancel_requested(job_id):
            raise TrainingCancelledError("Training was cancelled by the user.")

        generate_finetuning_data(
            project_id=str(project_id),
            job_id=str(job.id),
            use_case=project.use_case,
            persona=persona_string,
            few_shot_examples=project.few_shot_examples
        )

        try:
            db.close()
        except Exception:
            pass

        db = SessionLocal()
        project = db.query(Project).filter(Project.id == project_id).first()
        job = db.query(TrainingJob).filter(TrainingJob.id == job_id).first()

        project.status = JobStatus.TRAINING
        project.progress = 50
        job.status = JobStatus.TRAINING
        db.commit()
        _write_log(db, job.id, "INFO", "Phase 3: Fine-tuning model with QLoRA")
        logger.info("[Celery Worker] Phase 3: Fine-tuning model")

        if _is_cancel_requested(job_id):
            raise TrainingCancelledError("Training was cancelled by the user.")

        _redis_client.set("gpu:state", "draining", ex=30)
        from app.ai.rag_inference import get_active_inference_count, free_all_memory
        
        for _ in range(10):
            if get_active_inference_count() == 0:
                break
            time.sleep(0.5)

        _redis_client.set("gpu:state", "training", ex=600)
        free_all_memory()

        vram_cleared = False
        for host in ["http://api:8000", "http://127.0.0.1:8000", "http://localhost:8000"]:
            try:
                resp = requests.delete(f"{host}/api/v1/inference/system/vram", params={"secret": settings.SECRET_KEY}, timeout=3)
                if resp.status_code == 200:
                    vram_cleared = True
                    break
            except Exception:
                continue

        finetune_results = run_finetuning_pipeline(
            job_id=str(job.id),
            use_case=project.use_case,
            hyperparameters=project.hyperparameters or {},
            base_model_name=project.base_model_name
        )

        try:
            db.close()
        except Exception:
            pass

        db = SessionLocal()
        project = db.query(Project).filter(Project.id == project_id).first()
        job = db.query(TrainingJob).filter(TrainingJob.id == job_id).first()

        project.progress = 90
        db.commit()

        adapter_path = f"data/adapters/job_{job.id}"
        db.add(ModelArtifact(job_id=job.id, adapter_path=adapter_path))

        project.status = JobStatus.COMPLETED
        project.progress = 100
        project.epoch = project.hyperparameters.get("epochs", 3) if project.hyperparameters else 3
        project.metrics = {
            "epoch": project.epoch,
            "trainLoss": finetune_results.get("train_loss"),
            "valLoss": finetune_results.get("val_loss"),
            "learningRate": finetune_results.get("learning_rate"),
            "gpuUtil": finetune_results.get("gpu_util"),
            "adapterSizeMb": finetune_results.get("adapter_size_mb"),
            "totalSteps": finetune_results.get("total_steps"),
            "finalLoss": finetune_results.get("final_loss"),
            "adapterPath": adapter_path,
            "trainingHistory": finetune_results.get("training_history", []),
        }
        job.status = JobStatus.COMPLETED
        db.commit()

        _write_log(db, job.id, "SUCCESS", "Training completed successfully")
        logger.info("[Celery Worker] Training task completed successfully")

    except TrainingCancelledError as e:
        logger.info("[Celery Worker] Training cancellation sequence initiated.")
        try:
            db.close()
        except Exception:
            pass

        # 🚀 AUTOMATED ON-CANCEL CLEANUP ROUTINE
        logger.info("🧹 Training halted. Running automated cloud cache sweep...")
        try:
            # 1. Clear out the specific cancel flag for this job ID from Upstash
            _clear_cancel_requested(job_id)
            
            # 2. Force-delete the global GPU state lock so retries work instantly
            _redis_client.delete("gpu:state")
            
            # 3. Scan and clear any other dead cancel keys to prevent stuck jobs
            keys = _redis_client.keys("job:*:cancel")
            for k in keys:
                _redis_client.delete(k)
                
            logger.info(f"✨ Cloud Upstash sweep completed successfully.")
        except Exception as cache_err:
            logger.error(f"❌ Automated on-cancel sweep failed: {cache_err}")

        # Non-blocking write to the Neon Postgres log table
        db = SessionLocal()
        try:
            _write_log(db, job_id, "WARNING", "Training execution halted by user request.")
        except Exception as log_err:
            logger.warning(f"Could not write final cancellation log: {log_err}")
        finally:
            db.close()

        # Natively drop out to Celery smoothly
        raise Ignore()
    except Exception as e:
        error_type = type(e).__name__
        logger.error(f"[Celery Worker] Training failed: {error_type}")
        try:
            db.close()
        except Exception:
            pass
            
        db = SessionLocal()
        project = db.query(Project).filter(Project.id == project_id).first() if project_id else None
        job = db.query(TrainingJob).filter(TrainingJob.id == job_id).first() if job_id else None

        if project:
            project.status = JobStatus.FAILED
            project.error_message = f"Training failed: {error_type}"
        if job:
            job.status = JobStatus.FAILED
            job.error_message = f"Training failed: {error_type}"
            _write_log(db, job.id, "ERROR", f"Training failed: {error_type}")
        db.commit()
        raise e

    finally:
        _clear_cancel_requested(job_id)
        try:
            _redis_client.delete("gpu:state")
            logger.info("[Celery Worker] GPU state cleared — inference can resume.")
        except Exception:
            pass
        try:
            if db:
                db.close()
        except Exception:
            pass