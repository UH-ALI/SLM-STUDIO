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
    ALLOWED_ORIGINS: str = "http://localhost:3000"

    # Public deployment base URL — used to generate embed snippets and public chat URLs.
    PUBLIC_API_BASE_URL: str = "http://localhost:8000"

    # Pydantic configuration to safely link settings with the env file
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        extra="ignore" # Crucial: safely bypasses keys like NGROK_AUTHTOKEN used by docker layers
    )

# Instantiate the settings singleton
settings = Settings()