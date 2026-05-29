# Frontend API Contract v1

## 1. Purpose

This document defines backend API request and response contracts for frontend integration. It is not a frontend implementation guide. This milestone does not add Next.js `route.ts` files, React hooks, frontend API clients, or frontend mock data.

## 2. Current Scope

Backend Pydantic DTOs are provided for common responses, reference templates, brand kits, generation jobs, archive items, usage summaries, and user settings. Endpoint routers, persistence, object storage, background queues, and real image/model calls remain out of scope.

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

## 6. BrandKit API Contract

Brand kit DTOs describe store identity, tone, colors, phrases, logo asset references, and representative products. `BrandKitCreateRequest` requires non-empty `store_name` and `business_type`.

Contracts:
- `BrandProduct`
- `BrandKitResponse`
- `BrandKitCreateRequest`
- `BrandKitUpdateRequest`
- `BrandKitGetCurrentResponse`

## 7. GenerationJob API Contract

Generation jobs start in `queued_only` mode by default. This contract carries reference template selection, optional image paths, copy mode, user plan, status, progress, output path, and result payload. The API contract does not imply immediate image generation or external model calls.

Contracts:
- `GenerationJobCreateRequest`
- `GenerationProgress`
- `GenerationJobResponse`
- `GenerationJobCreateResponse`
- `GenerationJobGetResponse`

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

- FastAPI routers and endpoint handlers
- Database persistence
- Redis, Celery, or queue execution
- Object storage and signed URLs
- Frontend gallery, hooks, API clients, or mock data files
- Real GPT-image-2, SD3.5, FLUX, LLM, VLM, OCR, rembg, or SAM calls

## 12. FE/BFF vs Backend Responsibilities

Backend owns DTO validation, stable response shapes, domain service integration, and safe public asset references. FE/BFF owns screen composition, query hooks, caching strategy, frontend mock data during UI prototyping, and route-level presentation logic.

`AssetRef.path` exists for transitional backend contract compatibility, but public API handlers should avoid filling it with local absolute paths. Prefer `url` or `thumbnail_url` once asset serving is available; keep internal filesystem paths out of frontend-facing responses.
