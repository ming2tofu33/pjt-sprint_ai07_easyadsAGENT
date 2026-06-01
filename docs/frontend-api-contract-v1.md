# Frontend API Contract v1

## 1. Purpose

This document defines backend API request and response contracts for frontend integration. It is not a frontend screen implementation guide. BFF route handlers and API client helpers may exist in `apps/web`, but screen-level frontend implementation, query hooks, and frontend mock data are out of scope for this contract.

## 2. Current Scope

Reference Catalog, BrandKit, and GenerationJob FastAPI routes are implemented in v1.

Implemented routes:

- `GET /api/v1/references`
- `GET /api/v1/references/{template_id}`
- `GET /api/v1/references/{template_id}/similar`
- `GET /api/v1/brand-kits/current`
- `POST /api/v1/brand-kits`
- `GET /api/v1/brand-kits/{brand_kit_id}`
- `PATCH /api/v1/brand-kits/{brand_kit_id}`
- `POST /api/v1/generation-jobs`
- `GET /api/v1/generation-jobs/{job_id}`

Archive, Usage, and Settings routers are still out of scope. Persistence, object storage, background queues, and real image/model calls also remain out of scope.

## 3. Common Response Format

Successful response DTOs use explicit `success: true` fields and a typed payload such as `items`, `template`, `brand_kit`, or `job`. Each response includes `ApiMeta` with `request_id`, `timestamp`, and `version`.

```json
{
  "success": true,
  "items": [],
  "pagination": { "limit": 20, "offset": 0, "total": 0, "has_more": false },
  "meta": { "request_id": "req_001", "timestamp": "2026-05-29T00:00:00Z", "version": "v1" }
}
```

## 4. Common ErrorResponse

Errors use `ErrorResponse` with a stable `error_code`, a user-safe message, optional detail, and optional recovery actions. API keys, tokens, and local absolute paths must not be returned.

```json
{
  "success": false,
  "error_code": "template_not_found",
  "message": "Reference template was not found.",
  "detail": null,
  "recovery_actions": [
    { "action": "browse_references", "label": "Browse reference templates", "href": "/references", "metadata": {} }
  ],
  "meta": { "request_id": "req_001", "timestamp": null, "version": "v1" }
}
```

## 5. References API Contract

Reference list cards use a slim DTO and do not expose internal `thumbnail_path` or `preview_path`. Until asset serving exists, `thumbnail_url` and `preview_url` can be `null` or a backend-controlled public URL.

Contracts:
- `ReferenceTemplateCardResponse`
- `ReferenceTemplateListResponse`
- `ReferenceTemplateDetailResponse`
- `ReferenceTemplateSimilarResponse`

### Reference Catalog Routes

#### `GET /api/v1/references`

Purpose: list seed reference templates for a gallery-style picker.

Query params:
- `keyword`
- `category`
- `business_type`
- `ad_format`
- `platform`
- `aspect_ratio`
- `tags`
- `style_keywords`
- `limit`
- `offset`
- `sort_by`
- `active_only`

Repeated query params are supported for list filters, for example `?tags=CTA&tags=event`. The response schema is `ReferenceTemplateListResponse`. Empty searches return `200` with `items: []` and an `EmptyState`.

#### `GET /api/v1/references/{template_id}`

Purpose: fetch a single reference template detail for preview and selection. The response schema is `ReferenceTemplateDetailResponse`. Missing templates return a structured `ErrorResponse` with `reference_template_not_found`.

The `detail` object may include style hints such as `style_keywords`, `color_palette`, `layout_hint`, `typography_hint`, `background_style`, and `has_source_image`. Internal local asset paths are not returned.

#### `GET /api/v1/references/{template_id}/similar`

Purpose: return deterministic similar templates based on the seed catalog scoring rules. Query param `limit` accepts values from 1 to 50. The response schema is `ReferenceTemplateSimilarResponse`. Missing templates return a structured `ErrorResponse` with `reference_template_not_found`.

Current limitations:
- `thumbnail_url` and `preview_url` are `null` while asset serving is not implemented.
- Internal local paths are not exposed through the public API response.
- The catalog is seed metadata based, not database backed.
- Saved reference state is not implemented.
- Static file serving and object storage are not implemented.

## 6. BrandKit API Contract

Brand kit DTOs describe store identity, tone, colors, phrases, logo asset references, and representative products. `BrandKitCreateRequest` requires non-empty `store_name` and `business_type`.

Contracts:
- `BrandProduct`
- `BrandKitResponse`
- `BrandKitCreateRequest`
- `BrandKitUpdateRequest`
- `BrandKitGetCurrentResponse`

### BrandKit Routes

#### `GET /api/v1/brand-kits/current`

Purpose: return the current BrandKit for a user. Query param `user_id` is optional; when omitted, the backend skeleton uses `demo_user`.

Response schema: `BrandKitGetCurrentResponse`.

Empty state: when no BrandKit exists, the response returns `has_brand_kit: false`, `brand_kit: null`, and an `EmptyState` with `kind: "no_brand_kit"`.

#### `POST /api/v1/brand-kits`

Purpose: create a BrandKit in the in-memory skeleton store and mark it as current for the user.

Request body: `BrandKitCreateRequest`.

Response schema: `BrandKitMutationResponse`.

Validation errors such as an empty `store_name`, empty `business_type`, or invalid `brand_colors` return a structured error with `invalid_brand_kit_request`.

#### `GET /api/v1/brand-kits/{brand_kit_id}`

Purpose: fetch a BrandKit by id.

Path params: `brand_kit_id`.

Response schema: `BrandKitMutationResponse`.

Missing ids return a structured error with `brand_kit_not_found`.

#### `PATCH /api/v1/brand-kits/{brand_kit_id}`

Purpose: partially update an existing BrandKit.

Path params: `brand_kit_id`.

Request body: `BrandKitUpdateRequest`. Fields omitted or sent as `null` keep their existing values. Empty lists such as `brand_colors: []` are treated as explicit updates.

Response schema: `BrandKitMutationResponse`.

Missing ids return `brand_kit_not_found`. Invalid update payloads return `invalid_brand_kit_request`.

Current limitations:
- BrandKit storage is in-memory only.
- Data is not retained after server restart.
- Real database persistence is planned for a later milestone.
- Logo upload and object storage are not implemented.
- Authenticated user extraction is not implemented.
- When `user_id` is omitted, `demo_user` is used.

## 7. GenerationJob API Contract

Generation jobs start in `queued_only` mode by default. This contract carries reference template selection, optional image paths, copy mode, user plan, status, progress, output path, and result payload. The API contract does not imply real image generation or external model calls.

Contracts:
- `GenerationJobCreateRequest`
- `GenerationProgress`
- `GenerationJobResponse`
- `GenerationJobCreateResponse`
- `GenerationJobGetResponse`

### Generation Job Routes

#### `POST /api/v1/generation-jobs`

Purpose: create a generation job record that the frontend can poll.

Request body: `GenerationJobCreateRequest`.

Response schema: `GenerationJobCreateResponse`.

Run mode policy:
- `queued_only`: create a queued job only.
- `mock_immediate`: run deterministic mock execution, write local mock artifacts, and return a completed job.
- `graph_immediate`: currently degrades to `queued_only`; no graph execution happens.

`mock_immediate` result:
- `status: "done"`
- `progress.progress_percent: 100`
- `progress.current_stage: "completed"`
- `output_path: "data/outputs/{job_id}/final_0.png"`
- `result_payload` includes background, final, metadata, prompt, and validation artifact paths.

#### `GET /api/v1/generation-jobs/{job_id}`

Purpose: fetch a generation job for polling.

Path params: `job_id`.

Response schema: `GenerationJobGetResponse`.

Error responses:
- Missing job returns `generation_job_not_found`.
- Missing selected reference template during create returns `reference_template_not_found`.
- Invalid create payload returns `invalid_generation_job_request`.

Current limitations:
- GenerationJob storage is in-memory only.
- Job state is not retained after server restart.
- Worker and queue execution are not implemented.
- `build_marketing_graph()` is not executed.
- GPT-image-2, SD3.5, and FLUX are not called.
- LLM/VLM/OCR calls are not made.
- Output URL/static serving is not implemented.
- `download_url` is `null`.

## 8. Archive Response Contract

Archive DTOs expose saved or generated ad records with public URLs when available. Internal generated file paths should not be exposed directly through public API responses.

Contracts:
- `ArchiveItemResponse`
- `ArchiveListResponse`

## 9. Usage Response Contract

Usage DTOs summarize plan limits, consumption, remaining quota, usage rate, and recent usage events.

Contracts:
- `UsageEventResponse`
- `UsageSummaryResponse`

## 10. Settings Response Contract

Settings DTOs define default output preferences and notification preferences.

Contracts:
- `NotificationSettingsResponse`
- `UserAppSettingsResponse`
- `UserAppSettingsUpdateRequest`

## 11. Not Implemented Yet

- Archive, Usage, and Settings routers
- Database persistence
- Redis, Celery, or queue execution
- Object storage and signed URLs
- Static asset serving for reference thumbnails/previews
- Saved reference state
- Logo upload and object storage integration for BrandKit
- Authenticated user extraction for BrandKit
- Frontend gallery, hooks, API clients, or mock data files
- Real GPT-image-2, SD3.5, FLUX, LLM, VLM, OCR, rembg, or SAM calls

## 12. FE/BFF vs Backend Responsibilities

Backend owns DTO validation, stable response shapes, domain service integration, and safe public asset references. FE/BFF owns screen composition, query hooks, caching strategy, frontend mock data during UI prototyping, and route-level presentation logic.

`AssetRef.path` exists for transitional backend contract compatibility, but public API handlers should avoid filling it with local absolute paths. Prefer `url` or `thumbnail_url` once asset serving is available; keep internal filesystem paths out of frontend-facing responses.
