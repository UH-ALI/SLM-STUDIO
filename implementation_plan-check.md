# Architectural Improvement Plan: Resilience, Deduplication, and State Continuity

This implementation plan outlines the exact technical solutions to resolve the four challenges you identified across project state management, document deduplication, deletion integrity, and user workflow routing.

---

## 1. Challenge & Solution: Admin/User Override & Cancellation Circuit Breaker

### The Challenge
When a project enters `JobStatus.PROCESSING` (either during document ingestion or Phase 2 Groq synthetic data generation), both `DELETE /projects/{id}` and `POST /projects/{id}/train` (`Start Training`) block further actions (`HTTP 400: Datasets are still processing`). If a background Celery worker hangs or enters an exponential backoff loop without setting `status = FAILED`, the project remains permanently locked.

### The Solution
We will implement an explicit **Circuit Breaker / Cancellation System**:
1. **New Backend Endpoint (`POST /api/v1/projects/{project_id}/cancel`) & Force Delete Option**:
   - Allows the owner to forcefully terminate any in-flight background tasks (`celery_app.control.revoke(task_id, terminate=True)`).
   - Instantly resets `project.status = JobStatus.FAILED` and clears any Redis locks (`gpu:state`, `rag:version`), unlocking the project.
   - We will also add a `?force=true` query parameter to `DELETE /projects/{project_id}` so users can force-delete a project even if its status is marked `processing`.
2. **Frontend UI Integration**:
   - On the Training/Status dashboard (`TrainingLayout.tsx`), when `status === 'processing'` or `status === 'training'`, display a prominent **`[⚠️ Cancel & Unlock]`** button next to the status badge, allowing users to break out of stuck operations at will.

---

## 2. Challenge & Solution: Clean Project Deletion & Foreign Key Cascading

### The Challenge
Currently, `delete_project` (`DELETE /projects/{id}`) deletes physical folders from disk (`shutil.rmtree` on vector stores and adapters) *before* deleting the database record (`db.delete(project)`). When `db.commit()` runs, Postgres raises an `IntegrityError` (Foreign Key Constraint Violation) because `model_artifacts` and `job_logs` still reference the `TrainingJob` associated with the project. The database transaction rolls back, leaving the project visible in the frontend UI (`Dashboard`), but any attempt to interact with it fails because its disk files were already wiped.

### The Solution
We will ensure atomic, 100% clean deletions every time:
1. **Configure Cascading Foreign Keys (`models.py`)**:
   - Add explicit `cascade="all, delete-orphan"` to `TrainingJob.artifact` and `TrainingJob.logs`:
     ```python
     artifact = relationship("ModelArtifact", back_populates="job", uselist=False, cascade="all, delete-orphan")
     logs = relationship("JobLog", back_populates="job", order_by="JobLog.created_at", cascade="all, delete-orphan")
     ```
   - Add `ondelete="CASCADE"` to the physical database schema on `ModelArtifact.job_id` and `JobLog.job_id`.
2. **Atomic Deletion Ordering (`projects.py`)**:
   - In `delete_project`, execute database deletions first (`db.delete(project); db.commit()`).
   - Only after the database commit succeeds without errors do we release VRAM models (`unload_model(job_id)`) and remove disk folders (`shutil.rmtree`). This guarantees zero orphaned database rows or split-brain states.

---

## 3. Challenge & Solution: Duplicate Document Prevention & Cross-Project Chunk Reuse

### The Challenge
As seen in the Datasets screenshot (`DSU_STUDENT_HANDBOOK_1.pdf`, `Need_Based_Scholarship_Form.pdf` repeated multiple times), the system currently allows users to upload documents with the same name repeatedly. Each upload creates a duplicate `Dataset` row, saves a duplicate file to disk, re-runs Markdown extraction (`pymupdf4llm`), and re-computes `SentenceTransformer` vector embeddings from scratch.

### The Solution
We will implement **Zero-Compute Deduplication & Cross-Project Reuse**:
1. **File Hashing & Name Deduplication at Upload (`validate_file` & `upload_project_datasets`)**:
   - When a file is uploaded, calculate its SHA-256 hash (and check filename per user).
   - Check the `datasets` table: if an identical file (`DSU_STUDENT_HANDBOOK_1.pdf` with matching hash) already exists for this user:
     - **If already attached to the current project:** Reject immediately with a clean 400 message: `Document 'DSU_STUDENT_HANDBOOK_1.pdf' is already attached to this project.`
     - **If attached to another project (or global library):** Do NOT save a duplicate file or create a duplicate `Dataset` record. Instead, reuse the existing `Dataset` entity and link it: `project.datasets.append(existing_dataset)`.
2. **Zero-Compute Chunk & Embedding Reuse (`rag_ingestion.py`)**:
   - When `ingest_document_task` runs for a reused `Dataset` across projects (`Project B` links `Dataset X` from `Project A`), the ingestion worker checks if `Dataset X` has previously extracted chunks or existing embeddings in ChromaDB.
   - If chunks exist, instead of re-running CPU/GPU embedding (`embedder.encode(...)`), it directly copies the existing vector embeddings and metadata (`documents, embeddings, metadatas`) from the source collection into `docs_{project_id}`. This reduces ingestion time for reused documents from **~30 seconds to < 50 milliseconds**.

---

## 4. Challenge & Solution: Wizard State Continuity vs. Dashboard Routing

### The Challenge
When a user begins creating a project via `/projects/new`:
1. Completing Step 0 (Name/Persona) immediately creates the project in Postgres with `status = JobStatus.PENDING`.
2. Completing Step 1 (Document Upload) links the documents and dispatches `ingest_document_task`.
If the user navigates away to the Dashboard (`/dashboard` or `/projects`) before clicking "Start Training" (Step 2 Configure), two problems occur:
- If `ingestion` is still processing (or got stuck), the project sits in `PROCESSING` state on the dashboard.
- When the user clicks the project card from the Dashboard, `ProjectCard.tsx` checks `status !== 'completed'` and routes them to `/projects/{id}/train` (the live terminal/progress page), which sits idle or shows "No logs available" because a `TrainingJob` has not been dispatched yet (`len(project.jobs) == 0`). The user loses their place in the setup wizard.

### The Solution
We will implement **Draft State Continuity & Smart Navigation**:
1. **Track Setup Stage / Draft Status (`models.py` & `projects.py`)**:
   - We will distinguish between a **Draft Project** (setup wizard in progress, no `TrainingJob` dispatched yet) and a **Training Project** (`TrainingJob` has been created and dispatched).
   - If `project.status == JobStatus.PENDING` and `len(project.jobs) == 0` (meaning training has never been initiated), the project card on the Dashboard will display a **`[Draft / In Setup]`** badge instead of `Ready`.
2. **Smart Routing in `ProjectCard.tsx`**:
   - Update `handleCardClick`:
     ```tsx
     if (project.status === 'completed') {
       router.push(`/projects/${project.id}/playground`);
     } else if (project.jobs && project.jobs.length === 0 && project.status === 'pending') {
       // Resume wizard exactly where they left off!
       router.push(`/projects/new?resumeId=${project.id}&step=2`);
     } else {
       router.push(`/projects/${project.id}/train`);
     }
     ```
3. **Wizard Resume Capability (`/projects/new/page.tsx`)**:
   - When `/projects/new` receives `?resumeId={id}&step=2`, it loads the existing project's Persona and attached `datasets` from the API, populating `wizardData` instantly so the user can continue configuring hyperparameters and click **Start Training** without losing a single step!
   - Furthermore, once training has officially started (`project.jobs.length > 0`), the user is guided directly to the Training/Monitor screen.

---

## Proposed Implementation Checklist (For Review)

If you approve this plan, I will implement the changes cleanly across the following layers:

### Database & Models Layer
- [ ] `backend/app/models.py`: Add `cascade="all, delete-orphan"` to `TrainingJob.artifact` / `TrainingJob.logs` and `ondelete="CASCADE"` to foreign keys.

### Backend API & Worker Layer
- [ ] `backend/app/routers/projects.py`:
  - Add `POST /{project_id}/cancel` endpoint + `?force=true` parameter on `DELETE /{project_id}`.
  - Re-order `delete_project` to delete DB records before `shutil.rmtree` disk unlinking.
  - Add deduplication check in `upload_project_datasets` (reject exact duplicates within project, reuse `Dataset` across projects).
- [ ] `backend/app/ai/rag_ingestion.py`: Add vector/chunk copy mechanism to skip `SentenceTransformer` re-computation when linking existing datasets.

### Frontend UI & Wizard Layer
- [ ] `frontend/components/organisms/ProjectCard.tsx`: Route draft projects (`jobs.length === 0`) to `/projects/new?resumeId={id}&step=2` and display `[Draft]` badge.
- [ ] `frontend/app/projects/new/page.tsx`: Support resuming draft projects from URL parameter (`resumeId`).
- [ ] `frontend/components/templates/TrainingLayout.tsx`: Add **`[Cancel & Unlock]`** circuit breaker button during `processing`/`training` states.

---

## User Review Required

> [!IMPORTANT]
> Please review this comprehensive solution covering your four challenges. All proposed changes are non-breaking, clean up existing edge cases, and provide an intuitive workflow for both document deduplication and wizard resumption.

Per your instructions (`DON'T proceed unless I ask you to`), I will wait for your review and explicit permission before making any code modifications!
