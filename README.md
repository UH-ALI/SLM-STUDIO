# SLM Studio

No-code fine-tuning platform for small language models on private business data.
Upload documents → configure a persona → fine-tune (QLoRA/Unsloth) → chat with citations.

```
SLM-Studio/
├── docker-compose.yml      ← orchestrates all 5 services
├── .env.example            ← copy to .env and fill in real values
├── backend/                ← FastAPI + Celery + Postgres + Redis
└── frontend/               ← Next.js 14 (App Router)
```

## Quick start

```bash
cp .env.example .env
# edit .env: set POSTGRES_PASSWORD, SECRET_KEY, GROQ_API_KEY, HF_TOKEN

docker compose up -d --build
```

| Service  | URL                          |
|----------|-------------------------------|
| Frontend | http://localhost:3000         |
| API      | http://localhost:8000         |
| API docs | http://localhost:8000/docs    |

Requires an NVIDIA GPU + `nvidia-container-toolkit` on the host (training and
inference both need CUDA). To run API-only on CPU for UI/contract testing, remove
the `deploy:` GPU blocks from `api` and `worker` in `docker-compose.yml` — training
jobs will fail, but auth/projects/uploads/listing all work without a GPU.

## What this delivery contains

This started from a backend that had already gone through a "Project Refactor"
(an earlier session added `Project`/`TrainingJob` versioning, SSE streaming,
citations, VRAM eviction) and a frontend wizard that predated that refactor and
still called the old single-step `/jobs` contract. The production-readiness PDF
that was floating around described an even older state of the backend — most of
its Critical/High findings (UUID typing, path traversal, persona sync, SSE,
citations, VRAM LRU, log streaming) were **already fixed** before this pass
started. What's below is what was actually still broken, verified by reading
and running the real code rather than trusting any prior document.

### Backend fixes
- **Hand-written Alembic migration** (`7a3f9c1e2b44`) for the Project Refactor —
  `models.py` had `Project`, `project_datasets`, `TrainingJob.project_id/version`,
  and the `s3_path → adapter_path` rename with **no corresponding migration**.
  The app only survived on a fresh DB via `create_all()`; any already-migrated
  database would have broken on the missing columns. Validated by generating the
  full upgrade/downgrade SQL with `alembic ... --sql` against the real revision
  chain (no live Postgres needed for this check).
- Fixed `app/routers/__init__.py`, which imported a `jobs` module that no longer
  exists (renamed to `projects` during the refactor) — this would crash on
  `import app.routers` as a package.
- Removed dead `hasattr()` branches in `create_project()` that could never fire,
  since `ProjectCreate` never declared the fields they were checking for.
- Consolidated duplicated file-upload validation logic (`routers/datasets.py` and
  `routers/projects.py` each had their own copy of size/format checks) into
  `app/services/upload_helpers.py`, used by both.
- Added missing `__init__.py` to `app/services/`.
- `.gitignore`: added `data/` and `unsloth_compiled_cache/` (previously only in
  `.dockerignore` — would have bloated the git repo with adapters/PDFs/CUDA cache).
- `docker-compose.yml`: Postgres credentials moved to `.env` (were hardcoded),
  added an API healthcheck (`db`/`redis` had one, `api` didn't), pinned image
  tags, added the `frontend` service.

### Frontend fixes
- **`lib/api.ts`**: default `baseURL` pointed at `localhost:3000` (itself) instead
  of the backend on `:8000`.
- **Rebuilt the wizard submission flow.** The old code sent one flat payload to
  `POST /jobs` including a hardcoded `datasetId: 'ds-001'` placeholder — files
  selected in the upload step were *never actually sent anywhere*. The backend's
  real flow is three calls: `POST /projects` → `POST /projects/{id}/datasets`
  (multipart) → `POST /projects/{id}/train`. Rewired `projectStore.ts` with
  separate `createProject`/`uploadDatasets`/`startTraining` actions and rewrote
  `app/projects/new/page.tsx` to call them in sequence, including converting
  pasted text (the upload step also accepts raw text) into a `.txt` file before
  upload, since the backend only has a file-upload endpoint.
- **Rewrote `useChatStream.ts`.** It called a relative `/api/v1/inference/chat/stream`
  path (resolves against the Next dev server, not the API) with only
  `{ message }` in the body — the *legacy* endpoint it hit requires `job_id` and
  `dataset_id` and would 422. Switched to the project-scoped
  `POST /inference/projects/{id}/chat/stream`, which needs neither. Also fixed an
  in-place state mutation (`lastMsg.content += token`) to build new objects
  immutably, and added real citation parsing from the backend's final SSE event
  (`{citations, done}`) — citations were previously 100% hardcoded mock data in
  `PlaygroundLayout.tsx`, never connected to anything the backend returned.
- **Security**: Next.js was pinned to `14.2.15`, which has a [critical RSC
  RCE chain](https://nextjs.org/blog) (CVE-2025-55182/55183/55184/67779) — this
  app uses the App Router, which is the affected surface. Bumped to `14.2.35`.
  Ran `npm audit fix` for the rest; two remaining advisories only resolve by
  forcing a Next 16 major bump, which would need its own compatibility pass and
  was left out of scope rather than force-upgraded silently.
- **TypeScript**: the project didn't type-check cleanly before this pass. Fixed:
  a `react`/`@types/react` major-version mismatch (runtime on 18, types pinned to
  19) that broke `@react-three/fiber`'s JSX intrinsic-element augmentation for
  the hero background; `Hyperparameters.temperature` missing from a `Required<>`
  default object; a missing `size` prop on the shared `Button` component (added
  properly rather than dropped at call sites); a strict-mode `useRef` call
  missing its initial value; an `Icon.tsx` type narrower than `lucide-react`'s
  actual `LucideIcon` type; and the `Project.status`/`TrainingStatus` union
  missing `'training'` — which was a real bug, not just a type gap: the status
  page's mapping `useEffect` silently collapsed `'training'` to `'pending'`,
  so a project mid-fine-tuning showed the empty "waiting to start" panel instead
  of the live progress UI. Fixed the mapping plus the polling hook (which would
  have stopped polling at exactly that point) and the two display components
  that branched on `'processing'` only.
- Cleaned up genuinely dead code (unused imports flagged by `tsc`) and, where the
  unused import implied unfinished work rather than leftover cruft, finished it
  instead of just deleting the import — a file-extension badge on uploaded files,
  a retry action on failed project cards, and actually surfacing the validation
  error state in the project-setup step (declared and read, but never set).

`npx tsc --noEmit` passes with zero errors. The full register → login → create
project → upload dataset → start training → poll status flow was run live
against the real FastAPI app (in-process `TestClient`, SQLite standing in for
Postgres) and passes end-to-end.

## Teammate backend reconciliation + deployment feature completion

A teammate independently extended the backend with real, substantial work: a
"Project Refactor" (Project/TrainingJob versioning), and a complete deployment
feature (public chat widget, deploy keys, usage tracking, rate limiting). That
work was merged in — their version won wherever they'd genuinely solved
something I hadn't, mine won where I had a fix they didn't, and anywhere both
touched the same code the two were reconciled rather than one side picked
blindly. Every claim below was verified by reading the actual diff and running
it live, not by trusting either side's comments.

**Adopted wholesale from the teammate (verified byte-identical, all real
fixes):** `rag_inference.py` (thread-safety lock on the model LRU cache, a
generation-thread exception that would otherwise hang requests forever, an
empty-results crash, weak context truncation, the cosine-distance fix),
`finetune.py` (training/inference persona mismatch, a tiered model lineup),
`data_generator.py` (stricter anti-hallucination overlap check), `rag_ingestion.py`,
`main.py`, `models.py`, `config.py`, `auth.py`, `inference.py`, `users.py`,
plus the entire new deployment feature (`deploy_admin.py`, `deploy_public.py`,
`rate_limit.py`, `widget.js`).

**Reconciled rather than picked:** `datasets.py`/`projects.py` — the teammate's
branch predated this session's upload-helper deduplication, so their copies had
reintroduced the duplicated validation code (one file even had a dead,
unreachable duplicate function from an incomplete edit). Their new logic
(all-or-nothing multi-file uploads, an ingestion-race-condition guard before
training can start, default model resolution at project creation) was merged
onto the deduplicated structure rather than replacing it wholesale.
`schemas.py` — restored two fixes that were lost in the teammate's branch
(`summary_path`'s camelCase alias, a Pydantic warning suppression) while
keeping their new required, non-empty `persona` validation and removing a
status-masking validator that would have conflicted with this session's
earlier frontend fix (the frontend now understands a `'training'` status
natively; masking it at the API boundary would have broken that again).

**Bugs found and fixed during the merge itself, not present as-shipped in
either side:**
- The teammate's 3-migration chain created a foreign key referencing the
  `projects` table two migrations *before* a later migration created that
  table — would fail with `relation "projects" does not exist" on any
  genuinely fresh database. Verified by walking the revision chain
  programmatically and generating the full offline SQL via
  `alembic upgrade head --sql`; fixed by moving table creation earlier without
  changing revision IDs.
- The same migration dropped `model_artifacts.s3_path` with no data copy to
  the new `adapter_path` column — would have silently orphaned the file path
  on every existing trained model. Added a backfill `UPDATE` before the drop.
- A live-database `Inspector.has_table()` check in the deployment migration
  broke `alembic upgrade head --sql` (offline SQL generation/dry-run) — removed,
  since it was only guarding against `create_all()` already having made the
  table during local dev, not something a migration-managed database needs.

**Deployment feature: backend fully verified, frontend was previously 0%
wired (now done).** Backend tested live end-to-end: gate enforcement (can't
deploy before training completes), key generation, the public widget config
endpoint, key rotation invalidating the old key immediately, usage tracking,
revocation. `DeployPanel.tsx` was previously 100% hardcoded fake data
(`api.slmstudio.ai` placeholder URLs, a static `1.2K requests` stat, a
`v1.0.0` badge) — rewired to real data via a new `deployStore.ts`: live
enable/pause/rotate, the real embed snippet and cURL example, real per-day
usage stats, and an allowed-origins manager (the backend supported
per-deployment origin locking; nothing in the UI ever exposed it).

**Three real bugs found in `widget.js` during a careful line-by-line read,
fixed:**
- `document.currentScript` only reliably identifies the widget's own
  `<script>` tag during synchronous, blocking script execution — it silently
  returns `null` if the embed snippet is loaded with `async`/`defer`, or
  injected by a CMS/tag-manager/page-builder that defers script loading (very
  common for "paste this snippet anywhere" embeds, and something page owners
  often do deliberately so a chat widget doesn't block page load). Added a
  `querySelector` fallback that finds the tag regardless of load timing.
- If the SSE stream dropped mid-response after some tokens had already
  arrived, the error-handling code's `if (botText === "")` guard meant nothing
  updated the now-permanently-stuck partial message — the user saw the bot
  silently stop talking with no explanation. Now appends a
  "[Connection interrupted]" notice to whatever text did arrive.
- **A real stored-XSS vulnerability**: `config.title` and `config.greeting`
  (set by the project owner via `DeployPanel`, no server-side validation) were
  injected into the page via `innerHTML` *without* the `escapeHtml()` call that
  message text and citations correctly used elsewhere in the same file. A
  malicious or compromised project-owner account could have set `greeting` to
  a script payload that would execute in every visitor's browser on every page
  embedding that widget — the public nature of the widget makes site visitors,
  not the project owner, the actual blast radius. Fixed in the widget
  (`escapeHtml()` on both fields) and at the source (`WidgetConfig.primary_color`
  now validated as a strict 6-digit hex color server-side, since it was
  interpolated unescaped into a `<style>` block and an unvalidated value could
  break out of the CSS value context; `greeting`/`title` given reasonable
  length caps).

**Separately, while wiring `DeployPanel.tsx`:** found and fixed
`Project.modelName` in the frontend's TypeScript types — it never matched
what the backend actually serializes (`baseModelName`), a pre-existing,
silently-broken field that nothing live had been reading (confirmed via
project-wide search; its only reference was a comment documenting an
unrelated, already-fixed bug).

**What's still unverified — needs a real browser, which this environment
cannot provide:** the widget has never actually been rendered. Shadow DOM
construction, SSE stream parsing, and the embed snippet working when pasted
into a real page are all read carefully and reasoned through line by line, but
not executed. Paste the snippet `DeployPanel.tsx` generates into a blank HTML
file, open it in a browser, and confirm the chat bubble appears and a message
round-trips before trusting this in front of an evaluation panel.



- **Next.js build couldn't be verified in the sandbox this was built in** — it
  fetches `Inter`/`JetBrains Mono` from `fonts.googleapis.com` at build time via
  `next/font/google`, and that domain wasn't reachable from the verification
  environment. `tsc --noEmit` (full type-check, no network needed) passes clean,
  which is the strongest check available without that access — but run
  `npm run build` once after pulling this down to confirm the production build
  itself succeeds in your environment.
- **`DeployPanel.tsx`** still shows placeholder `api.slmstudio.ai` URLs — it was
  never wired to a real deployment backend (the `deployments` table exists in
  `models.py` with no endpoints, same gap the original PDF flagged as L2). Out of
  scope for this pass; flagging so it isn't mistaken for working.
- DevOps polish items that don't block functionality (log rotation, a graceful
  Celery shutdown handler that only fails the in-flight job rather than all
  `PROCESSING` jobs, a smoke-test script) weren't done in this pass — none of
  them affect the wizard→train→chat flow working correctly today.
