# LLM/VLM Metadata Contract v1

## Purpose

This document defines the first shared metadata contract for future LLM/VLM-capable nodes.

The source priority for this work is `markdown/llm 연동 시 보완사항.md`. This v1 scope does not add real OpenAI, Gemini, Gemma, Qwen, OCR, or VLM calls. It only standardizes the payload shape that those calls may use later.

## Scope

Implemented files:

```text
orchestrator/app/llm/metadata_contracts.py
orchestrator/app/llm/metadata_builders.py
orchestrator/tests/test_llm_metadata_contracts.py
```

The metadata contract is designed to sit beside:

```text
docs/llm-model-policy.md
docs/llm-langgraph-schema-v1.md
docs/tlfp-implementation-notes.md
docs/vision-pipeline-mvp.md
docs/secrets.md
```

Those documents remain responsible for model policy, graph workflow, TLFP behavior, vision stubs, and secret handling. This document is only about node input payloads for future model calls.

## Common Payload Shape

Every builder returns a JSON-serializable dict with this shape:

```json
{
  "trace": {
    "schema_version": "llm_marketing_v1",
    "job_id": "job_123",
    "thread_id": "thread_123",
    "revision": 1,
    "node_name": "image_prompt_planner"
  },
  "task": {
    "objective": "Plan a text-free commercial background prompt while preserving reserved text areas.",
    "output_schema": "ImagePromptSpec"
  },
  "available_state": {},
  "constraints": {},
  "output_rules": {
    "structured_output_only": true,
    "no_chain_of_thought": true,
    "include_reasoning_summary_only": true
  }
}
```

## Common Rules

All metadata builders preserve these rules:

```text
structured_output_only=true
no_chain_of_thought=true
include_reasoning_summary_only=true
render_text_in_image=false
must_not_include_text=true
do_not_invent includes phone, address, price, discount, event_period
```

The sanitizer removes:

```text
API keys
secret-bearing tokens
secrets
passwords
raw image bytes
binary/base64 payload fields
chain-of-thought / hidden reasoning / raw reasoning fields
exact prompt fields
```

`reasoning_summary` is allowed because it is the user-safe summary field used by the existing schema policy.
Usage accounting keys such as `token_usage`, `prompt_tokens`, `completion_tokens`, and `total_tokens` are also allowed because they are not credentials.

## Builder Functions

The core builder module exposes:

```python
build_common_trace_metadata(state, node_name)
build_common_constraints_metadata(state)
build_validator_metadata(state)
build_tone_binding_metadata(state)
build_copy_generation_metadata(state, node_name="copy_generation", output_schema="CopyCandidateListOutput")
build_copy_spec_parser_metadata(state)
build_image_prompt_planner_metadata(state)
build_background_validation_metadata(state)
build_final_validation_metadata(state)
```

Each builder accepts partial or empty state and must not crash. Missing values are represented as `None`, `{}`, or `[]` depending on the field shape.

## Node Payload Coverage

### Validator

Carries:

```text
user_input
messages
current_brief
context
prompt_json
image_features
reference_style_profile
```

Output schema:

```text
ValidatorOutput
```

### Tone Binding

Carries:

```text
context
ad_format_spec
layout_spec
copy_generation_mode
copy_required
text_overlay_pending
selected_reference_template
reference_style_profile
product_preserve_spec
```

Output schema:

```text
ToneBindingOutput
```

### Copy Generation

Carries:

```text
context
ad_format_spec
layout_spec
tone_binding_output
plan_policy.max_candidates
copy_generation_mode
current_brief
messages
reference_style_profile
selected_reference_template
custom_copy_input
```

Constraints also surface:

```text
forbidden_claims
channel_copy_rules
copy_constraints
preserve_custom_input
```

`build_copy_generation_metadata()` accepts `node_name` and `output_schema` arguments so copy candidate, auto-pilot, and custom validation paths can keep their metadata contract aligned with the actual structured output schema.

### CopySpec Parser

Carries:

```text
marketing_copy
copy_candidates
selected_copy_id
custom_copy_input
copy_generation_mode
copy_required
text_overlay_pending
context
ad_format_spec
layout_spec
tone_binding_output
```

Constraint:

```text
no_new_facts=true
```

### ImagePromptPlanner

Carries:

```text
context
ad_format_spec
layout_spec
copy_spec
text_style_spec
text_layout_spec
reserved_text_areas
reference_style_profile
product_preserve_spec
selected_reference_template
reference_template_selection
vision_pipeline_results
engine
render_profile
```

Constraints include:

```text
must_not_include_text=true
negative_prompt_required_terms=text, letters, numbers, Hangul, logo, watermark
reserved_text_areas
```

`reserved_text_areas` must prefer the current `text_layout_spec.reserved_text_areas`. Existing `image_prompt_spec.reserved_text_areas` is only a fallback because `ImagePromptPlanner` creates the next `ImagePromptSpec`.

### Background Validation

This is a VLM-ready metadata stub. It does not call OCR or VLM.

Carries:

```text
t2i_result.image_paths
t2i_request.metadata
image_prompt_spec
text_layout_spec.reserved_text_areas
ad_format_spec
copy_generation_mode
copy_required
text_overlay_pending
reference_style_profile
product_preserve_spec
selected_reference_template
validation_questions
```

### Final Validation

This is a VLM-ready metadata stub. It does not call OCR or VLM.

Carries:

```text
final_image_path
render_result
copy_spec
marketing_copy
text_layout_spec
text_style_spec
ad_format_spec
background_validation_report
safe_area_report
readability_report
tone_binding_output.forbidden_claims
copy_generation_mode
validation_questions
```

## Explicit Non-Goals

This v1 work does not:

```text
call real LLM providers
call real VLM/OCR providers
change prompts for quality
change copy generation behavior
change image generation behavior
change graph routing
change fallback behavior
implement RevisionIntentClassifier
```

## Test Contract

`orchestrator/tests/test_llm_metadata_contracts.py` verifies:

```text
trace includes job_id, thread_id, revision, node_name
render_text_in_image=false is always present
do_not_invent includes phone, address, price, discount, event_period
builders tolerate empty state
builders return JSON-serializable dicts
hidden reasoning, secrets, and raw image bytes are not stored
OpenAIAdapter and MockLLMAdapter direct metadata paths use the same sanitizer
usage token accounting is preserved while secret-bearing token fields are removed
ImagePromptPlanner metadata prefers current TextLayoutSpec reserved areas over stale ImagePromptSpec values
copy generation metadata can use node-specific output schema names
future VLM metadata carries image paths, reserved areas, final path, and expected constraints
```
