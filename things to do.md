# Future Features & Backlog (Things To Do)

## 1. Downloadable Form / Document Attachment Links in RAG Chat Responses
* **Status**: Planned (Future Release)
* **Feature Description**:
  When a user asks for a specific form or document (e.g., *"I want the admission form"*), the assistant should not only answer from the RAG knowledge base, but also provide a direct, clickable file download link or attachment card (`📎 Download admission_form.pdf`) in the chat UI.
* **Technical Roadmap**:
  1. **Backend (`rag_inference.py`)**: `retrieve_context()` already returns document citations (`citations = [{"source": "admission_form.pdf", ...}]`).
  2. **File API**: Ensure `/api/v1/projects/{project_id}/files/{filename}` serves the original uploaded PDF/DOCX file securely.
  3. **Frontend / Widget**: Inspect response citation metadata and render a downloadable file attachment card directly below the assistant's message bubble.

## 2. Implement Cloud Object Storage (S3/GCS) for Persistent Data
* **Status**: Planned (Production Readiness)
* **Feature Description**:
  Currently, raw PDFs, generated `train.jsonl` files, and trained model adapters are stored locally in the `./backend/data/` folder (bind mount). This causes issues when cloning a fresh repository or deploying across multiple servers. We need to migrate file and adapter storage to a cloud object store (like AWS S3) or a centralized model registry.
* **Technical Roadmap**:
  1. **Backend API**: Refactor file upload endpoints to push raw documents directly to an S3 bucket and save the S3 URI in PostgreSQL instead of a local file path.
  2. **Worker/Celery**: Refactor data generation and training jobs to pull raw files from S3, generate datasets locally during execution, push `train.jsonl` to S3, and push the final compiled LoRA adapter directory to an S3 bucket or Hugging Face Hub registry.
  3. **Inference (RAG)**: Update `rag_inference.py` to stream/download the required LoRA adapter from S3 dynamically into the GPU memory rather than reading from `backend/data/adapters/`.
