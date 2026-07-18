import enum
import uuid
from datetime import datetime, timezone, date
from sqlalchemy import Column, Integer, String, DateTime, Date, ForeignKey, Enum, JSON, Text, Boolean, Table, Float, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base

# ─── ASSOCIATION TABLE: Project ↔ Dataset (M:M) ─────────────────────────────
# [PROJECT REFACTOR] New association table for project-dataset linking
project_datasets = Table(
    'project_datasets',
    Base.metadata,
    # [MERGED — matches a1b2c3d4e5f6_add_cascade_deletes.py, already applied
    # to the DB] ondelete=CASCADE was set at the DB level but never mirrored
    # here, so SQLAlchemy's own bookkeeping (and any ORM-level cascade
    # logic) was out of sync with the actual schema.
    Column('project_id', UUID(as_uuid=True), ForeignKey('projects.id', ondelete='CASCADE'), primary_key=True),
    Column('dataset_id', UUID(as_uuid=True), ForeignKey('datasets.id', ondelete='CASCADE'), primary_key=True)
)

# --- The Options (Enums) ---
class JobStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"   # Smart Ingestion
    TRAINING = "training"       # QLoRA Training
    COMPLETED = "completed"
    FAILED = "failed"

class DatasetType(str, enum.Enum):
    STRUCTURED = "structured"     # CSV/Excel
    UNSTRUCTURED = "unstructured" # PDF/Txt

# DeploymentStatus enum removed — deployment is now managed via Project.is_public + deploy_key

# --- The Tables ---

# [PROJECT REFACTOR] New Project table — the primary entity users interact with
class Project(Base):
    __tablename__ = "projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    name = Column(String, nullable=False)
    use_case = Column(String, default="education")

    # Immutable config (set at creation)
    persona = Column(Text, nullable=False)  # [FIX] Always set at training time (fallback to default if user skipped)
    few_shot_examples = Column(JSON, nullable=True)

    # Mutable config (updated when user configures & trains)
    base_model_name = Column(String, nullable=False)  # [FIX] Always set at training time
    hyperparameters = Column(JSON, nullable=True)

    # [TEMPERATURE FIX] Inference temperature for chat generation (0.0-2.0)
    # Set during Step 3 Configure wizard. Default 0.3 for factual RAG.
    inference_temperature = Column(Float, default=0.3)

    # Live training state (updated by Celery worker)
    status = Column(Enum(JobStatus), default=JobStatus.PENDING)
    progress = Column(Integer, default=0)  # 0-100
    epoch = Column(Integer, default=0)
    metrics = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)

    # ─── Deployment (Public API / Widget) ──────────────────────────────
    is_public = Column(Boolean, default=False, nullable=False)
    deploy_key = Column(String, unique=True, index=True, nullable=True)
    deploy_key_created_at = Column(DateTime, nullable=True)
    widget_config = Column(JSON, nullable=True)       # {primaryColor, position, greeting, title}
    allowed_origins = Column(JSON, nullable=True)      # ["https://school.edu"] or null = unrestricted

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    owner = relationship("User", back_populates="projects")
    datasets = relationship("Dataset", secondary=project_datasets, back_populates="projects")
    jobs = relationship("TrainingJob", back_populates="project", order_by="TrainingJob.created_at", cascade="all, delete-orphan")
    usage_records = relationship("DeploymentUsage", back_populates="project", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"

    # CHANGED: Integer -> UUID
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    full_name = Column(String, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    # ADDED: is_active flag for IAM authentication
    is_active = Column(Boolean, default=True) 
    # [MERGED from fyp_SLM--AI-Improved-Updated] True once the user has
    # clicked the verification link emailed on signup. Distinct from the
    # Verifalia deliverability check in /auth/check-email (which only says
    # "this address can probably receive mail", not "this person owns it").
    # Defaults False so existing rows read as unverified until they verify.
    is_email_verified = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    datasets = relationship("Dataset", back_populates="owner")
    jobs = relationship("TrainingJob", back_populates="owner")
    # [PROJECT REFACTOR] User owns multiple projects
    projects = relationship("Project", back_populates="owner")


# ─── PASSWORD RESET CODES ────────────────────────────────────────────────────
# [FEATURE] Backs the forgot-password email flow: a short-lived numeric code
# emailed to the user, which they exchange (along with a new password) for
# an actual password change. One row per requested code; old/used/expired
# rows are simply left in place (no cleanup job) since the volume is tiny
# and they carry no sensitive data beyond the code itself.
class PasswordResetCode(Base):
    __tablename__ = "password_reset_codes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    code = Column(String(6), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User")


# ─── REFRESH TOKENS ───────────────────────────────────────────────────────────
# [FEATURE] Backs the refresh-token flow: when the short-lived access token
# (ACCESS_TOKEN_EXPIRE_MINUTES) expires, the frontend exchanges one of these
# for a new access token instead of forcing a silent logout. Only the SHA-256
# hash of the token is stored — same reasoning as password hashing, so a DB
# read alone can't be replayed as a live session. Rotated (old row deleted,
# new row inserted) on every successful /auth/refresh call so a leaked token
# has a single-use window.
class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String, unique=True, index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    revoked = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User")


class Dataset(Base):
    __tablename__ = "datasets"

    # CHANGED: Integer -> UUID for PK and FK
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    name = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    dataset_type = Column(Enum(DatasetType), default=DatasetType.STRUCTURED)
    summary_path = Column(String, nullable=True)
    # [FEATURE] SHA-256 of the file's bytes. Column already existed in the DB
    # (added by a1b2c3d4e5f6_add_cascade_deletes.py) but was never mapped
    # here or written to — now used for automatic upload dedup, see
    # upload_helpers.find_dataset_by_hash().
    file_hash = Column(String, nullable=True, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    owner = relationship("User", back_populates="datasets")
    # [PROJECT REFACTOR] Dataset can belong to multiple projects
    projects = relationship("Project", secondary=project_datasets, back_populates="datasets")
    # Kept for backward compatibility — old TrainingJob records may reference this
    jobs = relationship("TrainingJob", back_populates="dataset")


class TrainingJob(Base):
    __tablename__ = "training_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # [PROJECT REFACTOR] New FK to Project (nullable for backward compatibility)
    # [MERGED] ondelete=CASCADE matches a1b2c3d4e5f6, already applied to the DB.
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True)
    # [PROJECT REFACTOR] version auto-increments per project (1, 2, 3...)
    version = Column(Integer, default=1)

    # [PROJECT REFACTOR] Made nullable — old jobs have these directly, new jobs inherit from Project
    dataset_id = Column(UUID(as_uuid=True), ForeignKey("datasets.id"), nullable=True)
    name = Column(String, nullable=True)
    base_model_name = Column(String, nullable=False)  # [FIX] Always set at training time
    use_case = Column(String, default="education")
    hyperparameters = Column(JSON, nullable=True)
    status = Column(Enum(JobStatus), default=JobStatus.PENDING)
    error_message = Column(Text, nullable=True)

    # ─── COLUMNS (now nullable for backward compatibility) ────────────────────
    persona = Column(Text, nullable=False)  # [FIX] Always set at training time (fallback to default if user skipped)
    few_shot_examples = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # [FEATURE] Celery task id, set at dispatch — lets the cancel endpoint
    # actually revoke the running task instead of just resetting DB status
    # while the GPU keeps training underneath. Nullable: old jobs (and any
    # job that failed before dispatch even happened) simply have none.
    task_id = Column(String, nullable=True)

    owner = relationship("User", back_populates="jobs")
    # [PROJECT REFACTOR] New relationship
    project = relationship("Project", back_populates="jobs")
    dataset = relationship("Dataset", back_populates="jobs")
    artifact = relationship("ModelArtifact", back_populates="job", uselist=False, cascade="all, delete-orphan")
    logs = relationship("JobLog", back_populates="job", order_by="JobLog.created_at", cascade="all, delete-orphan")


class ModelArtifact(Base):
    __tablename__ = "model_artifacts"

    # CHANGED: Integer -> UUID for PK and FK
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    job_id = Column(UUID(as_uuid=True), ForeignKey("training_jobs.id", ondelete="CASCADE"), nullable=False)

    # [PROJECT REFACTOR] Renamed from s3_path to adapter_path (L1 fix)
    adapter_path = Column(String, nullable=False)
    adapter_id = Column(String, unique=True, index=True) # Used for LoRAX
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    job = relationship("TrainingJob", back_populates="artifact")


class DeploymentUsage(Base):
    """One row per project per day — lightweight usage tracking."""
    __tablename__ = "deployment_usage"
    __table_args__ = (
        UniqueConstraint("project_id", "usage_date", name="uq_project_usage_date"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    usage_date = Column(Date, nullable=False)
    message_count = Column(Integer, default=0, nullable=False)

    project = relationship("Project", back_populates="usage_records")


class JobLog(Base):
    __tablename__ = "job_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    job_id = Column(UUID(as_uuid=True), ForeignKey("training_jobs.id", ondelete="CASCADE"), nullable=False, index=True)

    level = Column(String, nullable=False)   # INFO, WARNING, ERROR, SUCCESS
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    job = relationship("TrainingJob", back_populates="logs")