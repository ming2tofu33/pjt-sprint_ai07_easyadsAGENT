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

## Deterministic Boundaries

- `PromptRenderer`, `T2IRequestBuilder`, layout planning, style binding, and state updates must remain deterministic.
- LLM calls should be used only for future generation, classification, or validation nodes with Pydantic structured output.
- LLM calls must not own policy, routing, schema conversion, or state mutation.
- Vector DBs must be used only as example or reference retrieval layers, not as rule engines.
- Relational DB and vector store integrations are not part of this milestone.

## Not Implemented Yet

- `TextRenderer` is planned for the next rendering milestone.
- `ReadabilityGate` is planned for the next validation milestone.
- Background validation, SafeAreaGate, final validation, and VLM quality gates are not implemented here.
- `LLMAdapter`, structured output adapters, and `ModelRouter` are planned for a later model-integration milestone.
