# SLM Studio — Implementation Tasks (spec only, do not deviate)

Three tasks, ordered by demo priority. Task 1 is the important one.
Backend code is volume-mounted into the containers (`./backend:/app`), so backend
changes need only `docker compose restart api worker` — NO image rebuild.
Frontend is baked into its image, so any frontend change needs
`docker compose build frontend && docker compose up -d frontend`.

---

## Task 1 — Fix cross-project adapter bleed (HIGH priority, backend only, no rebuild)

### Symptom
With two trained projects sharing the same base model (e.g. "University Assistant"
and "Islamiat Teacher", both on Qwen3-1.7B), querying A → then B → then A again
makes A answer with B's fine-tuned knowledge (e.g. the university bot explains zakat).

### Root cause (verified in code)
`backend/app/ai/rag_inference.py`, function `get_or_load_model` (~line 148).

`ACTIVE_ADAPTERS` is a dict of `{job_id: base_slug}` recording which adapters have
been MOUNTED, but the guard uses it as if it recorded which adapter is ACTIVE:

```python
if ACTIVE_ADAPTERS.get(job_id) != base_slug:   # ~line 200
    ... set_adapter / load_adapter ...
    ACTIVE_ADAPTERS[job_id] = base_slug
```

A PeftModel has exactly ONE active adapter at a time, but this dict accumulates an
entry per job and never unsets anything. Deterministic failure sequence:

1. Request for job A → adapter A mounted + activated, `ACTIVE_ADAPTERS[A] = base`.
2. Request for job B → adapter B mounted + activated (B is now the active adapter),
   `ACTIVE_ADAPTERS[B] = base`.
3. Request for job A again → `ACTIVE_ADAPTERS.get(A) == base` → the entire swap
   block is SKIPPED → generation runs with **adapter B still active**. Bleed.

### Fix (minimal, surgical)
In `backend/app/ai/rag_inference.py`:

1. Add one module-level dict next to the existing caches (~line 70):
   ```python
   # base_slug -> job_id whose adapter is currently ACTIVE on that base model.
   # ACTIVE_ADAPTERS records what is MOUNTED; this records what is SELECTED.
   ACTIVE_ADAPTER_ON_BASE = {}
   ```

2. In `get_or_load_model`, change the Tier-2 guard (~line 200) from
   ```python
   if ACTIVE_ADAPTERS.get(job_id) != base_slug:
   ```
   to
   ```python
   if ACTIVE_ADAPTER_ON_BASE.get(base_slug) != job_id:
   ```
   Keep the body of the block exactly as is (set_adapter → except → load_adapter →
   fallback chain), and at the end of the block, where it currently does
   `ACTIVE_ADAPTERS[job_id] = base_slug`, ALSO set:
   ```python
   ACTIVE_ADAPTER_ON_BASE[base_slug] = job_id
   ```

3. Fresh-load path: in the Tier-1 branch that loads the base model for the first
   time via `FastLanguageModel.from_pretrained(model_name=adapter_path, ...)` —
   that load bakes THIS job's adapter in as the active one, so immediately after
   `ACTIVE_BASE_MODELS[base_slug] = (model, tokenizer)` add:
   ```python
   ACTIVE_ADAPTER_ON_BASE[base_slug] = job_id
   ```
   (Same for the two fallback `from_pretrained` calls inside the Tier-2 except
   branches — each of them makes `job_id` the active adapter.)

4. In `unload_model` (~line 244): when a job is evicted, clear its active mark:
   ```python
   if ACTIVE_ADAPTER_ON_BASE.get(base_slug) == job_id:
       ACTIVE_ADAPTER_ON_BASE.pop(base_slug, None)
   ```

### Explicitly OUT of scope for this task
Do NOT touch `_inference_lock`, the generation threads, or `generate_rag_response_stream`.
(There is a second, much rarer race where two *simultaneous* streams swap adapters
between `get_or_load_model()` and `model.generate()`; fixing it means re-activating
the adapter inside the `_inference_lock` block. Leave it — sequential correctness is
what the demo needs, and the demo drives one chat at a time.)

### Acceptance test
1. `docker compose restart api`
2. Playground project A: ask a domain question → correct domain answer.
3. Playground project B: ask a domain question → correct domain answer.
4. Back to project A, ask B's domain question → A must now refuse / answer from
   A's documents only. Repeat A→B→A twice.
5. `docker compose logs api | grep -i adapter` should show a swap line on every
   project change, not just the first.

### Deploy
Backend only → `docker compose restart api`. No rebuild, no migration.

---

## Task 2 — Remove the fake document-remove (✕) button in the Playground (LOW effort, frontend, needs rebuild)

### Symptom / rationale
`frontend/components/templates/PlaygroundLayout.tsx` renders a ✕ button per document
which calls `removeDocument(name)` — that function only filters the local React state.
Nothing is deleted on the backend; the chunks stay in ChromaDB, the dataset stays
linked, and the document reappears on refresh. A fake control is worse than none.

### Fix
In `PlaygroundLayout.tsx`:
1. Delete the `removeDocument` function.
2. Delete the `<button onClick={() => removeDocument(...)}>` (with the X icon) from
   the documents list row. Keep the row itself and the ingestion-status badges
   ("N chunks" / "Not readable") exactly as they are.
3. Remove the now-unused `X` icon import ONLY if it is not used elsewhere in the
   file (it IS used by the panel-close buttons — check before removing; almost
   certainly keep the import).

### Acceptance test
Documents panel lists documents with status badges and no per-document ✕.
Panel close buttons (top-right of each panel) still work.

### Deploy
Frontend → `docker compose build frontend && docker compose up -d frontend`.

---

## Task 3 — True "Cancel training" via Celery revoke (DEFER unless time allows; backend + migration + frontend)

### Current behaviour (intentional, do not "fix" halfway)
The button was deliberately relabelled "Reset status & unlock": it resets DB status
and clears the `gpu:state` Redis key but does NOT stop the running Celery task —
there is no stored Celery task id to revoke (an earlier version passed the
TrainingJob UUID to `revoke()`, which is not a Celery task id; it never worked).
So the GPU keeps training; clicking "retry" re-attaches to real state. That matches
what was observed.

### Fix (only if implementing fully — all five steps or none)
1. **Migration** (`backend/alembic/versions/`, new revision, `down_revision = 'a1b2c3d4e5f6'`):
   ```python
   op.add_column('training_jobs', sa.Column('task_id', sa.String(), nullable=True))
   # downgrade: op.drop_column('training_jobs', 'task_id')
   ```
2. **Model** — `backend/app/models.py`, class `TrainingJob`:
   ```python
   task_id = Column(String, nullable=True)  # Celery task id, set at dispatch
   ```
3. **Store at dispatch** — `backend/app/routers/projects.py`, in `train_project`
   where `train_model_task.delay(...)` is called (~line 520):
   ```python
   result = train_model_task.delay(str(project.id), str(new_job.id))
   new_job.task_id = result.id
   db.commit()
   ```
4. **Revoke in the reset endpoint** — same file, `cancel_project`: before resetting
   statuses, if `latest_job and latest_job.task_id`:
   ```python
   from app.worker.celery_app import celery_app as _celery
   _celery.control.revoke(latest_job.task_id, terminate=True, signal="SIGTERM")
   ```
   Keep the existing status reset + `gpu:state` delete — SIGTERM kills the prefork
   child mid-CUDA and the existing cleanup is what makes that safe.
5. **Frontend label** — `frontend/components/templates/TrainingLayout.tsx`: restore
   the button text to "Cancel & Unlock" ONLY after 1–4 are deployed and verified.

### Deploy
`docker compose exec api alembic upgrade head` (CRITICAL — without it every
training-job read 500s on the missing column), then `docker compose restart api worker`.
Frontend label → rebuild frontend.

### Acceptance test
Start a throwaway training → click cancel → worker log shows the task terminated
within a few seconds, GPU util drops, project status FAILED, a new training can start.

### Recommendation
DEFER. The demo mitigation is procedural: do not cancel a training during the
presentation. The relabelled button is honest about what it does.
