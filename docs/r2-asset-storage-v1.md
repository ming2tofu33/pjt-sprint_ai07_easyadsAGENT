# R2 Asset Storage v1

## Purpose

This milestone adds an optional Cloudflare R2 upload path for completed generation artifacts. The default backend remains `local_dev`, but when R2 is enabled the backend can upload `final_0.png`, persist R2 asset metadata, and return browser-usable URLs in `result_payload`.

## Environment

```env
EASYADS_ASSET_STORAGE_BACKEND=local_dev
EASYADS_ENABLE_R2_UPLOAD=false
EASYADS_R2_UPLOAD_REQUIRED=false

EASYADS_R2_BUCKET=
EASYADS_R2_ENDPOINT_URL=
EASYADS_R2_ACCESS_KEY_ID=
EASYADS_R2_SECRET_ACCESS_KEY=
EASYADS_R2_REGION=auto

EASYADS_R2_URL_MODE=signed
EASYADS_R2_SIGNED_URL_TTL_SECONDS=3600
EASYADS_R2_PUBLIC_BASE_URL=
```

## Backend Modes

- `local_dev`: create internal asset placeholders only.
- `r2` or `EASYADS_ENABLE_R2_UPLOAD=true`: attempt R2 upload during `mark_generation_job_done()`.

If `EASYADS_R2_UPLOAD_REQUIRED=false`, R2 failures fall back to the existing local-dev placeholder policy and the job remains `done`.

If `EASYADS_R2_UPLOAD_REQUIRED=true`, R2 failures transition the job to `failed` with `error_code=r2_upload_failed`.

## Object Key Convention

Generated final image uploads use:

```text
workspaces/{workspace_id}/threads/{thread_id}/jobs/{job_id}/{filename}
```

Object key parts are sanitized to block traversal and normalize unsafe characters.

## URL Modes

- `signed`: `final_image_url` and `download_url` use presigned `get_object` URLs with TTL from `EASYADS_R2_SIGNED_URL_TTL_SECONDS`.
- `public`: URLs are built from `EASYADS_R2_PUBLIC_BASE_URL` plus the object key.

Signed URL refresh is not implemented in this milestone.

## GenerationJob Integration

`mark_generation_job_done()` now:

1. resolves the final local artifact path,
2. optionally uploads that file to R2,
3. creates or updates an `assets` row,
4. creates a `generation_outputs` row,
5. records upload lifecycle events.

On successful R2 upload, `result_payload` is extended with:

- `final_asset_id`
- `storage_provider`
- `bucket`
- `object_key`
- `url_mode`
- `final_image_url`
- `download_url`
- `signed_url_expires_at`
- `assets.final`

Local-dev fallback rows also populate `final_asset_id`, `storage_provider`, `bucket`, `object_key`, and `assets.final`, while keeping `final_image_url` and `download_url` as `null`.

All `result_payload` values returned through API responses are sanitized to remove local absolute paths, unsafe URL schemes, and secret-like metadata keys.

## Assets Policy

R2 asset rows store:

- `kind=result`
- `storage_provider=r2`
- `bucket`
- `object_key`
- `mime_type`
- `size_bytes`
- `width`
- `height`
- `public_url` when public mode is used
- `metadata.public_serving=true`
- `metadata.url_mode=signed|public`

Local-dev fallback rows continue to use:

- `storage_provider=local_dev`
- `bucket=local-dev`
- `metadata.public_serving=false`

## Events

Possible GenerationJob events now include:

- `queued`
- `running`
- `done`
- `failed`
- `output_created`
- `r2_upload_started`
- `r2_upload_completed`
- `r2_upload_failed`

For `EASYADS_R2_UPLOAD_REQUIRED=true`, a failed upload records `r2_upload_started -> r2_upload_failed -> failed` and does not emit `done`.

## Limitations

- No real R2 upload happens in tests.
- `boto3` remains an optional lazy dependency in this milestone.
- Signed URL refresh API is not implemented.
- Thumbnail/background/copy preview uploads are out of scope for v1.
- Archive integration is not implemented here.

## Manual Smoke Preparation

Actual R2 smoke is intentionally not executed in this milestone.

Before running actual smoke, prepare:

```env
EASYADS_ASSET_STORAGE_BACKEND=r2
EASYADS_ENABLE_R2_UPLOAD=true
EASYADS_R2_UPLOAD_REQUIRED=false
EASYADS_R2_BUCKET=...
EASYADS_R2_ENDPOINT_URL=...
EASYADS_R2_ACCESS_KEY_ID=...
EASYADS_R2_SECRET_ACCESS_KEY=...
EASYADS_R2_URL_MODE=signed
EASYADS_R2_SIGNED_URL_TTL_SECONDS=3600
```

Recommended manual verification:

1. Run a completed GenerationJob with a local `final_0.png`.
2. Confirm `assets.storage_provider=r2`.
3. Confirm `result_payload.final_image_url` is present.
4. Open the URL in a browser/mobile environment.
5. Confirm no R2 credentials are present in logs, result payload, or events.
6. Confirm `data/logs/`, `data/outputs/`, `.env`, and `docs/api_key.env` are not staged.

## Commit Policy

Commit this document and source/test changes only.

Do not commit:

- `.env`
- `docs/api_key.env`
- `data/`
- `data/logs/`
- `data/outputs/`
- `*.png`
- `*.jpg`
- `*.jpeg`
- `*.webp`
