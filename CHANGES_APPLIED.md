# Corrections applied on top of `fyp_SLM--AI-Improved`

This is your AI-Improved codebase with 5 files patched to restore functionality
that `CHANGES.md` flagged as accidentally rolled back, plus one real security
fix. Every other file is untouched — byte-for-byte identical to what you
uploaded. Only these 5 files changed:

- `backend/app/schemas.py`
- `backend/app/routers/deploy_public.py`
- `backend/app/static/widget.js`
- `frontend/stores/deployStore.ts`
- `frontend/components/organisms/DeployPanel.tsx`

Nothing else was touched — `main.py`, `rag_inference.py`, the upload
validators, the hyperparameter defaults, etc. were already correct in your
AI-Improved version and were left exactly as-is.

---

## 1. Restored: widget color customization (5 fields)

Your original build let you customize 6 widget colors (header/primary,
chat background, typing dots, bot bubble, user bubble, input area). The
AI-Improved pass had quietly trimmed this down to just `primaryColor`. I put
the other 5 back everywhere they need to exist for the feature to actually
work end-to-end:

- **`schemas.py`** — `WidgetConfig` (and `PublicWidgetConfigResponse`, the
  model the public `/config` endpoint returns to the browser) gained back
  `bodyColor`, `dotsColor`, `botMessageColor`, `userMessageColor`,
  `chatInputColor`, each validated as a 6-digit hex color.
- **`routers/deploy_public.py`** — the `/config` endpoint now returns all 6
  colors (previously only `primaryColor`), otherwise the widget has no way
  to know what colors you picked.
- **`static/widget.js`** — restored `getContrastColor()` (auto-picks black
  or white text against whatever background color you choose, so text never
  goes invisible) and rewired the CSS template to use all 6 colors instead
  of hardcoded values. I kept the **citation rendering** and the **improved
  error handling** ("Connection interrupted" message on a dropped stream)
  that the AI-Improved pass added — those are good additions and had nothing
  to do with the color rollback, so they're preserved as-is.
- **`stores/deployStore.ts`** — `WidgetConfig` TS interface got the 5 fields
  back (marked optional, matching the backend defaults).
- **`components/organisms/DeployPanel.tsx`** — the entire "Widget
  Customization" card (title, greeting, 6 color pickers, position selector,
  "Save Appearance" button) was missing entirely from AI-Improved. It's back.

  One deliberate difference from the recovered version: the recovered code
  had 6 separate loading-state booleans (`isEnabling`, `isPausing`,
  `isRotating`, `isAddingOrigin`, `removingOrigin`, `isUpdatingConfig`).
  AI-Improved had consolidated these into one `actionLoading` boolean. That
  consolidation is a reasonable simplification (all it does is disable
  buttons while *any* deploy action is in flight — a bit less precise than
  per-button spinners, but simpler and not a regression), so I kept it and
  wired the new "Save Appearance" button into the same shared state rather
  than reintroducing 6 booleans.

## 2. Fixed: origin validation had become spoofable

`CHANGES.md` flagged this as "worth double-checking" and it's a real
security issue, so I fixed it:

- **`schemas.py`** — `DeployConfigUpdate.validate_origins` is back. When you
  add an allowed origin in the dashboard, it's now parsed as a URL and
  normalized to `scheme://netloc` (rejecting anything malformed).
- **`routers/deploy_public.py`** — `_check_origin` now does an **exact
  match** against `project.allowed_origins` again, instead of
  `origin.startswith(allowed)`. The `startswith` version meant an allowed
  origin of `https://example.com` would also match a request claiming to be
  from `https://example.com.evil.com` — anyone could spin up that subdomain
  and the widget would treat it as authorized. Exact matching after
  normalization closes that hole.

## 3. Fixed: a real bug in the streaming/usage-tracking path

This one wasn't just a stylistic revert — the AI-Improved version has an
actual bug:

```python
_track_usage(project.id, db)          # runs immediately
return StreamingResponse(event_stream(), ...)   # generator body runs later
```

`event_stream()` is a generator — calling it doesn't run any code inside it;
it only runs when something iterates it, which happens *after* this function
returns and FastAPI starts sending the response. So `_track_usage` was firing
before the model had generated a single token — a message got counted as
"usage" even if the stream immediately failed. I restored the original
pattern:

- Primitive values (`job_id`, `project_id`, `use_case`, `persona`,
  `temperature`) are pulled out of the ORM objects **before** the generator
  starts, since the request-scoped `db` session (and the ORM objects tied to
  it) may already be closed by the time the generator body actually runs.
- Usage is only recorded **after** the stream completes successfully
  (`success` flag), using a **fresh** DB session opened inside the generator
  — not the original request-scoped `db`, which isn't safe to touch from
  code that runs after the request handler has returned.
- If usage tracking itself fails, it fails silently rather than breaking the
  chat response — tracking is non-critical.

## 4. Left alone (already correct in AI-Improved)

Per `CHANGES.md`, these were legitimate improvements/fixes, not regressions,
so I didn't touch them: `main.py` cleanup, the `"who is this"` identity
regex in `rag_inference.py`, the notification-permission timing move in
`projects/new/page.tsx`, the `gradientAccumulationSteps` default in
`lib/constants.ts`, the dev-mode webpack polling removal in `next.config.js`,
and the new `upload_helpers.py` validators. I also didn't touch
`data_generator.py`, `finetune.py`, `worker/tasks.py`, or
`routers/inference.py` — per `CHANGES.md` there wasn't enough recovered data
to safely compare those, so the AI-Improved version is treated as
authoritative there, same as the report recommended.

## Suggested next step

Worth a quick manual read-through of `inference.py`, `finetune.py`,
`tasks.py`, and `data_generator.py` in your deployed repo — those are the
four files the recovery report couldn't meaningfully diff, so I can't tell
you whether anything changed there.

---

## 5. UI/UX Refinements (Latest Updates)

### A. Password Visibility Toggle
- **Files Modified**: `frontend/components/forms/LoginForm.tsx` & `frontend/components/forms/SignupForm.tsx`
- **What changed**: Added an interactive eye button (`Eye` / `EyeOff` from Lucide React) inside the password and confirm-password fields.
- **Why**: Allows users to inspect their typed password before submitting, reducing login and registration mistakes.

### B. Streamlined Document Upload Workflow
- **File Modified**: `frontend/components/forms/../organisms/WizardUpload.tsx`
- **What changed**: Removed the dual-tab switcher (`Upload Files` vs `Enter Text`) and raw text area input.
- **Why**: Encourages users to upload clean structured documents (`.txt`, `.pdf`, etc.) via drag-and-drop instead of typing unstructured raw text snippets.

### C. Context-Aware Citations Display
- **File Modified**: `backend/app/static/widget.js`
- **What changed**: Removed document citation rendering from the embeddable chat widget script while preserving full citation rendering inside the SLM Studio Playground.
- **Why**: End-users visiting embedded websites receive clean, conversational responses without technical file references (`[doc.pdf]`), while developers testing in the Playground retain full RAG traceability.
