# Modal GPU Execution Backend v1

## 1. Purpose

This milestone adds a guarded Modal execution path for GPU-heavy local T2I engines. It is a backend execution bridge only. It does not run actual Modal jobs, upload to R2, call OpenAI, load SD3.5/FLUX models, or change frontend behavior in CI/default tests.

Follow-up deployment preparation adds `modal_apps/easyads_t2i_worker.py`, with a lightweight deployed Modal function for smoke testing the `Railway -> Modal -> R2` path and a separate FLUX.1-schnell function for guarded real GPU smoke tests.

## 2. Environment

```env
EASYADS_T2I_EXECUTION_BACKEND=local
EASYADS_ENABLE_MODAL_EXECUTION=false
EASYADS_MODAL_SUBMIT_REQUIRED=false
EASYADS_MODAL_POLL_ON_GET=false
EASYADS_MODAL_APP_NAME=easyads-t2i
EASYADS_MODAL_FUNCTION_NAME=generate_image
EASYADS_MODAL_ENVIRONMENT=
EASYADS_MODAL_DEFAULT_GPU=L40S
EASYADS_MODAL_RESULT_TRANSPORT=inline_base64
EASYADS_MODAL_POLL_TIMEOUT_SECONDS=0
EASYADS_MODAL_POLL_INTERVAL_SECONDS=1
EASYADS_MODAL_MAX_POLL_ATTEMPTS=1
MODAL_TOKEN_ID=
MODAL_TOKEN_SECRET=
```

Default behavior is `local` and disabled. Unknown backend values fall back to `local`.

## 3. Eligible Run Modes

Modal routing is allowed only for local GPU lanes:

```text
sd35_local
sd35_local_smoke
flux_local
flux_local_smoke
flux_schnell_real
flux
flux_smoke
```

GPT-image-2 remains outside Modal because it is an external OpenAI API lane.

## 4. Create Flow

`POST /api/v1/generation-jobs` still creates a GenerationJob first. When `EASYADS_T2I_EXECUTION_BACKEND=modal` and the run mode is eligible:

1. The service requires Postgres persistence.
2. If Modal is disabled, the job is marked failed with `modal_execution_not_enabled`.
3. If Modal is enabled, the service submits a `ModalT2IRequest`.
4. The job stores `modal_call_id` in the DB row, while API metadata exposes only `modal_call_id_present=true`.
5. Events record `modal_submit_started` and `modal_submitted`, or `modal_submit_failed`.

The router does not import Modal SDKs or repositories directly.

## 5. Poll Flow

`GET /api/v1/generation-jobs/{job_id}` polls Modal only when:

```text
EASYADS_DB_BACKEND=postgres
EASYADS_MODAL_POLL_ON_GET=true
job.status is queued or running
generation_jobs.modal_call_id is present
```

Pending/running Modal results keep the job running. Failed/canceled results mark the job failed. Succeeded results write the returned image to:

```text
data/outputs/{job_id}/final_0.png
```

Then the service calls `mark_generation_job_done()`, which preserves the existing ResultArtifactPayload/R2/local-dev storage contract.

## 6. Result Payload Policy

Modal result image bytes are transient. The DB and API payload must not store:

```text
image_b64
image_bytes
raw binary data
Modal token values
```

The final API payload remains `schema_version=result_artifact_v1` and uses storage-backed fields from `docs/result-artifact-payload-storage-contract-v1.md`.

## 7. Usage Events

On successful Modal completion, the service may record a `usage_events` row:

```text
event_type=modal_gpu_seconds
provider=modal
unit=seconds
metadata.modal_call_id_present=true
```

GPU type, duration, and model name may be stored when returned by the fake/actual adapter. Token values and image data must not be stored.

## 8. Testing Policy

Unit tests use fake Modal clients and monkeypatched repositories only. They do not:

```text
call Modal
call R2
load SD3.5 or FLUX
call OpenAI
write data/logs artifacts
commit data/outputs artifacts
```

## 9. Current Limitations

```text
Actual SD3.5 Large deployment is not included. A mock Modal worker is available for connectivity smoke tests, and `generate_flux_schnell_image` is available for FLUX.1-schnell smoke tests when `easyads-hf-token` and a GPU deployment are configured.
Callback/webhook handling is not implemented.
Long polling and background workers are not implemented.
Signed URL refresh remains a separate storage milestone.
```

## 10. Follow-up Work

```text
1. Modal fake integration smoke through FastAPI.
2. Actual Modal dev smoke with prepared credentials.
3. R2 actual upload smoke after Modal output.
4. Background worker or callback-based polling.
5. Usage/cost accounting refinement.
```
