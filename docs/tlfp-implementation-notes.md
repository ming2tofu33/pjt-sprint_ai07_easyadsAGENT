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

## Deterministic Boundaries

- `PromptRenderer`, `T2IRequestBuilder`, layout planning, style binding, and state updates must remain deterministic.
- LLM calls should be used only for future generation, classification, or validation nodes with Pydantic structured output.
- LLM calls must not own policy, routing, schema conversion, or state mutation.
- Vector DBs must be used only as example or reference retrieval layers, not as rule engines.
- Relational DB and vector store integrations are not part of this milestone.

## Not Implemented Yet

- `copy_generation_mode` and `CopyModeRouter` are planned for 4-B.
- `TextRenderer` is planned for the next rendering milestone.
- `ReadabilityGate` is planned for the next validation milestone.
- Background validation, final validation, and VLM quality gates are not implemented here.
- `LLMAdapter` and `ModelRouter` are planned for a later model-integration milestone.
