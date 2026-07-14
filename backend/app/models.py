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
    Column('project_id', UUID(as_uuid=True), ForeignKey('projects.id'), primary_key=True),
    Column('dataset_id', UUID(as_uuid=True), ForeignKey('datasets.id'), primary_key=True)
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
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    datasets = relationship("Dataset", back_populates="owner")
    jobs = relationship("TrainingJob", back_populates="owner")
    # [PROJECT REFACTOR] User owns multiple projects
    projects = relationship("Project", back_populates="owner")


class Dataset(Base):
    __tablename__ = "datasets"

    # CHANGED: Integer -> UUID for PK and FK
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    name = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    dataset_type = Column(Enum(DatasetType), default=DatasetType.STRUCTURED)
    summary_path = Column(String, nullable=True)
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
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True)
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

    owner = relationship("User", back_populates="jobs")
    # [PROJECT REFACTOR] New relationship
    project = relationship("Project", back_populates="jobs")
    dataset = relationship("Dataset", back_populates="jobs")
    artifact = relationship("ModelArtifact", back_populates="job", uselist=False)
    logs = relationship("JobLog", back_populates="job", order_by="JobLog.created_at")


class ModelArtifact(Base):
    __tablename__ = "model_artifacts"

    # CHANGED: Integer -> UUID for PK and FK
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    job_id = Column(UUID(as_uuid=True), ForeignKey("training_jobs.id"), nullable=False)

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
    job_id = Column(UUID(as_uuid=True), ForeignKey("training_jobs.id"), nullable=False, index=True)

    level = Column(String, nullable=False)   # INFO, WARNING, ERROR, SUCCESS
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    job = relationship("TrainingJob", back_populates="logs")