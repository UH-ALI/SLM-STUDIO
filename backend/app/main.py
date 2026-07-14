import os
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.database import get_db, engine, Base
from app import models  # Required so SQLAlchemy knows about the tables
from app.core.config import settings

# --- Import the routers ---
from app.routers import users, datasets, inference, auth, projects  # [PROJECT REFACTOR] Added projects
from app.routers import deploy_admin, deploy_public

# 1. Initialize the API
app = FastAPI(title="SLM Studio Backend")


# ─── MIDDLEWARE FOR SECURE REDIRECTS (FIXES MIXED CONTENT) ──────────────────
class ForwardedProtoMiddleware(BaseHTTPMiddleware):
    """
    Forces FastAPI's routing scope to respect the secure 'https' scheme
    when running behind a secure SSL proxy (like ngrok).
    """
    async def dispatch(self, request, call_next):
        proto = request.headers.get("x-forwarded-proto")
        if proto == "https":
            request.scope["scheme"] = "https"
        return await call_next(request)

# Register early in the middleware stack
app.add_middleware(ForwardedProtoMiddleware)
# ──────────────────────────────────────────────────────────────────────────────


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
# Strip any stray quotes just in case, then split
origins_raw = settings.ALLOWED_ORIGINS.replace('"', '').replace("'", "")
origins = [origin.strip() for origin in origins_raw.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 4. Create Tables on Startup (If they don't exist)
Base.metadata.create_all(bind=engine)


# --- Include the routers ---
app.include_router(auth.router,      prefix="/api/v1/auth",      tags=["Authentication"])
app.include_router(users.router,     prefix="/api/v1/users",     tags=["Users"])
app.include_router(datasets.router,  prefix="/api/v1",           tags=["Datasets"])  # Mounted at v1 base
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
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")


# 5. Root Endpoint
@app.get("/")
def read_root():
    return {"message": "Welcome to SLM Studio! System is operational."}


# 6. Health Check Endpoint
@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database connection failed: {str(e)}")