import logging

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db, engine, Base
from app import models  # Required so SQLAlchemy knows about the tables
from app.core.config import settings


# Docker's healthcheck curls /health every 10s, which floods `docker compose up`
# with a 200-OK access line each time and buries the log lines that matter.
# Dropping just those lines from uvicorn's access log keeps the healthcheck
# itself fully functional — only the noise goes.
class _HealthCheckLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return "GET /health " not in record.getMessage()


logging.getLogger("uvicorn.access").addFilter(_HealthCheckLogFilter())

# --- Import the routers ---
from app.routers import users, datasets, inference, auth, projects  # [PROJECT REFACTOR] Added projects
from app.routers import deploy_admin, deploy_public

# 1. Initialize the API
app = FastAPI(title="SLM Studio Backend")

# 2. Validation Error Handler
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    print(f"⚠️  422 VALIDATION ERROR on {request.method} {request.url}")
    print(f"⚠️  DETAIL: {exc.errors()}")
    # Convert any non-JSON-serializable objects (e.g., ValueError instances) to strings
    safe_errors = []
    for err in exc.errors():
        safe_err = dict(err)
        if "ctx" in safe_err and safe_err["ctx"]:
            safe_err["ctx"] = {
                k: str(v) for k, v in safe_err["ctx"].items()
            }
        safe_errors.append(safe_err)
    return JSONResponse(
        status_code=422,
        content={"detail": safe_errors}
    )

# 3. Configure CORS (Cross-Origin Resource Sharing)
# Origins are read from ALLOWED_ORIGINS in .env (comma-separated).
# Default is localhost:3000. In production, set this to your frontend domain.
origins = [origin.strip() for origin in settings.ALLOWED_ORIGINS.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 4. Create Tables on Startup (If they don't exist)
# Crucial for Docker deployments so you don't have to manually run migrations initially.
Base.metadata.create_all(bind=engine)

# --- Include the routers ---
app.include_router(auth.router,      prefix="/api/v1/auth",      tags=["Authentication"])
app.include_router(users.router,     prefix="/api/v1/users",     tags=["Users"])
app.include_router(datasets.router,  prefix="/api/v1/datasets",  tags=["Datasets"])
# [PROJECT REFACTOR] Mount projects router at both /projects and /jobs for backward compatibility
app.include_router(projects.router,  prefix="/api/v1/projects",  tags=["Projects"])
app.include_router(projects.router,  prefix="/api/v1/jobs",      tags=["Training Jobs"])  # Legacy compat
app.include_router(inference.router, prefix="/api/v1/inference", tags=["Inference"])
# [DEPLOY] Deploy admin endpoints (JWT-protected, dashboard)
app.include_router(deploy_admin.router, prefix="/api/v1/projects", tags=["Deployment"])

# --- Public Deployment Sub-App (Open CORS, No Auth) ---
deploy_app = FastAPI(title="SLM Deploy API")
deploy_app.include_router(deploy_public.router)
app.mount("/deploy", deploy_app)

# Custom middleware to handle Open CORS for /deploy endpoints BEFORE the strict parent CORS rejects it
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

class DeployCORSMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.url.path.startswith("/deploy"):
            if request.method == "OPTIONS":
                response = Response()
            else:
                response = await call_next(request)
            
            origin = request.headers.get("origin")
            if origin:
                response.headers["Access-Control-Allow-Origin"] = origin
            else:
                response.headers["Access-Control-Allow-Origin"] = "*"
                
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "*"
            response.headers["Access-Control-Allow-Credentials"] = "false"
            return response
            
        return await call_next(request)

# Add our custom deploy CORS middleware OUTSIDE the standard CORS middleware
app.add_middleware(DeployCORSMiddleware)

# --- Static Files (widget.js) ---
import os
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
from fastapi.staticfiles import StaticFiles
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# 5. Root Endpoint
@app.get("/")
def read_root():
    return {"message": "Welcome to SLM Studio! System is operational."}

# 6. Health Check Endpoint
@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    try:
        # "SELECT 1" is a lightweight ping to confirm the DB connection is alive
        db.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database connection failed: {str(e)}")