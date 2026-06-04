# TLFP Implementation Notes

`docs/Production_Architecture_Specification.md` is the implementation source of truth for the Text-Layout-First Pipeline.

## Current Scope

- TLFP core schema is implemented in `orchestrator/app/schemas/text_layout.py`.
- `build_marketing_graph()` now routes generated `MarketingCopy` through:
  - `CopySpecParserNode`
  - `TextStyleBinderNode`
  - `TextLayoutPlannerNode`
  - `ImagePromptPlannerNode`
  - `PromptRendererNode`
  - `T2IRequestBuilderNode`
  - `T2IGenerationNode`
- Image generation remains mock-only in this graph.
- `TextLayoutSpec.slots` is the canonical source for later text composition.
- Existing `copy_space` values are only auxiliary hints.
- `ImagePromptSpec.reserved_text_areas` is used to reserve clean negative space for later Korean text overlay.
- `copy_generation_mode` is implemented with four deterministic branches:
  - `suggest_candidates`: generate three rule-based copy candidates, interrupt for user selection, then continue through TLFP.
  - `auto_pilot`: generate one rule-based `MarketingCopy`, then continue through TLFP.
  - `custom_input`: interrupt for user headline/subcopy when needed, validate without rewriting, then continue through TLFP.
  - `no_copy`: skip copy rendering intent, build `CopySpec(copy_mode="no_copy", items=[])`, and continue through TLFP with `render_text_in_image=false`.
- All copy branches merge back into `CopySpecParserNode`.
- `no_copy` means no post-processing text overlay is required. It does not allow the image model to draw text, letters, logos, or watermarks.
- After mock T2I generation, the graph now continues through:
  - `BackgroundValidationNode`
  - `SafeAreaGate`
  - `CopyPresenceRouter`
  - `TextRendererNode` for copy-present flows
  - `ReadabilityGate`
  - `FinalValidationNode`
  - `ResultNode`
- `no_copy` still runs background and safe-area checks, then bypasses `TextRendererNode` and `ReadabilityGate`.
- Copy-present flows render Korean copy after image generation using the deterministic PIL-based `TextRendererNode`.
- `TextRendererNode` now resolves cross-platform Korean fonts through `EASYADS_FONT_PATH` and system candidates, then falls back to PIL default without crashing.
- Headline, subheadline/body, promotion/badge, and CTA roles use separate sizing/treatment rules; CTA can render as a clearer rounded plate/button.
- Rule-based Copy Quality Policy trims excessive punctuation, removes overused promotional phrases from generated copy, and keeps `custom_input` copy unchanged except for warnings/quality metadata.
- ImagePromptPlanner v2 selects deterministic visual templates for cafe/dessert, restaurant/BBQ, beauty/salon, or a generic fallback template.
- Visual templates add business-aware composition, lighting, color palette hints, reserved text area guidance, and negative prompt additions while preserving `must_not_include_text=true`.
- `ResultNode` writes the final `result_payload`, including `output_path`, validation summary, and artifact references.
- GenerationJob `mock_immediate` uses Result Artifact Contract v1 with `background_0.png`, `final_0.png`, `metadata.json`, `prompt.json`, `validation.json`, `copy.json`, `layout.json`, and `render_result.json`.
- GenerationJob actual T2I lanes are guarded and disabled by default. `gpt_image_2_actual`/`gpt_image_2_smoke` require explicit external T2I and GPT-image-2 env flags plus an OpenAI API key. `sd35_local`/`sd35_local_smoke` require the SD3.5 local env flag and local dependency/model availability. `flux_local`/`flux_local_smoke` require the FLUX local env flag and local dependency/model availability.
- CI/default tests do not call GPT-image-2, load SD3.5 or FLUX, download HF models, or require GPU.
- `download_url` and `final_image_url` remain `null` because static serving/object storage is not implemented.
- Vision Pipeline MVP preprocessing is available before validation when `source_image_path` or `reference_image_path` is supplied.
- `ReferenceStyleProfile` can inform `ImagePromptPlannerNode` with deterministic palette and style hints.
- `ProductPreserveSpec` is currently a `center_bbox_stub` only; no real product-preserving edit is performed.
- `image_preprocess_result` is the latest preprocess result only. Use `vision_pipeline_results` for source/reference history, `product_preserve_spec` for product metadata, and `reference_style_profile` for style metadata.

## Deterministic Boundaries

- `PromptRenderer`, `T2IRequestBuilder`, layout planning, style binding, and state updates must remain deterministic.
- LLM calls should be used only for future generation, classification, or validation nodes with Pydantic structured output.
- LLM calls must not own policy, routing, schema conversion, or state mutation.
- Vector DBs must be used only as example or reference retrieval layers, not as rule engines.
- Relational DB and vector store integrations are not part of this milestone.
- Background validation, safe-area checks, text rendering, readability checks, final validation, and result assembly are deterministic MVP steps.
- `ReadabilityGate` only reports rule-based contrast and layout issues; it does not trigger automatic regeneration.
- `TextRendererNode` uses `TextLayoutSpec.slots` as the canonical text placement contract.
- Vision preprocessing, reference-style extraction, and product-preserve metadata are deterministic PIL-based stubs.

## Implemented MVP

- `TextRenderer`: deterministic PIL-based MVP implemented.
- `ReadabilityGate`: rule-based contrast/layout report MVP implemented.
- `BackgroundValidation`: file/dimension/render policy validation with OCR/VLM checks explicitly marked `not_run`.
- `SafeAreaGate`: bbox-based reserved text area and product-zone overlap validation implemented.
- `ResultNode`: final output payload and artifact reference assembly implemented.
- `Vision Pipeline MVP`: PIL preprocess, reference style stub, product preserve stub, and optional graph route implemented.
- `GenerationJob DB foundation`: Supabase/Postgres migration SQL and repository layer are prepared while `EASYADS_DB_BACKEND=memory` remains the default.
- The DB repository foundation is not yet a full production rollout. Actual Supabase smoke, R2 asset upload, Modal job persistence, and production Auth/RLS enforcement are separate follow-up milestones.
- `GenerationJob persistence v1`: postgres backend can persist create/get/running/done/failed lifecycle changes, record generation job events, and create local-dev asset/output placeholders for completed jobs.
- `R2 asset storage v1`: when explicitly enabled, `mark_generation_job_done()` can upload final local artifacts to Cloudflare R2, persist R2 asset metadata, and fill `result_payload.final_image_url` / `download_url`. Default CI and local test environments still keep R2 disabled.
- `Modal GPU execution backend v1`: eligible SD3.5/FLUX run modes can be routed through a guarded Modal bridge when `EASYADS_T2I_EXECUTION_BACKEND=modal` and `EASYADS_ENABLE_MODAL_EXECUTION=true`. Default tests use fake clients only and never call Modal or load models.

## Not Implemented Yet

- Actual OCR.
- Actual VLM quality gates.
- Actual product detection or segmentation.
- Actual product-preserving image edit.
- Actual reference-guided image generation beyond metadata prompt hints.
- Unguarded actual GPT-image-2, SD3.5, or FLUX generation.
- Actual Modal GPU smoke or deployed Modal app management.
- Signed URL refresh APIs and broader static artifact serving policy.
- Production Supabase Auth/RLS enforcement.
- Automatic regeneration loops.
- Production-grade font packaging.
- Real product occlusion detection.
- Actual text artifact detection by OCR/VLM.
- `LLMAdapter`, structured output adapters, and `ModelRouter` are planned for a later model-integration milestone.

## Rendering Policy

- The image model must not render text, letters, numbers, Hangul, logos, or watermarks.
- `render_text_in_image=false` is preserved through prompt planning, T2I request metadata, validation, and result payloads.
- `no_copy` means post-processing text overlay is skipped. It does not permit text inside the generated image.
- Generated files under `data/outputs/` are runtime artifacts and must not be committed.

## Manual T2I Smoke Reports

`scripts/smoke_generation_job_t2i.py` creates JSON and Markdown reports under `data/logs/` for guarded GPT-image-2, SD3.5, and FLUX lanes. Dry-run mode never calls external APIs or loads local models. Non-dry-run smoke is blocked unless the explicit engine flags and credentials/model readiness are present. Reports store only boolean credential presence, prompt hash/preview, job id, safe result payload fields, and error summaries; raw API keys, HF tokens, base64 image data, and image bytes must not be written.

Generated reports under `data/logs/` and generated artifacts under `data/outputs/` are runtime files and must not be committed.

## Reference Template Flow

`selectedReferenceTemplateId` is accepted by frontend/BFF camelCase payloads and normalized to `selected_reference_template_id` inside Orchestrator. Legacy chat/photo starts put the id into graph state before `ReferenceTemplateResolveNode`; GenerationJob starts preserve it in response and metadata. `ImagePromptPlanner` stores selected template metadata and visual template id in `image_prompt_spec.metadata`, and `T2IRequestBuilder` carries `selected_reference_template_id` plus `reference_template_selection` into `t2i_request.metadata`.

## GPT-image-2 Quality Batch v1

`scripts/run_gpt_image2_quality_batch.py` runs a guarded GenerationJob API batch for GPT-image-2 actual quality review. Dry-run mode records planned cafe, restaurant, and beauty cases without external calls. Actual mode is blocked unless explicit T2I/GPT-image-2 env flags, `OPENAI_API_KEY`, `EASYADS_QUALITY_BATCH_CONFIRM=true`, and `--confirm-cost` are all present. The runner enforces one image per case and a maximum of six cases, writes safe JSON/Markdown reports under `data/logs/`, and leaves generated images under `data/outputs/` for manual review. Reports must not include raw API keys, base64 image data, or image bytes.

## ImagePrompt v3

ImagePrompt v3 introduces the `ScenePlan`, `PromptQualityPolicy`, and `EnginePromptAdapter` (with adapters for `gpt_image_2`, `sd35_large`, and `flux`). In v3, the beauty industry template has been split into four subtypes: `beauty_skincare`, `beauty_hair`, `beauty_nail`, and `beauty_spa` based on v1 manual quality review findings. All v3 metadata is merged cleanly into `ImagePromptSpec.metadata` and carried into `T2IRequest.metadata` without breaking backward compatibility.

## Copy Visual Quality Loop v1

- Added deterministic copy tone policies for cafe, restaurant BBQ, beauty subtypes, and generic businesses.
- Added rule-based overlay validation for contrast, safe area complexity, and clipping without OCR/VLM/model calls.
- Added `scripts/run_copy_visual_overlay_review.py` to create local overlay previews from existing batch artifacts only.
- Runtime previews and reports are written under ignored `data/outputs` and `data/logs` paths and are not commit targets.
- Beauty outputs need stronger plate/shadow defaults; cafe and restaurant outputs are more likely to work with short copy and controlled CTAs.

## FLUX Lane Comparison v1

- Added a guarded FLUX local lane with `flux_local` and `flux_local_smoke` run modes.
- FLUX is disabled by default and performs no `diffusers`/`torch` import or model load until `EASYADS_ENABLE_FLUX_LOCAL=true` and an actual guarded execution path are used.
- The FLUX engine stores safe metadata only: model id when using a public model reference, model source, local path presence, HF token presence, and generation parameters. Raw HF tokens and local absolute paths are not exposed.
- `scripts/run_t2i_engine_comparison.py` writes dry-run or guarded actual comparison reports for GPT-image-2, SD3.5, and FLUX under `data/logs/`.
