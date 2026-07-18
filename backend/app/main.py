import os
import time
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import text
from starlette.datastructures import Headers
from starlette.types import ASGIApp, Scope, Receive, Send

from app.database import get_db, engine, Base
from app import models  
from app.core.config import settings
from app.core.logging_config import setup_logging, get_logger, new_request_id, request_id_var

# [FEATURE] Structured JSON logging — see core/logging_config.py. Set up
# before anything else logs, so every subsequent log line (including ones
# emitted during startup below) is captured in the same format.
setup_logging()
logger = get_logger(__name__)

# 1. Initialize the Main API Application Stack
app = FastAPI(title="SLM Studio Backend")


# ─── REQUEST ID / STRUCTURED ACCESS LOG MIDDLEWARE ──────────────────────────
# [FEATURE] Generates (or forwards, if a caller/proxy already set one) a
# request ID, makes it available to every logger via request_id_var for the
# duration of the request, echoes it back as a response header (so a report
# of "this specific request failed" can be traced straight to matching log
# lines), and logs one structured line per request with method/path/status/
# duration.
class RequestIDMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        req_id = headers.get("x-request-id") or new_request_id()
        token = request_id_var.set(req_id)
        start = time.perf_counter()
        status_holder = {"code": None}

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_holder["code"] = message["status"]
                headers_list = list(message.get("headers", []))
                headers_list.append((b"x-request-id", req_id.encode()))
                message["headers"] = headers_list
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.info(
                "request completed",
                extra={
                    "method": scope.get("method"),
                    "path": scope.get("path"),
                    "status_code": status_holder["code"],
                    "duration_ms": duration_ms,
                },
            )
            request_id_var.reset(token)

app.add_middleware(RequestIDMiddleware)
# ──────────────────────────────────────────────────────────────────────────────


# ─── PURE ASGI MIDDLEWARE FOR SECURE REDIRECTS ──────────────────────────────
class ForwardedProtoMiddleware:
    """Forces secure 'https' scheme when passing through proxies like ngrok."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            headers = Headers(scope=scope)
            if headers.get("x-forwarded-proto") == "https":
                scope["scheme"] = "https"
        await self.app(scope, receive, send)

app.add_middleware(ForwardedProtoMiddleware)
# ──────────────────────────────────────────────────────────────────────────────


# 2. Advanced Validation Error Handler
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    print(f"⚠️  422 VALIDATION ERROR on {request.method} {request.url}")
    safe_errors = []
    for err in exc.errors():
        safe_err = dict(err)
        if "ctx" in safe_err and safe_err["ctx"]:
            safe_err["ctx"] = {k: str(v) for k, v in safe_err["ctx"].items()}
        safe_errors.append(safe_err)
    return JSONResponse(status_code=422, content={"detail": safe_errors})


# ─── CUSTOM SPLIT-CORS ARCHITECTURE ──────────────────────────────────────────
# 3. Configure Parent Application CORS Pipeline
origins_raw = settings.ALLOWED_ORIGINS.replace('"', '').replace("'", "")
origins = [origin.strip() for origin in origins_raw.split(",") if origin.strip()]

for allowed_origin in [
    "https://daisy-flammable-remindful.ngrok-free.dev",
    "https://no-code-slm-studio.vercel.app",
]:
    if allowed_origin not in origins:
        origins.append(allowed_origin)


class SplitCORSMiddleware:
    """
    Dynamically routes CORS preflight options and traffic.
    Public widget endpoints (/api/v1/deploy) process wide-open wildcard access,
    while all administrative/private endpoints remain under strict origin verification.
    """
    def __init__(self, app: ASGIApp):
        self.app = app
        
        # Strict CORS for administrative/private endpoints
        self.strict_cors = CORSMiddleware(
            app,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=[
                "Authorization",
                "Content-Type",
                "Accept",
                "Origin",
                "X-Requested-With",
                "ngrok-skip-browser-warning",
                "Cache-Control",
                "X-Accel-Buffering"
            ],
            expose_headers=["*"],
        )
        
        # Public, open CORS for widgets and embeds
        self.public_cors = CORSMiddleware(
            app,
            allow_origins=["*"],
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["*"],
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in ("http", "websocket"):
            path = scope.get("path", "")
            # Intercept and route requests destined for the deployment sub-app early
            if path.startswith("/api/v1/deploy"):
                await self.public_cors(scope, receive, send)
                return
        
        # Default to strict CORS for all parent paths
        await self.strict_cors(scope, receive, send)


# Register our smart split-CORS layer first
app.add_middleware(SplitCORSMiddleware)


@app.middleware("http")
async def add_dynamic_vercel_cors(request, call_next):
    """Dynamic middleware layer to handle dynamic wildcards for Vercel previews."""
    origin = request.headers.get("origin")
    response = await call_next(request)
    
    if origin and (origin.endswith(".vercel.app") or origin in origins):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = (
            "Authorization, Content-Type, Accept, Origin, X-Requested-With, "
            "ngrok-skip-browser-warning, Cache-Control, X-Accel-Buffering"
        )
        response.headers["Access-Control-Expose-Headers"] = "*"
    return response
# ──────────────────────────────────────────────────────────────────────────────


# 4. Create Tables on Startup
Base.metadata.create_all(bind=engine)

# [FEATURE] Same automated cleanup as the worker (see app/startup_maintenance.py
# and app/worker/celery_app.py) — run here too since the API container might
# come up before or independently of the worker, and the DB-reconciliation
# half of this (resetting orphaned projects/jobs, fixing renamed model IDs)
# doesn't depend on having a Celery connection. Queue purging is left to the
# worker only, since that's the process actually connected to it.
from app.startup_maintenance import run_startup_cleanup
run_startup_cleanup(purge_queue=False)


# ─── CORE ROUTER ARCHITECTURE MOUNTING ───────────────────────────────────────
from app.routers import auth, users, datasets, projects, deploy_admin, deploy_public, inference

app.include_router(auth.router,      prefix="/api/v1/auth",      tags=["Authentication"])
app.include_router(users.router,     prefix="/api/v1/users",     tags=["Users"])
app.include_router(datasets.router,  prefix="/api/v1",           tags=["Datasets"])  
app.include_router(projects.router,  prefix="/api/v1/projects",  tags=["Projects"])
app.include_router(projects.router,  prefix="/api/v1/jobs",      tags=["Training Jobs"])  
app.include_router(inference.router, prefix="/api/v1/inference", tags=["Inference"])
app.include_router(deploy_admin.router, prefix="/api/v1/projects", tags=["Deployment"])


# ─── STANDALONE PUBLIC DEPLOYMENT SUB-APP ────────────────────────────────────
deploy_app = FastAPI(title="SLM Deploy API")

# Public sub-app definition leaves credentials wide open
deploy_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

deploy_app.include_router(deploy_public.router)
app.mount("/api/v1/deploy", deploy_app)
# ──────────────────────────────────────────────────────────────────────────────


# ─── STATIC WIDGET ROUTING ───────────────────────────────────────────────────
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/api/v1/static", StaticFiles(directory=static_dir), name="static")


# 5. Root Entrypoint
@app.get("/")
def read_root():
    return {"message": "Welcome to SLM Studio! System is operational."}


# 6. Comprehensive Health Check Engine
# [FEATURE] Expanded from a DB-only check into a real readiness probe:
# also pings Redis (Celery broker / GPU-state coordination) and reports
# whether the GPU is visible to torch. Each check is independent — a Redis
# or GPU problem is reported in the response rather than raising, so the
# endpoint keeps returning useful diagnostics instead of a bare 500.
@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    result = {"status": "healthy", "database": "connected", "redis": "unknown", "gpu": "unknown"}
    overall_ok = True

    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        result["status"] = "unhealthy"
        result["database"] = f"error: {str(e)}"
        overall_ok = False

    try:
        from app.core.rate_limit import _redis
        _redis.ping()
        result["redis"] = "connected"
    except Exception as e:
        result["redis"] = f"error: {str(e)}"
        overall_ok = False

    try:
        import torch
        result["gpu"] = "available" if torch.cuda.is_available() else "unavailable"
    except Exception as e:
        # Not fatal to overall health — CPU-only environments (e.g. a plain
        # API container without a worker) are expected to report this.
        result["gpu"] = f"error: {str(e)}"

    if not overall_ok:
        result["status"] = "unhealthy"
        raise HTTPException(status_code=503, detail=result)

    return result