"""
Structured logging setup.

Why this exists (see NEXT_STEPS.md #8): errors currently only go to
container stdout as unstructured text, which is why past investigations
(e.g. the Qwen3 VRAM issue) meant reading raw Celery tracebacks by hand
across three different `docker logs` calls. This module makes every log
line a single JSON object with a consistent shape — including a request_id
that's the same across the FastAPI request, any Celery task it dispatches
(if the task ID is logged), and every log line the request touches — so an
error can be found by grepping/filtering one field instead of correlating
timestamps by eye.

This is additive: it doesn't remove or rewrite the existing print()/logger
calls scattered through the codebase (those still work, just unstructured).
New code, or code you touch next, can adopt `get_logger(__name__)` from here
to get structured output for free.
"""
import contextvars
import json
import logging
import sys
import time
import uuid
from datetime import datetime, timezone

# Holds the current request's ID for the lifetime of that request/task, so
# any logger anywhere in the call stack can include it without threading it
# through every function signature.
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_var.get(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        # Allow callers to attach extra structured fields, e.g.
        # logger.info("training started", extra={"project_id": pid})
        for key, value in record.__dict__.items():
            if key not in payload and key not in (
                "args", "msg", "levelname", "levelno", "pathname", "filename",
                "module", "exc_info", "exc_text", "stack_info", "lineno",
                "funcName", "created", "msecs", "relativeCreated", "thread",
                "threadName", "processName", "process", "name",
            ):
                payload[key] = value
        return json.dumps(payload, default=str)


def setup_logging(level: int = logging.INFO) -> None:
    """Call once at process startup (API and worker both)."""
    root = logging.getLogger()
    root.setLevel(level)
    # Avoid duplicate handlers if setup_logging() is ever called twice
    # (e.g. once from main.py, once from a Celery worker bootstrap).
    root.handlers = []
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def new_request_id() -> str:
    return uuid.uuid4().hex[:16]
