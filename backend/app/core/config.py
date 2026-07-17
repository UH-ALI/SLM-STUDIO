from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Core Application Database
    DATABASE_URL: str

    # Security Configuration
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Celery Background Tasks
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str

    # Third-Party API Keys & Execution Modes
    GROQ_API_KEY: str
    HF_TOKEN: str
    EXECUTION_MODE: str = "distributed"

    # CORS — comma-separated list of allowed frontend origins.
    # Defaults to localhost:3000; add production domain(s) via .env when deployed.
    ALLOWED_ORIGINS: str = "http://localhost:3000"

    # Public deployment base URL — used to generate embed snippets and public chat URLs.
    # Set this to your actual deployed domain in production.
    PUBLIC_API_BASE_URL: str = "http://localhost:8000"

    # Frontend URL — used to generate email verification / reset-password links.
    FRONTEND_URL: str = "http://localhost:3000"

    # ─── Email (Gmail SMTP) ───────────────────────────────────────────────────
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""          # your.email@gmail.com
    SMTP_PASSWORD: str = ""      # Gmail App Password (NOT your login password)
    SMTP_FROM_NAME: str = "SLM Studio"

    # Pydantic configuration to load the file
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        extra="ignore" # Safely ignores any extra system variables
    )

# Instantiate the settings singleton
settings = Settings()