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

Archive skeleton support is partially prepared for MVP generated-result flows, but production persistence and complete frontend archive integration are not implemented. Usage and Settings routers are still out of scope. Persistence, object storage, background queues, unguarded image/model calls, and production serving remain out of scope. Guarded GPT-image-2 and SD3.5 lanes exist but are disabled by default and are not executed in CI/default tests.

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
- `thumbnail_url` and `preview_url` may be backend-controlled public URLs when reference asset serving is enabled.
- Internal local paths are not exposed through the public API response.
- The catalog is seed metadata based, not database backed.
- Saved reference state is not implemented.
- Object storage is not implemented.
- Generated result static serving is separate from reference asset serving and remains a later milestone.

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
- `gpt_image_2_actual` / `gpt_image_2_smoke`: request the guarded GPT-image-2 lane.
- `sd35_local` / `sd35_local_smoke`: request the guarded SD3.5 local lane.

Actual generation lane policy:
- All actual generation lanes are disabled by default.
- GPT-image-2 requires `EASYADS_ENABLE_EXTERNAL_T2I=true`, `EASYADS_ENABLE_GPT_IMAGE_2=true`, and an `OPENAI_API_KEY`.
- SD3.5 requires `EASYADS_ENABLE_SD35_LOCAL=true` plus local dependency/model availability.
- CI/default tests do not call external APIs, load local models, download HF models, or require GPU.
- If an actual lane is requested without the required guard conditions, the job returns `status: "failed"` with `error.error_code: "t2i_engine_not_enabled"` or `t2i_engine_unavailable`.

`mock_immediate` result:
- `status: "done"`
- `progress.progress_percent: 100`
- `progress.current_stage: "completed"`
- `output_path: "data/outputs/{job_id}/final_0.png"`
- `result_payload.schema_version: "result_artifact_v1"`
- `result_payload` includes background, final, metadata, prompt, validation, copy, layout, and render result artifact paths.
- FE-readable summaries are available at `result_payload.prompt_summary`, `result_payload.validation_summary`, `result_payload.copy_summary`, and `result_payload.layout_summary`.
- `result_payload.download_url` and `result_payload.final_image_url` are `null` until static serving or object storage is implemented.

Result fields FE can safely bind:
- `job.status`
- `job.progress`
- `job.output_path`
- `job.result_payload.final_image_path`
- `job.result_payload.download_url`
- `job.result_payload.final_image_url`
- `job.result_payload.prompt_summary`
- `job.result_payload.validation_summary`
- `job.result_payload.copy_summary`
- `job.result_payload.layout_summary`


### FE Result Binding Policy

Frontend result screens should read `GenerationJob.result_payload` before falling back to legacy mock data. Preview and download handling must distinguish public URLs from local development paths:

- Use `result_payload.final_image_url` first when present.
- Use `result_payload.download_url` as the next public URL fallback.
- Treat `result_payload.final_image_path`, `result_payload.download_path`, and `job.output_path` as repo-relative development paths, not browser-safe public URLs.
- Do not render `<img src="data/outputs/...">` or `<a href="data/outputs/...">`.
- If public URLs are `null`, disable the download action and show that the artifact exists but public serving is not connected yet.
- Copy actions may include `job_id`, `status`, engine/render mode, repo-relative final path, and prompt/validation/copy/layout summaries because they do not require a public URL.

Polling policy: FE may poll `GET /api/v1/generation-jobs/{job_id}` while `status` is `queued` or `running`, then stop on `done` or `failed`.

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
- GPT-image-2 and SD3.5 lanes exist but are guarded and disabled by default; FLUX is still not implemented here.
- LLM/VLM/OCR calls are not made.
- Output URL/static serving is not implemented.
- `download_url` is `null`.
- `result_payload.download_path` is a repo-relative development path and is not a public URL.
- `result_payload.download_url` and `result_payload.final_image_url` remain `null` until static serving or object storage is implemented.
- The mock artifact contract is local-path based for development tracing only; public URL serving is a later milestone.

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

- Usage and Settings routers
- Production database persistence
- Redis, Celery, or queue execution
- Object storage and signed URLs
- Static asset serving for generated results
- Saved reference state
- Logo upload and object storage integration for BrandKit
- Authenticated user extraction for BrandKit
- Production archive persistence and full archive frontend integration
- Unguarded or default GPT-image-2 / SD3.5 calls
- FLUX generation lane
- LLM, VLM, OCR, rembg, or SAM calls
- Production-grade manual smoke validation for GPT-image-2 / SD3.5

## 12. Reference Template Selection Flow

Frontend and BFF payloads may send `selectedReferenceTemplateId`. Orchestrator DTOs also accept this camelCase alias but store the canonical field as `selected_reference_template_id`.

Supported paths:

- `POST /api/generate/chat/start` forwards `selectedReferenceTemplateId` to `/v1/marketing/chat/start`.
- `POST /api/generate/photo/start` forwards `selectedReferenceTemplateId` to `/v1/marketing/photo/start`.
- `POST /api/generation-jobs` converts `selectedReferenceTemplateId` to `selected_reference_template_id` before calling `/api/v1/generation-jobs`.
- `GenerationJobCreateRequest` accepts both camelCase and snake_case field names.

Graph metadata expectations:

- `MarketingState.selected_reference_template_id` contains the selected id.
- `selected_reference_template` and `reference_template_selection` are populated after template resolution when the id is valid.
- `image_prompt_spec.metadata.selected_reference_template` and `image_prompt_spec.metadata.visual_template_id` are available for prompt planning traceability.
- `t2i_request.metadata.selected_reference_template_id` and `t2i_request.metadata.reference_template_selection` preserve the selection for downstream engines.

Reference asset proxy/static serving is independent from generated result serving. Do not use generated artifact local paths as reference asset URLs.

## 13. FE/BFF vs Backend Responsibilities

Backend owns DTO validation, stable response shapes, domain service integration, and safe public asset references. FE/BFF owns screen composition, query hooks, caching strategy, frontend mock data during UI prototyping, and route-level presentation logic.

`AssetRef.path` exists for transitional backend contract compatibility, but public API handlers should avoid filling it with local absolute paths. Prefer `url` or `thumbnail_url` once asset serving is available; keep internal filesystem paths out of frontend-facing responses.
