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
celery_app = Celery(
    "slm_worker",
    broker=settings.CELERY_BROKER_URL,       # e.g. rediss://...
    backend=settings.CELERY_RESULT_BACKEND   # e.g. rediss://...
)

# Tell Celery where to find the task functions
celery_app.conf.imports = ["app.worker.tasks"]

# Track when a task moves from PENDING → STARTED so the API can report live progress
celery_app.conf.task_track_started = True

# Explicitly sets connection retry behaviors to match upcoming Celery 6.0 standards
celery_app.conf.broker_connection_retry_on_startup = True

# --- CUDA POOL CONFIGURATION ---
# worker_pool = "solo" runs all tasks in the main process without forking.
celery_app.conf.worker_pool = "solo"

# Only fetch one task at a time from Redis.
celery_app.conf.worker_prefetch_multiplier = 1

# --- CRITICAL FIX FOR UPSTASH + SOLO POOL DEADLOCK ---
celery_app.conf.update(
    # 1. Disable Celery's application-level heartbeats.
    # Since 'solo' blocks the thread during PyTorch runs, it will miss heartbeats 
    # and cause Upstash to drop the connection.
    broker_heartbeat=0,

    # 2. Force TCP Keepalive at the OS layer.
    # This keeps the Upstash connection open even while the Python GIL is locked by PyTorch.
    broker_transport_options={
        "socket_keepalive": True,
        # visibility_timeout defines how long before Redis assumes a task failed and requeues it.
        # Set this slightly higher than your longest possible PyTorch execution time. (e.g., 43200 = 12 hours)
        "visibility_timeout": 43200, 
    },
    
    # 3. Apply the same Keepalive rules to the result backend 
    # so the worker doesn't hang when trying to report Task Success.
    redis_backend_transport_options={
        "socket_keepalive": True,
        "retry_on_timeout": True,
    },

    # 4. Limit the connection pool. 
    # A 'solo' worker only processes one thing at a time, so it only needs 1 or 2 connections.
    # This prevents you from blowing past Upstash Free Tier limits.
    broker_pool_limit=1,
    redis_max_connections=2,
)