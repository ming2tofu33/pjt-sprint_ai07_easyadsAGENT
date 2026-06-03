# ResultArtifactPayload Storage Contract v1

## Purpose

This document defines the storage-backed extension of `ResultArtifactPayload`. The schema version remains `result_artifact_v1`; this is a backward-compatible expansion, not a breaking contract change.

## Top-Level Fields

Existing frontend-safe URL fields remain top-level:

- `final_image_url`
- `download_url`

Storage-backed fields are also top-level for DB, Archive, and debugging workflows:

- `final_asset_id`
- `background_asset_id`
- `thumbnail_asset_id`
- `copy_visual_preview_asset_id`
- `storage_provider`
- `bucket`
- `object_key`
- `url_mode`
- `signed_url_expires_at`

Repo-relative trace paths such as `final_image_path`, `download_path`, and `output_path` may still exist for development tracing. They are not browser URLs.

## Nested Assets Map

`assets` is a map keyed by logical artifact role:

- `final`
- `background`
- `thumbnail`
- `copy_visual_preview`

Each entry follows `ResultArtifactAssetRef`.

## R2 Success Example

```json
{
  "schema_version": "result_artifact_v1",
  "final_image_path": "data/outputs/job_db/final_0.png",
  "final_asset_id": "asset_uuid",
  "storage_provider": "r2",
  "bucket": "easyads-dev",
  "object_key": "workspaces/workspace_uuid/threads/thread_db/jobs/job_db/final_0.png",
  "url_mode": "signed",
  "final_image_url": "https://signed.example/final_0.png",
  "download_url": "https://signed.example/final_0.png",
  "signed_url_expires_at": "2026-06-03T00:00:00+00:00",
  "assets": {
    "final": {
      "asset_id": "asset_uuid",
      "kind": "result",
      "storage_provider": "r2",
      "bucket": "easyads-dev",
      "object_key": "workspaces/workspace_uuid/threads/thread_db/jobs/job_db/final_0.png",
      "final_image_url": "https://signed.example/final_0.png",
      "download_url": "https://signed.example/final_0.png",
      "url_mode": "signed",
      "public_serving": true
    }
  }
}
```

## Local-Dev Fallback Example

```json
{
  "schema_version": "result_artifact_v1",
  "final_image_path": "data/outputs/job_db/final_0.png",
  "final_asset_id": "asset_local_uuid",
  "storage_provider": "local_dev",
  "bucket": "local-dev",
  "object_key": "data/outputs/job_db/final_0.png",
  "url_mode": null,
  "final_image_url": null,
  "download_url": null,
  "assets": {
    "final": {
      "asset_id": "asset_local_uuid",
      "kind": "result",
      "storage_provider": "local_dev",
      "bucket": "local-dev",
      "object_key": "data/outputs/job_db/final_0.png",
      "final_image_url": null,
      "download_url": null,
      "public_serving": false
    }
  }
}
```

## Sanitizer Policy

API responses pass through artifact sanitization before returning `result_payload`.

Allowed development trace paths:

- `data/outputs/...`
- `data/logs/...`

Blocked paths and URLs:

- local absolute paths such as `C:/...`, `/home/...`, `/mnt/...`, `/tmp/...`, `/var/...`
- `file://...`
- `data:image/...`
- `javascript:...`

Only `http://` and `https://` are accepted as browser-safe URLs.

Secret-like keys are recursively removed from payloads and nested metadata:

- `api_key`
- `openai_api_key`
- `hf_token`
- `huggingface_token`
- `token`
- `authorization`
- `password`
- `secret`
- `service_role_key`
- `access_key`
- `secret_access_key`
- `r2_secret`

## FE Binding Policy

FE may use only `final_image_url`, `download_url`, or nested asset public URL fields for preview/download. FE must not use `final_image_path`, `download_path`, `output_path`, or local-dev `object_key` as `img src` or anchor `href`.

When URL fields are `null`, the result can be complete but not browser-displayable yet.

## Follow-Ups

- signed URL refresh API
- thumbnail/background/copy visual preview upload expansion
- Archive integration with `assets.final`
- Local Postgres/Supabase dev DB smoke
