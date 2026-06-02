# GenerationJob Persistence v1

## Purpose

This milestone moves GenerationJob lifecycle operations toward DB persistence while keeping the in-memory backend as the default. It wires the Postgres repository foundation into create/get/status transitions and records output/asset placeholders for completed jobs.

## Backend Split

- `EASYADS_DB_BACKEND=memory`: existing in-memory store remains active.
- `EASYADS_DB_BACKEND=postgres`: GenerationJob service uses repositories under `orchestrator/app/db/repositories/`.

The API response shape remains unchanged. Public API ids continue to use `job_...` and `thread_...` values backed by `public_job_id` and `public_thread_id`.

## Create/Get Flow

Postgres `create_generation_job()` ensures a demo workspace, creates a chat thread, creates a queued generation job, updates the thread active job, and records a `queued` event.

`get_generation_job(job_id)` selects by `generation_jobs.public_job_id` and converts the row back into `GenerationJobResponse`.

## Status Transitions

- `mark_generation_job_running()` updates status/progress/stage, sets `started_at`, records a `running` event, and keeps the thread generating.
- `mark_generation_job_done()` updates status/result payload/output path, sets `finished_at`, records `done`, creates a local-dev asset placeholder, creates a generation output, marks it final, updates the thread final output, and records `output_created`.
- `mark_generation_job_failed()` stores a structured error, sets `finished_at`, records `failed`, and marks the thread failed.

## Output And Asset Policy

R2 upload is optional in this milestone. Completed local artifacts still fall back to asset placeholders when R2 is disabled or when upload fails with `EASYADS_R2_UPLOAD_REQUIRED=false`:

- `kind=result`
- `storage_provider=local_dev`
- `bucket=local-dev`
- `object_key=data/outputs/...`
- `metadata.public_serving=false`
- `metadata.serving_status=not_public`

This row is internal metadata only. It does not imply the artifact is browser-displayable.

When R2 upload succeeds, the backend stores an R2 asset row, creates the generation output against that asset, and fills `result_payload.final_image_url` / `result_payload.download_url` according to the configured URL mode.

Signed URLs may expire. Refresh APIs are a later milestone.

## Not Included

- static serving or signed URLs
- Modal execution
- Archive API/UI
- FE implementation
- actual GPT-image-2, SD3.5, FLUX, LLM, VLM, or OCR calls
- remote Supabase migration execution
