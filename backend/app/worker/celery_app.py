import multiprocessing
from celery import Celery
from app.core.config import settings  # Pydantic settings — reads validated values from .env

# --- CRITICAL CUDA FIX ---
# PyTorch and SentenceTransformers are not safe to use after a Unix fork().
# Forcing 'spawn' makes Celery create fresh child processes instead of forking,
# which allows the GPU to be initialised cleanly in each worker process.
try:
    multiprocessing.set_start_method('spawn', force=True)
except RuntimeError:
    # start method can only be set once — ignore if already set
    pass
# -------------------------

# Create the Celery application instance.
# broker  → Redis acts as the message queue (tasks are pushed here by the API)
# backend → Redis also stores task results so the API can poll job status
# Both URLs come from .env via Pydantic settings — no hardcoded values.
celery_app = Celery(
    "slm_worker",
    broker=settings.CELERY_BROKER_URL,       # e.g. redis://redis:6379/0
    backend=settings.CELERY_RESULT_BACKEND   # e.g. redis://redis:6379/0
)

# Tell Celery where to find the task functions (ingest_document_task, train_model_task)
celery_app.conf.imports = ["app.worker.tasks"]

# Track when a task moves from PENDING → STARTED so the API can report live progress
celery_app.conf.task_track_started = True

# --- CUDA POOL CONFIGURATION ---
# worker_pool = "solo" runs all tasks in the main process without forking.
# This is required because CUDA cannot be re-initialized in a forked subprocess.
# Combined with --pool=solo in docker-compose.yml command, this is bulletproof.
celery_app.conf.worker_pool = "solo"

# Only fetch one task at a time from Redis.
# Prevents a second GPU task from being reserved while the first is still running.
celery_app.conf.worker_prefetch_multiplier = 1