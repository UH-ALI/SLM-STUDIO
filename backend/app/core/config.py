from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    # Core Application Database
    DATABASE_URL: str

    # Security Configuration
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    # How long an unused refresh token stays valid. Long-lived by design —
    # this is what lets a session survive the short access token expiring.
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Celery Background Tasks
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str

    # Third-Party API Keys & Execution Modes
    GROQ_API_KEY: str
    HF_TOKEN: str
    EXECUTION_MODE: str = "distributed"

    # CORS — comma-separated list of allowed frontend origins.
    ALLOWED_ORIGINS: str = "http://localhost:3000"

    # Public deployment base URL — used to generate embed snippets and public chat URLs.
    PUBLIC_API_BASE_URL: str = "http://localhost:8000"

    # ─── EMAIL (SMTP) ────────────────────────────────────────────────────────
    # [FIX] All optional with no required fields: an existing deployment's .env
    # won't have these yet, and Pydantic would otherwise refuse to start the
    # app entirely over a missing *optional* feature's config. The email
    # service checks these at call time and skips sending (logging a warning)
    # rather than crashing, if they're unset.
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM_EMAIL: Optional[str] = None
    SMTP_FROM_NAME: str = "SLM Studio"
    SMTP_USE_TLS: bool = True

    # ─── VERIFALIA (email deliverability check on signup) ───────────────────
    VERIFALIA_USERNAME: Optional[str] = None
    VERIFALIA_PASSWORD: Optional[str] = None

    # Frontend base URL — used for links inside outbound emails.
    FRONTEND_BASE_URL: str = "http://localhost:3000"

    # ─── STARTUP AUTO-CLEANUP ────────────────────────────────────────────────
    # [FEATURE] Automates the manual "purge Celery queue + reset orphaned
    # DB state" recovery routine that previously had to be run by hand
    # (docker exec ... celery purge, then a one-off Python script) any time
    # a crashed/bad training run left stale tasks sitting in the Redis
    # queue. Runs automatically on both API and worker startup. Set to
    # "false" if you ever need tasks/jobs to survive a container restart
    # (e.g. multiple concurrent long jobs you don't want reset on deploy).
    AUTO_CLEANUP_STALE_TASKS_ON_STARTUP: bool = True

    # Pydantic configuration to safely link settings with the env file
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        extra="ignore" # Crucial: safely bypasses keys like NGROK_AUTHTOKEN used by docker layers
    )

# Instantiate the settings singleton
settings = Settings()