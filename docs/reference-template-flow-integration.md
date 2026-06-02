# Reference Template Flow Integration

This note documents how `selectedReferenceTemplateId` moves from the frontend reference gallery to backend generation metadata.

## End-to-End Path

1. `ReferenceBrowseStep` fetches backend reference cards through the BFF and falls back to local sample cards only when the API has no usable items or fails.
2. Selecting a backend reference card writes `selectedReferenceTemplateId`, `selectedReferenceTemplateTitle`, and a draft prompt to `sessionStorage` via `generation-request-context.ts`.
3. `ChatGenerateClient` reads that request context on mount and stores the selected template in `ChatFlowState` without overwriting an existing user prompt.
4. `startChatGeneration` and `startPhotoGeneration` include `selectedReferenceTemplateId` in the BFF request body.
5. The BFF accepts `selectedReferenceTemplateId` for chat/photo starts and forwards it to the legacy Orchestrator APIs. For GenerationJob proxy calls, the BFF normalizes camelCase to `selected_reference_template_id`.
6. Orchestrator legacy chat/photo APIs accept camelCase aliases and put `selected_reference_template_id` into graph state and `context.extra`.
7. `GenerationJobCreateRequest` accepts both `selectedReferenceTemplateId` and `selected_reference_template_id` and preserves the value on `GenerationJobResponse.selected_reference_template_id` and job metadata.
8. The marketing graph resolves the template through `ReferenceTemplateResolveNode`, then `ImagePromptPlanner` and `T2IRequestBuilder` carry template metadata into prompt and T2I request metadata.

## Naming Policy

- Frontend and browser-facing BFF payloads may use camelCase: `selectedReferenceTemplateId`.
- Orchestrator API schemas accept camelCase aliases but store canonical snake_case: `selected_reference_template_id`.
- BFF GenerationJob proxy converts camelCase to snake_case before forwarding to `/api/v1/generation-jobs`.

## Legacy API Support

The legacy chat/photo flow remains supported:

- `POST /v1/marketing/chat/start`
- `POST /v1/marketing/photo/start`

Both routes now accept `selectedReferenceTemplateId` and `copyGenerationMode` while keeping prior defaults.

## Asset Boundary

Reference asset proxy/static serving and generated result serving are separate concerns. Reference templates may expose backend-controlled public thumbnail or preview URLs. Generated artifacts still use `ResultArtifactPayload` rules and must not treat repo-relative paths as public browser URLs.

## Non-Goals

This integration does not change image quality, prompts, copy quality, model selection, object storage, archive behavior, or actual GPT-image-2/SD3.5 execution behavior.
