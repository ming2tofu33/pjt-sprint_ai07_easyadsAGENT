# ResultArtifactPayload Storage-backed Contract v1

## 1. Purpose

This document defines the storage-backed `ResultArtifactPayload` contract for EasyAds generated results.

Earlier versions of the result payload were primarily local-artifact oriented. They usually exposed repo-relative runtime paths such as `data/outputs/{job_id}/final_0.png` and left browser-usable URL fields as `null`.

The storage-backed contract keeps backward compatibility with the existing `result_artifact_v1` schema while adding asset metadata for DB/R2-backed generated outputs.

Main goals:

```text
1. Keep the existing FE-compatible top-level fields.
2. Add DB asset references for generated outputs.
3. Support Cloudflare R2 public/signed URLs.
4. Preserve local-dev fallback behavior.
5. Prevent local absolute paths, unsafe URLs, secrets, and image bytes from leaking through API responses.
```

---

## 2. Schema version policy

The schema version remains:

```json
{
  "schema_version": "result_artifact_v1"
}
```

This milestone is an additive contract expansion, not a breaking schema replacement.

FE/BFF clients may continue reading the existing top-level fields:

```text
final_image_url
download_url
final_image_path
download_path
prompt_summary
validation_summary
copy_summary
layout_summary
render_summary
```

New storage-backed fields are optional and must be handled defensively.

---

## 3. Top-level ResultArtifactPayload fields

Recommended top-level shape:

```json
{
  "schema_version": "result_artifact_v1",
  "output_dir": "data/outputs/job_x",
  "background_image_path": "data/outputs/job_x/background_0.png",
  "final_image_path": "data/outputs/job_x/final_0.png",
  "download_path": "data/outputs/job_x/final_0.png",
  "metadata_path": "data/outputs/job_x/metadata.json",
  "prompt_path": "data/outputs/job_x/prompt.json",
  "validation_path": "data/outputs/job_x/validation.json",
  "copy_path": "data/outputs/job_x/copy.json",
  "layout_path": "data/outputs/job_x/layout.json",
  "render_result_path": "data/outputs/job_x/render_result.json",
  "final_image_url": "https://signed-or-public-url.example/final_0.png",
  "download_url": "https://signed-or-public-url.example/final_0.png",
  "preview_image_url": null,
  "copy_visual_preview_url": null,
  "final_asset_id": "asset_uuid",
  "background_asset_id": null,
  "thumbnail_asset_id": null,
  "copy_visual_preview_asset_id": null,
  "storage_provider": "r2",
  "bucket": "easyads-dev",
  "object_key": "workspaces/workspace_uuid/threads/thread_x/jobs/job_x/final_0.png",
  "url_mode": "signed",
  "signed_url_expires_at": "2026-06-03T00:00:00+00:00",
  "assets": {
    "final": {
      "asset_id": "asset_uuid",
      "kind": "result",
      "storage_provider": "r2",
      "bucket": "easyads-dev",
      "object_key": "workspaces/workspace_uuid/threads/thread_x/jobs/job_x/final_0.png",
      "mime_type": "image/png",
      "size_bytes": 123456,
      "width": 1024,
      "height": 1024,
      "public_url": null,
      "final_image_url": "https://signed-or-public-url.example/final_0.png",
      "download_url": "https://signed-or-public-url.example/final_0.png",
      "preview_url": null,
      "url_mode": "signed",
      "signed_url_expires_at": "2026-06-03T00:00:00+00:00",
      "public_serving": true,
      "metadata": {
        "source": "generation_job_r2_upload"
      }
    }
  },
  "prompt_summary": {},
  "validation_summary": {},
  "copy_summary": {},
  "layout_summary": {},
  "render_summary": {}
}
```

All new storage-backed fields are optional.

---

## 4. Nested assets map

`assets` is a role-keyed map of output assets.

Supported role keys:

```text
final
background
thumbnail
copy_visual_preview
```

The current v1 implementation primarily fills:

```text
assets.final
```

Future milestones may fill:

```text
assets.background
assets.thumbnail
assets.copy_visual_preview
```

Recommended asset reference shape:

```json
{
  "asset_id": "asset_uuid",
  "kind": "result",
  "storage_provider": "r2",
  "bucket": "easyads-dev",
  "object_key": "workspaces/workspace_uuid/threads/thread_x/jobs/job_x/final_0.png",
  "mime_type": "image/png",
  "size_bytes": 123456,
  "width": 1024,
  "height": 1024,
  "public_url": null,
  "final_image_url": "https://...",
  "download_url": "https://...",
  "preview_url": null,
  "url_mode": "signed",
  "signed_url_expires_at": "2026-06-03T00:00:00+00:00",
  "public_serving": true,
  "metadata": {}
}
```

---

## 5. R2 success payload

When R2 upload is enabled and succeeds, the payload should include browser-safe URLs and asset metadata.

Example:

```json
{
  "schema_version": "result_artifact_v1",
  "final_image_path": "data/outputs/job_db/final_0.png",
  "download_path": "data/outputs/job_db/final_0.png",
  "final_asset_id": "asset_r2_uuid",
  "storage_provider": "r2",
  "bucket": "easyads-dev",
  "object_key": "workspaces/workspace_uuid/threads/thread_db/jobs/job_db/final_0.png",
  "url_mode": "signed",
  "final_image_url": "https://signed.example/final_0.png",
  "download_url": "https://signed.example/final_0.png",
  "signed_url_expires_at": "2026-06-03T00:00:00+00:00",
  "assets": {
    "final": {
      "asset_id": "asset_r2_uuid",
      "kind": "result",
      "storage_provider": "r2",
      "bucket": "easyads-dev",
      "object_key": "workspaces/workspace_uuid/threads/thread_db/jobs/job_db/final_0.png",
      "mime_type": "image/png",
      "size_bytes": 123456,
      "width": 1024,
      "height": 1024,
      "final_image_url": "https://signed.example/final_0.png",
      "download_url": "https://signed.example/final_0.png",
      "url_mode": "signed",
      "signed_url_expires_at": "2026-06-03T00:00:00+00:00",
      "public_serving": true,
      "metadata": {
        "source": "generation_job_r2_upload"
      }
    }
  }
}
```

Notes:

```text
- final_image_url and download_url must be browser-safe http(s) URLs.
- signed URLs may expire.
- signed URL refresh is a separate follow-up milestone.
```

---

## 6. Local-dev fallback payload

When R2 is disabled or upload falls back to local-dev, the payload may still include an asset reference. However, browser-safe URL fields remain `null`.

Example:

```json
{
  "schema_version": "result_artifact_v1",
  "final_image_path": "data/outputs/job_db/final_0.png",
  "download_path": "data/outputs/job_db/final_0.png",
  "final_asset_id": "asset_local_uuid",
  "storage_provider": "local_dev",
  "bucket": "local-dev",
  "object_key": "data/outputs/job_db/final_0.png",
  "url_mode": null,
  "final_image_url": null,
  "download_url": null,
  "signed_url_expires_at": null,
  "assets": {
    "final": {
      "asset_id": "asset_local_uuid",
      "kind": "result",
      "storage_provider": "local_dev",
      "bucket": "local-dev",
      "object_key": "data/outputs/job_db/final_0.png",
      "mime_type": "image/png",
      "size_bytes": 123456,
      "width": 1024,
      "height": 1024,
      "final_image_url": null,
      "download_url": null,
      "url_mode": null,
      "signed_url_expires_at": null,
      "public_serving": false,
      "metadata": {
        "source": "generation_job_local_artifact",
        "serving_status": "not_public"
      }
    }
  }
}
```

Important:

```text
local_dev object_key may contain a repo-relative data/outputs/... path.
This does not mean the file is browser-accessible.
FE must not use data/outputs/... as img src or download href.
```

---

## 7. Path policy

Allowed repo-relative development trace paths:

```text
data/outputs/{job_id}/final_0.png
data/outputs/{job_id}/background_0.png
data/outputs/{job_id}/metadata.json
data/logs/...
```

Forbidden path values in API response:

```text
C:\Users\...
C:/Users/...
/home/...
/mnt/...
/tmp/...
/var/...
file://...
../data/...
..\data\...
```

`final_image_path`, `download_path`, `metadata_path`, and other `*_path` fields may contain only approved repo-relative trace paths.

`object_key` is a storage key and may contain R2 object key values such as:

```text
workspaces/{workspace_id}/threads/{thread_id}/jobs/{job_id}/final_0.png
```

Path traversal such as `../` or `workspaces/../secrets` must be rejected.

---

## 8. URL policy

Browser-safe URL fields must be `http://` or `https://`.

URL fields include:

```text
final_image_url
download_url
preview_image_url
copy_visual_preview_url
thumbnail_url
public_url
preview_url
any future *_url field
```

Forbidden URL values:

```text
file://...
data:image/png;base64,...
javascript:...
```

Unsafe URL values should be removed or set to `null` before API response serialization.

---

## 9. Secret and large payload sanitizer policy

The result payload must not expose secrets or raw image data.

Blocked key patterns include:

```text
api_key
openai_api_key
hf_token
huggingface_token
token
authorization
password
secret
service_role_key
access_key
secret_access_key
r2_secret
```

Safe presence booleans may be allowed:

```text
api_key_present
hf_token_present
secret_configured
```

The payload must not contain:

```text
base64 image data
raw image bytes
raw prompt containing secrets
chain-of-thought
hidden reasoning
local absolute file paths
```

Large strings that resemble base64/image bytes should be removed or truncated.

---

## 10. GenerationJob response policy

`GenerationJobResponse.result_payload` remains a dict-like payload for compatibility.

The API response must preserve existing fields:

```text
job_id
thread_id
status
progress_percent
current_stage
output_path
result_payload
error
metadata
created_at
updated_at
```

Before returning API response:

```text
1. result_payload must pass the artifact payload sanitizer.
2. job.output_path must be normalized and must not expose local absolute paths.
3. final_image_url/download_url must be retained only if browser-safe.
```

DB-internal rows may keep repo-relative local trace paths, but public API responses must not expose local absolute paths.

---

## 11. FE binding policy

FE should prefer URLs in this order:

```text
final_image_url
preview_image_url
copy_visual_preview_url
download_url
```

FE download URL should prefer:

```text
download_url
final_image_url
preview_image_url
copy_visual_preview_url
```

FE must not use these as image src or download href:

```text
final_image_path
download_path
output_path
data/outputs/...
data/logs/...
```

When URL fields are null:

```text
- The job may still be done.
- The result may still have local-dev asset metadata.
- FE should show "browser-displayable URL not ready" or equivalent state.
- Download should remain disabled.
```

---

## 12. DB and Archive direction

This contract is designed for later Archive integration.

Archive/detail views should use:

```text
generation_outputs.asset_id
assets.object_key
assets.storage_provider
assets.public_url or signed URL refresh result
result_payload.assets.final
```

`generation_outputs` should point to the authoritative asset row.

`result_payload.assets.final` is a denormalized API snapshot for client convenience and debug visibility.

---

## 13. Current limitations

```text
- signed URL refresh API is not implemented.
- thumbnail/background/copy_visual_preview upload is not required in v1.
- Archive API is not implemented.
- Actual R2 smoke is separate from unit tests.
- Modal GPU execution writes successful results into this contract instead of defining a separate payload. Modal image bytes/base64 values are transient runtime data and must not be stored in `result_payload`, events, or public API responses.
```

---

## 14. Follow-up work

Recommended next steps:

```text
1. Local Postgres or Supabase dev DB smoke.
2. R2 actual upload smoke.
3. FE mobile QA with real final_image_url/download_url.
4. signed URL refresh API.
5. thumbnail/background/copy_visual_preview upload expansion.
6. Modal GPU execution bridge.
7. Archive DB-backed API.
```
