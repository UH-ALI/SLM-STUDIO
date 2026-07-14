# Future Features & Backlog (Things To Do)

## 1. Downloadable Form / Document Attachment Links in RAG Chat Responses
* **Status**: Planned (Future Release)
* **Feature Description**:
  When a user asks for a specific form or document (e.g., *"I want the admission form"*), the assistant should not only answer from the RAG knowledge base, but also provide a direct, clickable file download link or attachment card (`📎 Download admission_form.pdf`) in the chat UI.
* **Technical Roadmap**:
  1. **Backend (`rag_inference.py`)**: `retrieve_context()` already returns document citations (`citations = [{"source": "admission_form.pdf", ...}]`).
  2. **File API**: Ensure `/api/v1/projects/{project_id}/files/{filename}` serves the original uploaded PDF/DOCX file securely.
  3. **Frontend / Widget**: Inspect response citation metadata and render a downloadable file attachment card directly below the assistant's message bubble.

