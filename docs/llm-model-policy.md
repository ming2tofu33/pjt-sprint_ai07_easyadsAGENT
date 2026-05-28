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
- Direct JSON-string parsing is a fallback only.
- Output schemas should come from `llm_marketing.py`, `text_layout.py`, or `llm_model_policy.py`.
- Raw chain-of-thought must not be stored.
- User-readable summaries may be stored as `reasoning_summary` or metadata.

## Current 6th Milestone Scope

Implemented:

- `llm_model_policy.py` schema.
- Default `PlanPolicy`.
- `ModelRouter`.
- `BaseLLMAdapter`.
- `MockLLMAdapter`.
- Adapter registry with safe mock fallback.
- `MarketingState` tracking fields for `user_plan`, `plan_policy`, `model_selections`, and `llm_call_results`.

Not implemented:

- Real OpenAI adapter.
- Real Local Gemma adapter.
- Real Local Qwen adapter.
- Real Vision adapter.
- API key usage.
- Real LLM calls from graph nodes.

## Next Milestone

The next model-integration milestone should add:

- OpenAI adapter skeleton.
- Provider cost guard.
- A narrow structured-output connection for selected LLM-capable nodes.
- Fallback strategy using `ModelRouter` and `LLMAdapter`.
