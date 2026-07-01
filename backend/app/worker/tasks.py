import logging
import os
import uuid
from .celery_app import celery_app
from app.database import SessionLocal
from app.models import TrainingJob, Dataset, JobStatus, ModelArtifact, Project

# Import our decoupled AI modules
from app.ai.rag_ingestion import process_and_ingest_document
from app.ai.data_generator import generate_finetuning_data


logger = logging.getLogger(__name__)


def _write_log(db, job_id, level, message):
    """Write a log entry to the job_logs table."""
    from app.models import JobLog
    log = JobLog(
        job_id=job_id,
        level=level,
        message=message
    )
    db.add(log)
    db.commit()


# ─── TASK 1: THE RAG INGESTION WORKER ────────────────────────────────────────

@celery_app.task(name="ingest_document_task", bind=True)
def ingest_document_task(self, project_id: str, dataset_id: str):
    """
    [PROJECT REFACTOR] Now accepts project_id + dataset_id.
    Fires independently when a document is uploaded.
    Extracts Markdown, chunks text, and populates ChromaDB.

    If project_id is None, falls back to legacy dataset-only collection naming
    for backward compatibility.
    """
    # [DATA SOVEREIGNTY FIX] Generic log message — no UUIDs exposed
    logger.info("[Celery Worker] Document ingestion started")
    db = SessionLocal()

    try:
        dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
        if not dataset:
            # [DATA SOVEREIGNTY FIX] Generic error message
            logger.error("[Celery Worker] Dataset not found")
            return

        # Phase 1: Vectorize and store in ChromaDB
        # [PROJECT REFACTOR] Pass project_id for project-scoped collection naming
        process_and_ingest_document(
            project_id=project_id,
            dataset_id=str(dataset.id),
            file_path=dataset.file_path
        )

        # [DATA SOVEREIGNTY FIX] Generic success message
        logger.info("[Celery Worker] Document ingestion completed")

    except Exception as e:
        # [DATA SOVEREIGNTY FIX] Sanitized error — only exception type, no internal details
        logger.error(f"[Celery Worker] Ingestion failed: {type(e).__name__}")
        raise e

    finally:
        db.close()


# ─── TASK 2: THE SLM FINE-TUNING WORKER ──────────────────────────────────────

@celery_app.task(name="train_model_task", bind=True)
def train_model_task(self, project_id: str, job_id: str):
    """
    [PROJECT REFACTOR] Now accepts project_id + job_id.
    Fires when the user initiates a training run.
    Connects to the pre-built ChromaDB, generates JSONL, and runs QLoRA training.

    All config is read from the Project (the mutable source of truth).
    The TrainingJob is an immutable snapshot of the config at train time.
    """
    from app.ai.finetune import run_finetuning_pipeline  # Import here to avoid circular imports
    # [DATA SOVEREIGNTY FIX] Generic start message — no UUIDs
    logger.info("[Celery Worker] Training task started")
    db = SessionLocal()

    try:
        # [PROJECT REFACTOR] Read config from Project, not TrainingJob
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            logger.error("[Celery Worker] Project not found in database")
            return

        job = db.query(TrainingJob).filter(TrainingJob.id == job_id).first()
        if not job:
            logger.error("[Celery Worker] Training job not found in database")
            return

        # Update both Project and Job status
        project.status = JobStatus.PROCESSING
        project.progress = 10
        job.status = JobStatus.PROCESSING
        db.commit()
        # [DATA SOVEREIGNTY FIX] Generic log message — no UUIDs
        _write_log(db, job.id, "INFO", "Training task started")

        # Build the Persona Wrapper (using the AI team's strict boundaries)
        # [PROJECT REFACTOR] Read persona from Project
        persona_string = project.persona or (
            "You are a highly capable AI domain expert.\n"
            "Strictly adopt the following persona provided by the user:\n\n"
            "[START USER DEFINED PERSONA]\n"
            "You are an expert AI assistant specializing in the content of this document.\n"
            "You explain concepts clearly and concisely using simple language.\n"
            "When asked who you are, respond with: \"I am your AI assistant, here to help you understand this material. Ask me anything!\"\n"
            "You only answer questions grounded in the provided document.\n"
            "[END USER DEFINED PERSONA]\n\n"
            "UNBREAKABLE BOUNDARIES:\n"
            "- Answer entirely in the first-person voice of the role above.\n"
            "- Never break character or remind the user you are an AI.\n"
            "- If the context does not contain the answer, refuse politely in character:\n"
            "  'This information is not available in the provided document.'\n"
            "- Never fabricate facts."
        )

        # Phase 2: Data Generation Pipeline (Now reads from ChromaDB!)
        # [PROJECT REFACTOR] Pass project_id for project-scoped collection
        _write_log(db, job.id, "INFO", "Phase 2: Generating synthetic training data")
        # [DATA SOVEREIGNTY FIX] Generic log message
        logger.info("[Celery Worker] Phase 2: Generating synthetic training data")

        project.progress = 30
        db.commit()

        generate_finetuning_data(
            project_id=str(project_id),  # [PROJECT REFACTOR] was dataset_id
            job_id=str(job.id),
            use_case=project.use_case,
            persona=persona_string,
            few_shot_examples=project.few_shot_examples
        )

        # Phase 3: Fine-Tuning Pipeline
        # [PROJECT REFACTOR] Set TRAINING status and update progress
        project.status = JobStatus.TRAINING
        project.progress = 50
        job.status = JobStatus.TRAINING
        db.commit()
        _write_log(db, job.id, "INFO", "Phase 3: Fine-tuning model with QLoRA")
        # [DATA SOVEREIGNTY FIX] Generic log message
        logger.info("[Celery Worker] Phase 3: Fine-tuning model")

        # [PROJECT REFACTOR] Pass base_model_name from Project
        finetune_results = run_finetuning_pipeline(
            job_id=str(job.id),
            use_case=project.use_case,
            hyperparameters=project.hyperparameters or {},
            base_model_name=project.base_model_name
        )

        # Update progress during training (approximate)
        project.progress = 90
        db.commit()

        # Record the model artifact in the database
        _write_log(db, job.id, "INFO", "Saving model artifact")
        # [DATA SOVEREIGNTY FIX] Generic log message
        logger.info("[Celery Worker] Saving model artifact")

        # [PROJECT REFACTOR] Use adapter_path instead of s3_path (L1 fix)
        adapter_path = f"data/adapters/job_{job.id}"
        new_artifact = ModelArtifact(
            job_id=job.id,
            adapter_path=adapter_path
        )
        db.add(new_artifact)

        # Mark Success and update project state
        project.status = JobStatus.COMPLETED
        project.progress = 100
        project.epoch = project.hyperparameters.get("epochs", 3) if project.hyperparameters else 3
        # [L3 FIX] Store real metrics returned by finetune.py
        project.metrics = {
            "epoch": project.epoch,
            "trainLoss": finetune_results.get("train_loss"),
            "valLoss": finetune_results.get("val_loss"),
            "learningRate": finetune_results.get("learning_rate"),
            "gpuUtil": finetune_results.get("gpu_util"),
            "adapterSizeMb": finetune_results.get("adapter_size_mb"),
            "totalSteps": finetune_results.get("total_steps"),
            "finalLoss": finetune_results.get("final_loss"),
            "adapterPath": finetune_results.get("adapter_path"),
            "trainingHistory": finetune_results.get("training_history", []),
        }
        job.status = JobStatus.COMPLETED
        db.commit()

        _write_log(db, job.id, "SUCCESS", "Training completed successfully")
        # [DATA SOVEREIGNTY FIX] Generic success message
        logger.info("[Celery Worker] Training task completed successfully")

    except Exception as e:
        # [DATA SOVEREIGNTY FIX] Sanitized error — only exception type, no UUIDs or paths
        error_type = type(e).__name__
        logger.error(f"[Celery Worker] Training failed: {error_type}")

        if 'project' in locals() and project:
            project.status = JobStatus.FAILED
            # [DATA SOVEREIGNTY FIX] Sanitized error message
            project.error_message = f"Training failed: {error_type}"
            db.commit()

        if 'job' in locals() and job:
            job.status = JobStatus.FAILED
            # [DATA SOVEREIGNTY FIX] Sanitized error message
            job.error_message = f"Training failed: {error_type}"
            _write_log(db, job.id, "ERROR", f"Training failed: {error_type}")
            db.commit()

        raise e

    finally:
        db.close()