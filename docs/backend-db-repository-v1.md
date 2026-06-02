# Backend DB Repository v1

## Backend Selection

`EASYADS_DB_BACKEND` controls the GenerationJob storage backend.

- `EASYADS_DB_BACKEND=memory`: use the current in-memory store. This remains the default.
- `EASYADS_DB_BACKEND=postgres`: use the Postgres repository layer.
- Empty or unknown values fall back to `memory`.

When `postgres` is selected, `DATABASE_URL` is required. The app does not open a DB connection at import time; connections are created lazily through `get_db_connection()`.

Postgres repository path requires `psycopg` at runtime. This milestone keeps `psycopg` as an optional lazy dependency for CI safety and does not change `pyproject.toml` or `uv.lock`. Actual Supabase smoke requires installing `psycopg` or adding it to project dependencies in the deployment PR.

R2 upload path also remains lazy and optional. `boto3` is not added to project dependencies in this milestone; actual R2 smoke or deployment needs a runtime `boto3` installation.

## Environment

```env
EASYADS_DB_BACKEND=memory
DATABASE_URL=
EASYADS_DEMO_WORKSPACE_ID=
EASYADS_DEMO_USER_ID=
```

## Repository Layer

The repository layer lives under `orchestrator/app/db/repositories/`.

- `workspaces.py`: demo workspace lookup/create fallback.
- `chat_threads.py`: create/get/update chat thread rows.
- `chat_messages.py`: append/list chat messages with thread-local sequence numbers.
- `generation_jobs.py`: create/get/update GenerationJob rows by `public_job_id`.
- `generation_outputs.py`: create/list outputs and mark one output final per thread.
- `assets.py`: store asset metadata only using R2-ready fields such as `kind`, `storage_provider`, `mime_type`, `size_bytes`, checksum, public URL, and soft delete metadata.
- `usage_events.py`: record/list usage events with optional thread/job/provider/model/plan/cost fields.

Repositories return DB row dictionaries. They do not construct API DTOs. Service modules own DTO conversion and business logic.

Repositories pass JSONB values through `jsonb_param(...)` and SQL `::jsonb` casts instead of relying on implicit Python dict adaptation.

## GenerationJob DB Backend

`orchestrator/app/generation_jobs/service.py` now branches by backend:

- memory backend keeps the existing module-level store and response shape.
- postgres backend creates or resolves a demo workspace, creates a chat thread, inserts a generation job row, records lifecycle events, and converts rows back into `GenerationJobResponse`.

The public API response shape is preserved:

- `job_id`
- `thread_id`
- `status`
- `progress`
- `selected_reference_template_id`
- `output_path`
- `result_payload`
- `error`
- `metadata`
- `created_at`
- `updated_at`

## Demo Fallback

If request context does not include workspace information, the postgres backend uses:

1. `EASYADS_DEMO_WORKSPACE_ID` when configured.
2. A created demo workspace when no demo id is configured.
3. `EASYADS_DEMO_USER_ID` as `created_by`/`requested_by` when configured.

## GenerationJob Persistence

The postgres backend supports create/get/running/done/failed lifecycle operations:

- create records a `queued` event and sets the thread active job.
- running records a `running` event and updates progress/current stage.
- done records a `done` event, optionally uploads the final artifact to R2, creates either an R2 asset row or a local-dev placeholder, creates a generation output row, marks it final, updates the thread final output, and records `output_created`.
- failed records a `failed` event and marks the thread failed.

When R2 is enabled, upload lifecycle events `r2_upload_started`, `r2_upload_completed`, and `r2_upload_failed` may be recorded. Local artifact assets still use `storage_provider=local_dev`, `bucket=local-dev`, and `metadata.public_serving=false` when fallback is used.

## Not Included

- Remote Supabase migration execution.
- Modal execution.
- Supabase Auth/RLS enforcement.
- Frontend changes.
- Evaluation pipeline implementation.
- Actual GPT-image-2, SD3.5, FLUX, LLM, VLM, or OCR calls.
