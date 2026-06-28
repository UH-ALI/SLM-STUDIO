from pydantic import BaseModel, EmailStr, field_validator, Field, ConfigDict
from datetime import datetime
from typing import Optional
from uuid import UUID
from typing import Optional, List, Dict, Any, Literal


# --- TOKEN SCHEMAS (For JWT Authentication) ---
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

# [PROJECT REFACTOR] Login response includes user object (Mismatch 2 fix)
class TokenWithUser(Token):
    user: "UserResponse"

# --- USER SCHEMAS ---

# 1. Base Schema (Shared properties)
class UserBase(BaseModel):
    email: EmailStr
    username: str

# 2. Create Schema (What the user sends to US)
# [PROJECT REFACTOR] Accepts firstName/lastName from frontend, combines to full_name internally
class UserCreate(UserBase):
    first_name: str = Field(alias="firstName")
    last_name: Optional[str] = Field(default="", alias="lastName")
    password: str

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v

# 3. Response Schema (What WE send back to the user)
# [PROJECT REFACTOR] CamelCase aliases for frontend compatibility
class UserResponse(UserBase):
    id: UUID
    full_name: str = Field(alias="fullName")
    is_active: bool = Field(alias="isActive")
    created_at: datetime = Field(alias="createdAt")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

# --- DATASET SCHEMAS ---
# [PROJECT REFACTOR] CamelCase aliases for frontend compatibility
class DatasetResponse(BaseModel):
    id: UUID
    name: str
    file_path: str = Field(alias="filePath")
    dataset_type: str = Field(alias="datasetType")
    user_id: UUID = Field(alias="userId")
    # [ALIAS FIX] Every other field on this schema has a camelCase alias;
    # this one was the odd one out. Single-word name so it wouldn't have looked
    # obviously wrong in JSON, but kept inconsistent the frontend would need to
    # special-case it.
    summary_path: Optional[str] = Field(default=None, alias="summaryPath")
    created_at: datetime = Field(alias="createdAt")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

# --- PROJECT SCHEMAS ---
# [PROJECT REFACTOR] New schemas for Project-centric architecture

class ProjectCreate(BaseModel):
    name: str
    use_case: str = Field(default="education", alias="useCase")
    persona: str
    few_shot_examples: Optional[List[Dict[str, str]]] = Field(default=None, alias="fewShotExamples")

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("persona")
    @classmethod
    def persona_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Persona cannot be empty")
        return v.strip()


class ProjectResponse(BaseModel):
    id: UUID
    name: str
    status: str
    use_case: str = Field(alias="useCase")
    persona: Optional[str] = None
    few_shot_examples: Optional[List[Dict[str, str]]] = Field(default=None, alias="fewShotExamples")
    datasets: Optional[List[DatasetResponse]] = Field(default_factory=list)
    base_model_name: Optional[str] = Field(default=None, alias="baseModelName")
    hyperparameters: Optional[Dict[str, Any]] = None
    inference_temperature: Optional[float] = Field(default=0.3, alias="inferenceTemperature")
    created_at: datetime = Field(alias="createdAt")
    updated_at: Optional[datetime] = Field(default=None, alias="updatedAt")

    # [STATUS FIX] No longer collapses "training" to "processing". The
    # frontend now has first-class support for a 'training' status across
    # Project.status / TrainingStatus type unions, the training-page mapping,
    # and the live progress components (TrainingPanel, LogPanel, TrainingOrb
    # all branch on 'training' explicitly, matching 'processing'). Masking it
    # here would silently break that — the value from the DB enum is passed
    # through as-is.
    @field_validator('status', mode='before')
    def map_status(cls, v):
        return v.value if hasattr(v, 'value') else v

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


# [PROJECT REFACTOR] Rich status response for training dashboard polling
class ProjectStatusResponse(BaseModel):
    id: UUID = Field(alias="id")
    name: str
    status: str
    model_name: Optional[str] = Field(default=None, alias="modelName")
    use_case: str = Field(alias="useCase")
    progress: float = 0.0
    epoch: int = 0
    metrics: Optional[Dict[str, Any]] = None
    logs: List[Dict[str, str]] = []
    # [TEMPERATURE FIX] Include temperature in status response
    inference_temperature: Optional[float] = Field(default=0.3, alias="inferenceTemperature")
    created_at: datetime = Field(alias="createdAt")
    error_message: Optional[str] = Field(default=None, alias="errorMessage")

    # [WARNING FIX] model_name would otherwise trigger Pydantic's reserved
    # protected-namespace warning on every import/response — harmless but
    # noisy in logs. Disabled specifically for this field.
    model_config = ConfigDict(populate_by_name=True, from_attributes=True, protected_namespaces=())


# [PROJECT REFACTOR] Request body for starting training (Step 3 wizard)
# [TEMPERATURE FIX] Includes inference temperature from frontend slider
class ProjectTrainRequest(BaseModel):
    base_model_name: str = Field(alias="baseModelName")
    hyperparameters: Dict[str, Any]
    # [TEMPERATURE FIX] Creativity control slider from frontend (0.0-2.0, default 0.3)
    inference_temperature: Optional[float] = Field(default=0.3, alias="inferenceTemperature")

    model_config = ConfigDict(populate_by_name=True)


# --- JOB SCHEMAS (Kept for backward compatibility) ---
class JobCreate(BaseModel):
    name: str
    dataset_id: UUID
    base_model_name: str = "SLM-Tiny-1"
    use_case: str = "education"
    persona: str
    few_shot_examples: Optional[List[Dict[str, str]]] = None
    hyperparameters: Optional[Dict[str, Any]] = None

    @field_validator("persona")
    @classmethod
    def persona_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Persona cannot be empty")
        return v.strip()


class JobResponse(BaseModel):
    id: UUID
    name: Optional[str] = None
    status: str
    base_model_name: str
    use_case: str
    # [FIX] dataset_id stays Optional — project-based jobs link through Project, not directly
    dataset_id: Optional[UUID] = None
    error_message: Optional[str] = None
    persona: str
    few_shot_examples: Optional[List[Dict[str, str]]] = None
    hyperparameters: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

# --- INFERENCE SCHEMAS ---
class ChatRequest(BaseModel):
    job_id: UUID = Field(alias="jobId")
    dataset_id: UUID = Field(alias="datasetId")
    message: str
    use_case: str = "education"
    introduced: bool = False
    # [TEMPERATURE FIX] Optional per-chat temperature override
    temperature: Optional[float] = None

    model_config = ConfigDict(populate_by_name=True)


# [PROJECT REFACTOR] New request for project-based chat
# [TEMPERATURE FIX] Optional per-chat temperature override (hybrid: overrides project default)
class ProjectChatRequest(BaseModel):
    message: str
    introduced: bool = False
    # [TEMPERATURE FIX] Optional per-chat temperature override (0.0-2.0)
    temperature: Optional[float] = None


class ChatResponse(BaseModel):
    response: str
    citations: List[Dict[str, str]] = []


# --- JOB LOG SCHEMAS ---
# [DATA SOVEREIGNTY FIX] Removed id and job_id — endpoint is already scoped to the project/job.
# The frontend does not need these identifiers in the log response.
class JobLogResponse(BaseModel):
    level: str
    message: str
    created_at: datetime = Field(alias="createdAt")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


# --- DEPLOYMENT SCHEMAS ---

class WidgetConfig(BaseModel):
    primary_color: str = Field(default="#4F46E5", alias="primaryColor")
    position: Literal["bottom-right", "bottom-left"] = "bottom-right"
    greeting: str = Field(default="Hi! Ask me anything.", max_length=300)
    title: Optional[str] = Field(default=None, max_length=80)

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("primary_color")
    @classmethod
    def validate_hex_color(cls, v: str) -> str:
        import re
        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", v):
            raise ValueError("primaryColor must be a 6-digit hex color, e.g. #4F46E5")
        return v


class DeployConfigUpdate(BaseModel):
    is_public: Optional[bool] = Field(default=None, alias="isPublic")
    widget_config: Optional[WidgetConfig] = Field(default=None, alias="widgetConfig")
    allowed_origins: Optional[List[str]] = Field(default=None, alias="allowedOrigins")

    model_config = ConfigDict(populate_by_name=True)


class DeployConfigResponse(BaseModel):
    is_public: bool = Field(alias="isPublic")
    deploy_key: Optional[str] = Field(default=None, alias="deployKey")
    embed_script: Optional[str] = Field(default=None, alias="embedScript")
    public_chat_url: Optional[str] = Field(default=None, alias="publicChatUrl")
    widget_config: Optional[WidgetConfig] = Field(default=None, alias="widgetConfig")
    allowed_origins: Optional[List[str]] = Field(default=None, alias="allowedOrigins")
    created_at: Optional[datetime] = Field(default=None, alias="createdAt")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class PublicChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)


class PublicChatResponse(BaseModel):
    response: str
    citations: List[Dict[str, Any]] = []


class PublicWidgetConfigResponse(BaseModel):
    title: str
    greeting: str
    primary_color: str = Field(alias="primaryColor")
    position: str

    model_config = ConfigDict(populate_by_name=True)
