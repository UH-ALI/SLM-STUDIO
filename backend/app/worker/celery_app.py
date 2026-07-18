import ssl
import multiprocessing
from celery import Celery
from celery.signals import worker_ready
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
    broker=settings.CELERY_BROKER_URL,       # e.g. rediss://... (with health_check_interval/ssl args removed)
    backend=settings.CELERY_RESULT_BACKEND   # e.g. rediss://... (with health_check_interval/ssl args removed)
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

    # 2. Force TCP Keepalive at the OS layer + Inject Safe Health Checks.
    # This keeps the Upstash connection open even while the Python GIL is locked by PyTorch.
    broker_transport_options={
        "socket_keepalive": True,
        "health_check_interval": 30,  # Safely handle checks on the socket network loop
        # visibility_timeout defines how long before Redis assumes a task failed and requeues it.
        # Set this slightly higher than your longest possible PyTorch execution time. (e.g., 43200 = 12 hours)
        "visibility_timeout": 43200, 
    },
    
    # 3. Apply the same Keepalive and Health Check rules to the result backend 
    # so the worker doesn't hang when trying to report Task Success.
    redis_backend_transport_options={
        "socket_keepalive": True,
        "retry_on_timeout": True,
        "health_check_interval": 30,  # Safely configured for backend connection pool as well
    },

    # 4. Enforce Strict Verification Contexts over SSL
    # This securely validates Upstash targets via standard TLS and silences SecurityWarning errors.
    broker_use_ssl={
        "ssl_cert_reqs": ssl.CERT_REQUIRED
    },
    redis_backend_use_ssl={
        "ssl_cert_reqs": ssl.CERT_REQUIRED
    },

    # 5. Limit the connection pool. 
    # A 'solo' worker only processes one thing at a time, so it only needs 1 or 2 connections.
    # This prevents you from blowing past Upstash Free Tier limits.
    broker_pool_limit=1,
    redis_max_connections=2,
)


# ─── AUTOMATED STARTUP CLEANUP ────────────────────────────────────────────────
# [FEATURE] Automates the manual "purge queue + reset orphaned DB state"
# recovery routine (previously two separate `docker compose exec` commands
# run by hand after any crashed/bad training run). Fires once, after the
# worker has fully connected and is about to start consuming tasks — see
# app/startup_maintenance.py for exactly what this does and how to disable
# it (AUTO_CLEANUP_STALE_TASKS_ON_STARTUP=false in .env).
@worker_ready.connect
def _run_startup_cleanup(sender=None, **kwargs):
    from app.startup_maintenance import run_startup_cleanup
    run_startup_cleanup(purge_queue=True)