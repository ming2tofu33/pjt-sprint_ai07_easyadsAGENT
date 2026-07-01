# LLM Model Policy

## Purpose

This policy separates model selection from LangGraph node logic before real LLM providers are connected.

- Nodes must not hard-code model names.
- `PlanPolicy` controls cost, quality, latency, and vision availability by user plan.
- `ModelRouter` chooses a model class for an LLM-capable node.
- `LLMAdapter` owns provider invocation.
- Deterministic nodes remain deterministic.

## UserPlan Policy

### free

- Uses local or mock model classes only.
- Allows zero API calls per job.
- Optimizes for fast, no-cost responses.
- Blocks `api_nano`, `api_mini`, `api_full`, and `api_vision`.

### economic

- Uses local models plus limited `api_nano` and `api_mini`.
- Allows API use only for important or low-confidence nodes.
- Prioritizes cost control.
- Blocks `api_full` and `api_vision` by default.

### premium

- Allows `api_nano`, `api_mini`, `api_full`, and `api_vision`.
- Prioritizes quality.
- Enables future VLM quality gates.

### internal_benchmark

- Internal experiment plan.
- Allows every model class.
- Must remain separate from production deployment policy.
- This repository stage still performs no real external calls.

## LLM-Capable Nodes

These nodes may later use LLM structured output:

- `validator`
- `copy_mode_inference`
- `tone_binding`
- `copy_candidate_generation`
- `auto_pilot_copywriting`
- `custom_copy_validation`
- `copy_spec_parser`
- `image_prompt_planner`
- `background_validation`
- `final_validation`
- `revision_intent_classifier`

## Deterministic Nodes

These nodes must remain deterministic and must not call LLMs:

- `options`
- `state_update`
- `format_planner`
- `text_layout_planner`
- `text_style_binder`
- `prompt_renderer`
- `t2i_request_builder`
- `copy_presence_router`
- `text_renderer`
- `readability_gate`
- `result_node`
- `safe_area_gate`

## Structured Output Rule

- LLM nodes should use Pydantic structured output whenever possible.
- `openai` and OpenAI-compatible adapters must request `json_schema` with `strict=true` for Pydantic schemas.
- Pydantic structured output must be validated immediately with `model_validate_json` or an equivalent strict validator.
- Direct `json.loads` parsing is a schema-less JSON object fallback only.
- Output schemas should come from `llm_marketing.py`, `text_layout.py`, or `llm_model_policy.py`.
- Raw chain-of-thought must not be stored.
- User-readable summaries may be stored as `reasoning_summary` or metadata.

## Adapter Instruction Boundary

- Trusted system instructions and untrusted user prompts must not be concatenated into one prompt string.
- Responses API calls use `instructions=` for trusted instructions and `input=` for user content.
- Chat Completions-compatible calls use separate `system` and `user` messages.
- `system_instruction` and `instructions` metadata keys are call controls and must not be copied into result metadata.
- OpenAI-compatible providers that reject strict JSON schema should fail the adapter call and trigger deterministic fallback rather than silently relaxing validation.

## Current 6th Milestone Scope

Implemented:

- `llm_model_policy.py` schema.
- Default `PlanPolicy`.
- `ModelRouter`.
- `BaseLLMAdapter`.
- `MockLLMAdapter`.
- Adapter registry with safe mock fallback.
- `MarketingState` tracking fields for `user_plan`, `plan_policy`, `model_selections`, and `llm_call_results`.

## 7th-A Milestone Scope

Implemented:

- `OpenAIAdapter` skeleton.
- API call guard with `LLM_ENABLE_API_CALL=false` as the default.
- Adapter registry strict/fallback policy.
- Guarded structured node runner.
- Optional adapter path for selected nodes:
  - `copy_mode_inference`
  - `copy_candidate_generation`
  - `auto_pilot_copywriting`
  - `image_prompt_planner`
- Deterministic fallback remains the default behavior.

## Provider Fallback Policy

- `mock` is the safe provider and always resolves to `MockLLMAdapter`.
- `openai` resolves to `OpenAIAdapter`.
- `openai_compatible` resolves to `OpenAICompatibleLLMAdapter` for hosted OpenAI-compatible endpoints.
- `local_openai_compat` wraps `OpenAICompatibleLLMAdapter` for local/self-hosted OpenAI-compatible endpoints.
- `local_gemma`, `local_qwen`, and `vision_api` are not implemented in this milestone.
- Strict mode raises a clear provider-not-implemented error for unavailable providers.
- Mock fallback is allowed only when the caller explicitly opts into `allow_mock_fallback`.
- Silent provider downgrade is not allowed in production-facing paths.

## API Call Guard

- `LLM_ENABLE_API_CALL=false` by default.
- `free` plan blocks all API calls even if the environment flag is enabled.
- `PlanPolicy.max_api_calls_per_job` limits external calls per job.
- Missing API key, missing model name, SDK import errors, API errors, and structured output parse errors return `LLMCallResult(success=false)` and trigger deterministic fallback.
- API keys are never written to state, logs, docs, or test output.

## Selected Node Connection State

- `copy_mode_inference`: guarded adapter path added with heuristic fallback.
- `copy_candidate_generation`: guarded adapter path added with rule-based candidate fallback.
- `auto_pilot_copywriting`: guarded adapter path added with rule-based copywriting fallback.
- `image_prompt_planner`: guarded adapter path added with deterministic TLFP prompt fallback.
- Safety-critical fields such as `must_not_include_text`, `reserved_text_areas`, and `render_text_in_image=false` are enforced after any adapter output.

Not implemented:

- Full production OpenAI adapter behavior.
- Real Local Gemma adapter.
- Real Local Qwen adapter.
- Real Vision adapter.
- API key usage.
- Real LLM calls in default tests.
- VLM, OCR, streaming, semantic routing, Qdrant, or DB-backed policy.

## Next Milestone

The next model-integration milestone should add:

- OpenAI adapter skeleton.
- Provider cost guard.
- A narrow structured-output connection for selected LLM-capable nodes.
- Fallback strategy using `ModelRouter` and `LLMAdapter`.
