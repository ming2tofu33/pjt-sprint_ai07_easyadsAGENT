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
- `ResultNode` writes the final `result_payload`, including `output_path`, validation summary, and artifact references.

## Deterministic Boundaries

- `PromptRenderer`, `T2IRequestBuilder`, layout planning, style binding, and state updates must remain deterministic.
- LLM calls should be used only for future generation, classification, or validation nodes with Pydantic structured output.
- LLM calls must not own policy, routing, schema conversion, or state mutation.
- Vector DBs must be used only as example or reference retrieval layers, not as rule engines.
- Relational DB and vector store integrations are not part of this milestone.
- Background validation, safe-area checks, text rendering, readability checks, final validation, and result assembly are deterministic MVP steps.
- `ReadabilityGate` only reports rule-based contrast and layout issues; it does not trigger automatic regeneration.
- `TextRendererNode` uses `TextLayoutSpec.slots` as the canonical text placement contract.

## Implemented MVP

- `TextRenderer`: deterministic PIL-based MVP implemented.
- `ReadabilityGate`: rule-based contrast/layout report MVP implemented.
- `BackgroundValidation`: file/dimension/render policy validation with OCR/VLM checks explicitly marked `not_run`.
- `SafeAreaGate`: bbox-based reserved text area and product-zone overlap validation implemented.
- `ResultNode`: final output payload and artifact reference assembly implemented.

## Not Implemented Yet

- Actual OCR.
- Actual VLM quality gates.
- Actual product detection or segmentation.
- Automatic regeneration loops.
- Advanced Korean typography/font management.
- Production-grade font loading.
- Real product occlusion detection.
- Actual text artifact detection by OCR/VLM.
- `LLMAdapter`, structured output adapters, and `ModelRouter` are planned for a later model-integration milestone.

## Rendering Policy

- The image model must not render text, letters, numbers, Hangul, logos, or watermarks.
- `render_text_in_image=false` is preserved through prompt planning, T2I request metadata, validation, and result payloads.
- `no_copy` means post-processing text overlay is skipped. It does not permit text inside the generated image.
- Generated files under `data/outputs/` are runtime artifacts and must not be committed.
