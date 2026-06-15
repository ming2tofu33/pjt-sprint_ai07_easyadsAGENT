"""Consolidated llm services tests.

Merged from:
- orchestrator/tests/test_llm_adapters.py
- orchestrator/tests/test_llm_adapters_mock.py
- orchestrator/tests/test_llm_marketing_schema.py
- orchestrator/tests/test_llm_metadata_contracts.py
- orchestrator/tests/test_llm_model_policy_schema.py
- orchestrator/tests/test_llm_node_fallbacks.py
- orchestrator/tests/test_llm_node_runner.py
- orchestrator/tests/test_llm_router_policy.py
- orchestrator/tests/test_llm_settings.py
- orchestrator/tests/test_llm_usage_tracking.py
"""



# ===== from test_llm_adapters.py =====
import sys
import types

from orchestrator.app.llm.adapters.mock import MockLLMAdapter
from orchestrator.app.llm.adapters.local_openai_compat import LocalOpenAICompatAdapter
from orchestrator.app.llm.adapters.openai_compatible import OpenAICompatibleLLMAdapter
from orchestrator.app.llm.settings import LLMSettings
from orchestrator.app.schemas.llm_model_policy import ModelSelection


def _selection(provider: str = "openai_compatible", model_class: str = "api_mini") -> ModelSelection:
    return ModelSelection(
        node_name="copy_candidate_generation",
        user_plan="premium",
        selected_model_class=model_class,
        provider=provider,
        structured_output=True,
        reason="test selection",
    )


def test_mock_llm_adapter_returns_deterministic_result():
    result = MockLLMAdapter().invoke_text("hello", _selection(provider="mock", model_class="mock"))

    assert result.success is True
    assert result.output == "mock text response"
    assert result.metadata["mock"] is True


def test_openai_compatible_adapter_does_not_call_when_disabled(monkeypatch):
    monkeypatch.setitem(sys.modules, "openai", None)

    result = OpenAICompatibleLLMAdapter(LLMSettings(enable_api_call=False, openai_api_key="set", llm_model="model")).invoke_text(
        "hello",
        _selection(),
    )

    assert result.success is False
    assert result.error == "llm_calls_disabled"


def test_openai_compatible_adapter_credentials_missing_when_enabled_without_key():
    result = OpenAICompatibleLLMAdapter(LLMSettings(enable_api_call=True, openai_api_key=None, llm_model="model")).invoke_text(
        "hello",
        _selection(),
    )

    assert result.success is False
    assert result.error == "llm_credentials_missing"


def test_openai_compatible_adapter_dependency_unavailable(monkeypatch):
    monkeypatch.setitem(sys.modules, "openai", None)

    result = OpenAICompatibleLLMAdapter(LLMSettings(enable_api_call=True, openai_api_key="set", llm_model="model")).invoke_text(
        "hello",
        _selection(),
    )

    assert result.success is False
    assert result.error == "llm_dependency_unavailable"


def test_openai_compatible_adapter_result_does_not_include_api_key():
    result = OpenAICompatibleLLMAdapter(LLMSettings(enable_api_call=False, openai_api_key="sk-secret", llm_model="model")).invoke_text(
        "hello",
        _selection(),
        metadata={"api_key": "sk-secret", "safe": True},
    )

    dumped = result.model_dump(mode="json")
    assert "sk-secret" not in str(dumped)
    assert dumped["metadata"]["safe"] is True


def test_local_openai_compat_adapter_disabled_guard():
    result = LocalOpenAICompatAdapter(LLMSettings(enable_api_call=False, local_llm_base_url="http://localhost:11434/v1")).invoke_text(
        "hello",
        _selection(provider="local_openai_compat", model_class="local_quality"),
    )

    assert result.success is False
    assert result.error == "llm_calls_disabled"
    assert result.metadata["provider"] == "local_openai_compat"
    assert result.metadata["direct_model_load"] is False


def test_local_openai_compat_adapter_requires_base_url():
    result = LocalOpenAICompatAdapter(LLMSettings(enable_api_call=True, local_llm_base_url=None, local_llm_model="gemma4-e4b")).invoke_text(
        "hello",
        _selection(provider="local_openai_compat", model_class="local_quality"),
    )

    assert result.success is False
    assert result.error == "local_llm_base_url_missing"


def test_local_openai_compat_adapter_dependency_unavailable(monkeypatch):
    monkeypatch.setitem(sys.modules, "openai", None)

    result = LocalOpenAICompatAdapter(
        LLMSettings(enable_api_call=True, local_llm_base_url="http://localhost:11434/v1", local_llm_model="gemma4-e4b")
    ).invoke_text(
        "hello",
        _selection(provider="local_openai_compat", model_class="local_quality"),
    )

    assert result.success is False
    assert result.error == "llm_dependency_unavailable"
    assert "local-dev" not in str(result.model_dump(mode="json"))


def test_local_openai_compat_adapter_uses_chat_completions(monkeypatch):
    captured = {}
    openai_module = types.ModuleType("openai")

    class FakeMessage:
        content = "local smoke ok"

    class FakeChoice:
        message = FakeMessage()

    class FakeChatCompletions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return types.SimpleNamespace(choices=[FakeChoice()])

    class FakeOpenAI:
        def __init__(self, **kwargs):
            captured["client_kwargs"] = kwargs
            self.chat = types.SimpleNamespace(completions=FakeChatCompletions())

    openai_module.OpenAI = FakeOpenAI
    monkeypatch.setitem(sys.modules, "openai", openai_module)

    result = LocalOpenAICompatAdapter(
        LLMSettings(
            enable_api_call=True,
            local_llm_base_url="http://localhost:11434/v1",
            local_llm_api_key="local-dev",
            local_llm_model="gemma4-e4b",
            local_llm_api_style="chat_completions",
        )
    ).invoke_text(
        "hello",
        _selection(provider="local_openai_compat", model_class="local_quality"),
    )

    assert result.success is True
    assert result.output == "local smoke ok"
    assert captured["model"] == "gemma4-e4b"
    assert captured["messages"] == [{"role": "user", "content": "hello"}]
    assert captured["client_kwargs"]["base_url"] == "http://localhost:11434/v1"
    assert "local-dev" not in str(result.model_dump(mode="json"))


# ===== from test_llm_adapters_mock.py =====
from orchestrator.app.llm.adapters.mock import MockLLMAdapter
from orchestrator.app.llm.adapters.openai import OpenAIAdapter
from orchestrator.app.llm.adapters.registry import ProviderNotImplementedError, get_llm_adapter, get_llm_adapter_safe
from orchestrator.app.llm.model_router import choose_model
from orchestrator.app.llm.settings import LLMSettings
from orchestrator.app.schemas.llm_model_policy import ModelSelection


def _selection__test_llm_adapters_mock() -> ModelSelection:
    return choose_model("validator", "free")


def test_mock_adapter_invoke_text():
    result = MockLLMAdapter().invoke_text(
        "hello",
        _selection__test_llm_adapters_mock(),
        metadata={
            "prompt": "secret",
            "hf_token": "secret-token",
            "raw_image_bytes": b"secret-bytes",
            "chain_of_thought": "private reasoning",
            "token_usage": {"prompt_tokens": 1},
        },
    )

    assert result.success is True
    assert result.output == "mock text response"
    assert result.cost_estimate == 0.0
    assert result.metadata["mock"] is True
    assert result.metadata["token_usage"]["prompt_tokens"] == 1
    assert "secret" not in str(result.metadata)
    assert "chain_of_thought" not in result.metadata


def test_mock_adapter_invoke_structured():
    result = MockLLMAdapter().invoke_structured(ModelSelection, "select", _selection__test_llm_adapters_mock())

    assert result.success is True
    assert result.model_selection.node_name == "validator"
    assert result.output["mock"] is True


def test_mock_adapter_invoke_vision():
    result = MockLLMAdapter().invoke_vision(dict, "image.png", "inspect", _selection__test_llm_adapters_mock())

    assert result.success is True
    assert result.output["image_path"] == "image.png"
    assert result.metadata["vision"] is True


def test_adapter_registry_returns_safe_mock_fallback():
    assert isinstance(get_llm_adapter("mock"), MockLLMAdapter)
    assert isinstance(get_llm_adapter("openai"), OpenAIAdapter)
    try:
        get_llm_adapter("local_gemma")
    except ProviderNotImplementedError:
        pass
    else:
        raise AssertionError("local_gemma should be explicit not implemented in strict mode")
    assert isinstance(get_llm_adapter("local_gemma", allow_mock_fallback=True), MockLLMAdapter)
    assert isinstance(get_llm_adapter_safe("vision_api", LLMSettings(provider_strict_mode=True)), MockLLMAdapter)


# ===== from test_llm_marketing_schema.py =====
from typing import get_args

import pytest
from pydantic import ValidationError

from orchestrator.app.schemas import llm_marketing as schema


def _is_snake_case(value: str) -> bool:
    return value == value.lower() and "-" not in value and " " not in value


def test_literal_values_are_snake_case():
    literal_types = [
        schema.EntryMode,
        schema.GenerationRoute,
        schema.GenerationEngine,
        schema.RenderProfile,
        schema.JobStatus,
        schema.CopySpace,
        schema.MissingField,
    ]

    for literal_type in literal_types:
        for value in get_args(literal_type):
            assert _is_snake_case(value), value


def test_required_llm_schema_classes_exist():
    expected = [
        "ConversationMessage",
        "MarketingContext",
        "ProgressState",
        "ValidatorOutput",
        "OptionItem",
        "OptionQuestion",
        "UserSelectionRequest",
        "AdFormatSpec",
        "Zone",
        "TextZone",
        "LayoutSpec",
        "MarketingCopy",
        "CopywritingOutput",
        "ImagePrompt",
        "UserReadableImageGuide",
        "PromptOptimizationOutput",
        "PromptRenderOutput",
        "RefactoringOutput",
        "ImageInput",
        "ImageFeatures",
        "ReferenceInput",
        "ReferenceStyleSpec",
        "GeneratedImageCandidate",
        "TextOverlayConfig",
        "BackgroundValidationReport",
        "FinalValidationReport",
        "ValidationReport",
        "JobStatusResponse",
        "ArtifactRef",
        "ErrorInfo",
    ]

    for name in expected:
        assert hasattr(schema, name), name


def test_marketing_context_fields_are_snake_case():
    for field_name in schema.MarketingContext.model_fields:
        assert _is_snake_case(field_name), field_name


def test_llm_schema_uses_existing_t2i_contracts():
    from orchestrator.app.t2i.schemas import T2IRequest, T2IResult

    assert schema.T2IRequest is T2IRequest
    assert schema.T2IResult is T2IResult


def test_progress_state_supports_dynamic_question_steps():
    progress = schema.ProgressState(
        current_step=1,
        total_steps=4,
        current_label="업종 선택",
        remaining_fields=["business_type", "ad_format"],
        can_skip_question_screen=False,
    )

    assert progress.current_step == 1
    assert progress.remaining_fields == ["business_type", "ad_format"]


def test_image_prompt_requires_six_core_fields():
    with pytest.raises(ValidationError):
        schema.ImagePrompt(subject="삼겹살")

    prompt = schema.ImagePrompt(
        subject="삼겹살",
        style="commercial food photography",
        lighting="warm amber lighting",
        composition="copy space at bottom",
        copy_space="bottom",
        negative_prompt="text, watermark, logo",
    )
    assert prompt.negative_prompt == "text, watermark, logo"


def test_prompt_render_output_uses_positive_prompt_and_render_profile():
    output = schema.PromptRenderOutput(
        engine="sd35_large",
        positive_prompt="text-free bbq background",
        negative_prompt="text, logo",
        render_profile="balanced",
        render_notes=["separate positive and negative prompts"],
        width=1024,
        height=1024,
    )

    assert output.positive_prompt.startswith("text-free")
    assert output.render_profile == "balanced"


def test_ad_format_spec_rejects_unknown_branch_values():
    with pytest.raises(ValidationError):
        schema.AdFormatSpec(
            ad_format="random_format",
            platform="instagram",
            aspect_ratio="1:1",
            width=1080,
            height=1080,
            output_strategy="generate_text_free_background_then_overlay",
        )

    with pytest.raises(ValidationError):
        schema.AdFormatSpec(
            ad_format="instagram_feed",
            platform="unknown_platform",
            aspect_ratio="1:1",
            width=1080,
            height=1080,
            output_strategy="generate_text_free_background_then_overlay",
        )

    with pytest.raises(ValidationError):
        schema.AdFormatSpec(
            ad_format="instagram_feed",
            platform="instagram",
            aspect_ratio="3:2",
            width=1080,
            height=1080,
            output_strategy="generate_text_free_background_then_overlay",
        )


# ===== from test_llm_metadata_contracts.py =====
import json

from orchestrator.app.llm.metadata_builders import (
    build_background_validation_metadata,
    build_common_constraints_metadata,
    build_common_trace_metadata,
    build_copy_generation_metadata,
    build_copy_spec_parser_metadata,
    build_final_validation_metadata,
    build_image_prompt_planner_metadata,
    build_tone_binding_metadata,
    build_validator_metadata,
)
from orchestrator.app.llm.metadata_contracts import sanitize_metadata
from orchestrator.app.llm.node_runner import safe_metadata


def _sample_state():
    return {
        "schema_version": "llm_marketing_v1",
        "job_id": "job-1",
        "thread_id": "thread-1",
        "revision": 2,
        "context": {"business_type": "cafe", "item_or_service": "latte"},
        "ad_format_spec": {"ad_format": "instagram_feed", "width": 1080, "height": 1080},
        "layout_spec": {"layout_type": "single_panel", "copy_space": "bottom"},
        "tone_binding_output": {
            "forbidden_claims": ["no phone"],
            "channel_copy_rules": ["short headline"],
            "copy_constraints": ["preserve facts"],
        },
        "plan_policy": {"max_candidates": 3},
        "copy_generation_mode": "suggest_candidates",
        "copy_required": True,
        "text_overlay_pending": True,
        "marketing_copy": {"headline": "Fresh latte"},
        "copy_spec": {"items": [{"role": "headline", "text": "Fresh latte"}]},
        "text_layout_spec": {
            "reserved_text_areas": [{"x": 0.05, "y": 0.1, "w": 0.9, "h": 0.2}],
        },
        "text_style_spec": {"profile": "clean"},
        "image_prompt_spec": {
            "reserved_text_areas": [{"x": 0.05, "y": 0.1, "w": 0.9, "h": 0.2}],
        },
        "t2i_request": {
            "metadata": {
                "render_text_in_image": False,
                "reserved_text_areas": [{"x": 0.05, "y": 0.1, "w": 0.9, "h": 0.2}],
            },
        },
        "t2i_result": {"image_paths": ["data/outputs/job-1/mock.png"]},
        "final_image_path": "data/outputs/job-1/final.png",
        "render_result": {"final_image_path": "data/outputs/job-1/final.png"},
        "background_validation_report": {"overall_pass": True},
        "safe_area_report": {"overall_pass": True},
        "readability_report": {"overall_pass": True},
    }


def _walk_keys(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from _walk_keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_keys(item)


def test_common_trace_includes_job_thread_and_node():
    trace = build_common_trace_metadata(_sample_state(), "tone_binding")

    assert trace["schema_version"] == "llm_marketing_v1"
    assert trace["job_id"] == "job-1"
    assert trace["thread_id"] == "thread-1"
    assert trace["revision"] == 2
    assert trace["node_name"] == "tone_binding"


def test_common_constraints_keep_text_free_policy_and_do_not_invent_list():
    constraints = build_common_constraints_metadata(_sample_state())

    assert constraints["render_text_in_image"] is False
    assert constraints["must_not_include_text"] is True
    assert {"phone", "address", "price", "discount", "event_period"} <= set(constraints["do_not_invent"])


def test_builders_return_json_serializable_payloads_when_state_is_empty():
    builders = [
        build_validator_metadata,
        build_tone_binding_metadata,
        build_copy_generation_metadata,
        build_copy_spec_parser_metadata,
        build_image_prompt_planner_metadata,
        build_background_validation_metadata,
        build_final_validation_metadata,
    ]

    for builder in builders:
        payload = builder({})
        assert set(payload) == {"trace", "task", "available_state", "constraints", "output_rules"}
        json.dumps(payload)


def test_payloads_do_not_store_hidden_reasoning_secrets_or_raw_image_bytes():
    state = {
        **_sample_state(),
        "current_brief": {
            "chain_of_thought": "private reasoning",
            "raw_reasoning": "private raw reasoning",
            "reasoning_summary": "short user-safe summary",
            "openai_api_key": "secret-key",
            "raw_image_bytes": b"not allowed",
        },
    }

    payload = build_validator_metadata(state)
    payload_text = json.dumps(payload)

    assert "private reasoning" not in payload_text
    assert "private raw reasoning" not in payload_text
    assert "secret-key" not in payload_text
    assert "not allowed" not in payload_text
    assert payload["available_state"]["current_brief"]["reasoning_summary"] == "short user-safe summary"
    assert "no_chain_of_thought" in payload["output_rules"]
    assert "chain_of_thought" not in set(_walk_keys(payload["available_state"]))


def test_node_runner_safe_metadata_uses_shared_sanitizer():
    metadata = safe_metadata(
        {
            "prompt": "full prompt should not be stored",
            "openai_api_key": "secret-key",
            "image_bytes": b"raw",
            "reasoning_summary": "ok",
        }
    )

    assert "prompt" not in metadata
    assert "openai_api_key" not in metadata
    assert "image_bytes" not in metadata
    assert metadata["reasoning_summary"] == "ok"


def test_sanitizer_preserves_usage_tokens_but_drops_secret_tokens():
    metadata = sanitize_metadata(
        {
            "token_usage": {"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14},
            "hf_token": "secret-token",
            "authorization": "Bearer secret",
        }
    )

    assert metadata["token_usage"]["prompt_tokens"] == 10
    assert metadata["token_usage"]["completion_tokens"] == 4
    assert metadata["token_usage"]["total_tokens"] == 14
    assert "hf_token" not in metadata
    assert "authorization" not in metadata


def test_sanitizer_redacts_unknown_objects_without_using_str_value():
    class SecretishObject:
        def __str__(self):
            return "secret-from-str"

    metadata = sanitize_metadata({"custom_object": SecretishObject()})

    assert metadata["custom_object"] == "[unsupported_metadata_value:SecretishObject]"
    assert "secret-from-str" not in json.dumps(metadata)


def test_image_prompt_planner_metadata_prefers_current_text_layout_reserved_areas():
    state = {
        **_sample_state(),
        "text_layout_spec": {
            "reserved_text_areas": [{"x": 0.1, "y": 0.2, "w": 0.7, "h": 0.2}],
        },
        "image_prompt_spec": {
            "reserved_text_areas": [{"x": 0.6, "y": 0.6, "w": 0.2, "h": 0.2}],
        },
    }

    payload = build_image_prompt_planner_metadata(state)

    assert payload["available_state"]["reserved_text_areas"] == [{"x": 0.1, "y": 0.2, "w": 0.7, "h": 0.2}]
    assert payload["constraints"]["reserved_text_areas"] == [{"x": 0.1, "y": 0.2, "w": 0.7, "h": 0.2}]


def test_copy_generation_metadata_accepts_node_specific_output_schema():
    payload = build_copy_generation_metadata(
        _sample_state(),
        node_name="auto_pilot_copywriting",
        output_schema="CopywritingOutput",
    )

    assert payload["trace"]["node_name"] == "auto_pilot_copywriting"
    assert payload["task"]["output_schema"] == "CopywritingOutput"


def test_image_and_validation_builders_include_future_vlm_contract_inputs():
    state = _sample_state()

    image_payload = build_image_prompt_planner_metadata(state)
    background_payload = build_background_validation_metadata(state)
    final_payload = build_final_validation_metadata(state)

    assert image_payload["available_state"]["text_layout_spec"]
    assert image_payload["constraints"]["reserved_text_areas"]
    assert "Hangul" in image_payload["constraints"]["negative_prompt_required_terms"]
    assert background_payload["available_state"]["image_paths"] == ["data/outputs/job-1/mock.png"]
    assert background_payload["available_state"]["reserved_text_areas"] == [{"x": 0.05, "y": 0.1, "w": 0.9, "h": 0.2}]
    assert background_payload["constraints"]["ocr_or_vlm_called"] is False
    assert background_payload["constraints"]["vlm_call_allowed"] is False
    assert final_payload["available_state"]["final_image_path"] == "data/outputs/job-1/final.png"
    assert final_payload["available_state"]["expected_copy"] == [{"role": "headline", "text": "Fresh latte"}]
    assert final_payload["available_state"]["forbidden_claims"] == ["no phone"]
    assert final_payload["constraints"]["ocr_or_vlm_called"] is False
    assert final_payload["constraints"]["vlm_call_allowed"] is False


# ===== from test_llm_model_policy_schema.py =====
from typing import get_args

import pytest
from pydantic import ValidationError

from orchestrator.app.schemas.llm_model_policy import (
    LLMCallResult,
    ModelClass,
    ModelSelection,
    NodeModelPolicy,
    PlanPolicy,
    UserPlan,
)


def test_model_policy_literals_include_expected_values():
    assert set(get_args(UserPlan)) == {"free", "economic", "premium", "internal_benchmark"}
    assert set(get_args(ModelClass)) == {"local_fast", "local_quality", "api_nano", "api_mini", "api_full", "api_vision", "mock"}


def test_default_policy_contains_compliance_rewrite_node():
    from orchestrator.app.llm.plan_policy import build_default_plan_policy

    policy = build_default_plan_policy("premium")

    assert "compliance_rewrite" in policy.node_policies
    assert policy.node_policies["compliance_rewrite"].default_model_class == "api_mini"


def test_node_model_policy_validates_allowed_defaults():
    policy = NodeModelPolicy(node_name="validator", default_model_class="local_fast", allowed_model_classes=["local_fast", "mock"])
    assert policy.fallback_model_class == "mock"

    with pytest.raises(ValidationError):
        NodeModelPolicy(node_name="validator", default_model_class="api_full", allowed_model_classes=["local_fast"])


def test_plan_policy_free_blocks_api_classes():
    with pytest.raises(ValidationError):
        PlanPolicy(
            user_plan="free",
            allowed_model_classes=["local_fast", "api_nano", "mock"],
            max_api_calls_per_job=0,
            max_candidates=1,
            vision_gate_enabled=False,
            allow_api_fallback=False,
            node_policies={},
        )


def test_model_selection_and_call_result_validate():
    selection = ModelSelection(
        node_name="validator",
        user_plan="free",
        selected_model_class="mock",
        provider="mock",
        structured_output=True,
        reason="free plan uses mock",
        confidence=0.5,
    )
    result = LLMCallResult(success=True, node_name="validator", model_selection=selection, output={"ok": True})
    assert result.success is True

    with pytest.raises(ValidationError):
        ModelSelection(
            node_name="validator",
            user_plan="free",
            selected_model_class="mock",
            provider="mock",
            structured_output=True,
            reason="",
        )
    with pytest.raises(ValidationError):
        ModelSelection(
            node_name="validator",
            user_plan="free",
            selected_model_class="mock",
            provider="mock",
            structured_output=True,
            reason="bad confidence",
            confidence=2.0,
        )


# ===== from test_llm_node_fallbacks.py =====
from orchestrator.app.graph.nodes import resolve_copy_generation_mode
from orchestrator.app.graph.state import create_initial_marketing_state
from orchestrator.app.llm.nodes.auto_pilot_copywriting import auto_pilot_copywriting_node
from orchestrator.app.llm.nodes.copy_candidates import copy_candidate_generation_node
from orchestrator.app.llm.nodes.format_planner import format_planner_node
from orchestrator.app.llm.nodes.image_prompt_planner import image_prompt_planner_node
from orchestrator.app.llm.nodes.text_layout_planner import text_layout_planner_node
from orchestrator.app.llm.nodes.text_style_binder import text_style_binder_node
from orchestrator.app.schemas.llm_marketing import CopyCandidate, CopyCandidateListOutput, CopyModeInferenceOutput, CopywritingOutput, InitialMarketingRequest, MarketingCopy
from orchestrator.app.schemas.text_layout import ImagePromptSpec


def _state(user_plan: str = "premium"):
    state = create_initial_marketing_state(
        InitialMarketingRequest(
            user_input="ready",
            user_plan=user_plan,
            copy_generation_mode="auto_pilot",
            context={
                "business_type": "restaurant",
                "item_or_service": "BBQ",
                "promotion_goal": "reservation_cta",
                "extra": {"ad_format": "instagram_feed"},
            },
        )
    )
    state.update(format_planner_node(state))
    state.update({"marketing_copy": MarketingCopy(headline="Hello BBQ", subcopy="Sub", cta="Book").model_dump()})
    state.update(text_style_binder_node(state))
    state.update({"copy_spec": {"items": [{"role": "headline", "text": "Hello BBQ"}], "copy_mode": "standard", "tone_profile": {}}})
    state.update(text_layout_planner_node(state))
    return state


def test_copy_mode_inference_disabled_falls_back_to_missing():
    state = create_initial_marketing_state(InitialMarketingRequest(user_input="ambiguous request", user_plan="premium"))
    mode, output = resolve_copy_generation_mode(state, "ambiguous request")

    assert mode is None
    assert output is None
    assert state["llm_call_results"]
    assert state["llm_call_results"][0]["error"] == "api_call_disabled"


def test_copy_mode_inference_adapter_output_can_be_used(monkeypatch):
    expected = CopyModeInferenceOutput(copy_generation_mode="no_copy", confidence=0.9, source="heuristic")
    monkeypatch.setattr("orchestrator.app.graph.nodes.run_structured_node", lambda *args, **kwargs: (expected, {"fallback_used": False}))
    state = create_initial_marketing_state(InitialMarketingRequest(user_input="ambiguous request", user_plan="premium"))

    mode, output = resolve_copy_generation_mode(state, "ambiguous request")

    assert mode == "no_copy"
    assert output.copy_generation_mode == "no_copy"


def test_copy_candidates_disabled_uses_rule_fallback():
    state = _state("premium")
    output = copy_candidate_generation_node(state)

    assert len(output["copy_candidates"]) == 3
    assert output["llm_call_results"][0]["error"] == "api_call_disabled"
    assert all("010-" not in candidate["headline"] for candidate in output["copy_candidates"])


def test_copy_candidates_adapter_success_is_used(monkeypatch):
    llm_output = CopyCandidateListOutput(
        candidates=[CopyCandidate(id="x", headline="LLM headline", subcopy="LLM sub", cta="Go")],
        recommended_candidate_id="x",
    )
    monkeypatch.setattr("orchestrator.app.llm.nodes.copy_candidates.run_structured_node", lambda *args, **kwargs: (llm_output, {"fallback_used": False}))
    output = copy_candidate_generation_node(_state("premium"))

    assert output["copy_candidates"][0]["headline"] == "LLM headline"


def test_auto_pilot_disabled_uses_rule_fallback():
    output = auto_pilot_copywriting_node(_state("premium"))

    assert output["marketing_copy"]["headline"]
    assert output["llm_call_results"][0]["error"] == "api_call_disabled"


def test_auto_pilot_adapter_success_is_used(monkeypatch):
    copy = MarketingCopy(headline="LLM copy", subcopy="LLM sub", cta="Act")
    llm_output = CopywritingOutput(marketing_copy=copy)
    monkeypatch.setattr("orchestrator.app.llm.nodes.auto_pilot_copywriting.run_structured_node", lambda *args, **kwargs: (llm_output, {"fallback_used": False}))
    output = auto_pilot_copywriting_node(_state("premium"))

    assert output["marketing_copy"]["headline"] == "LLM copy"


def test_image_prompt_planner_disabled_keeps_safety_fields():
    state = _state("premium")
    output = image_prompt_planner_node(state)

    spec = output["image_prompt_spec"]
    assert spec["must_not_include_text"] is True
    assert spec["reserved_text_areas"] == state["text_layout_spec"]["reserved_text_areas"]
    assert "hangul" in spec["negative_prompt_en"].lower()
    assert output["llm_call_results"] == []
    assert spec["metadata"]["prompt_critic"]["fallback_used"] is True


def test_image_prompt_planner_adapter_success_is_safety_corrected(monkeypatch):
    unsafe = ImagePromptSpec(
        scene_description="scene",
        product_subject="BBQ",
        color_palette=[],
        composition="composition",
        lighting="lighting",
        reserved_text_areas=[],
        must_not_include_text=False,
        positive_prompt_en="positive",
        negative_prompt_en="low quality",
        target_width=1,
        target_height=1,
        aspect_ratio="1:1",
    )
    monkeypatch.setattr("orchestrator.app.llm.nodes.image_prompt_planner.run_structured_node", lambda *args, **kwargs: (unsafe, {"fallback_used": False}))
    state = _state("premium")
    output = image_prompt_planner_node(state)

    spec = output["image_prompt_spec"]
    assert spec["must_not_include_text"] is True
    assert spec["reserved_text_areas"] == state["text_layout_spec"]["reserved_text_areas"]
    assert spec["target_width"] == state["ad_format_spec"]["width"]
    assert "watermark" in spec["negative_prompt_en"].lower()


# ===== from test_llm_node_runner.py =====
from orchestrator.app.llm.node_runner import run_structured_node
from orchestrator.app.llm.settings import LLMSettings
from orchestrator.app.schemas.llm_marketing import CopyModeInferenceOutput


def _state__test_llm_node_runner(plan: str = "premium"):
    from orchestrator.app.graph.state import create_initial_marketing_state
    from orchestrator.app.schemas.llm_marketing import InitialMarketingRequest

    return create_initial_marketing_state(InitialMarketingRequest(user_input="ready", user_plan=plan))


def test_node_runner_disabled_uses_fallback_and_tracks_result():
    state = _state__test_llm_node_runner("premium")
    output, metadata = run_structured_node(
        state,
        "copy_mode_inference",
        CopyModeInferenceOutput,
        "prompt should not be stored",
        fallback_fn=lambda: CopyModeInferenceOutput(copy_generation_mode="auto_pilot", confidence=0.7, source="heuristic"),
        settings=LLMSettings(enable_api_call=False),
    )

    assert output.copy_generation_mode == "auto_pilot"
    assert metadata["fallback_used"] is True
    assert state["model_selections"]
    assert state["llm_call_results"][0]["error"] == "api_call_disabled"
    assert "prompt should not be stored" not in str(state["llm_call_results"])


def test_node_runner_free_plan_uses_fallback():
    state = _state__test_llm_node_runner("free")
    output, metadata = run_structured_node(
        state,
        "copy_mode_inference",
        CopyModeInferenceOutput,
        "prompt",
        fallback_fn=lambda: None,
        settings=LLMSettings(enable_api_call=True),
    )

    assert output is None
    assert metadata["fallback_reason"] == "free_plan_deterministic_fallback"


def test_node_runner_invalid_structured_output_falls_back(monkeypatch):
    class BadAdapter:
        def invoke_structured(self, schema, prompt, model_selection, metadata=None):
            from orchestrator.app.schemas.llm_model_policy import LLMCallResult

            return LLMCallResult(success=True, node_name=model_selection.node_name, model_selection=model_selection, output={"bad": True})

    monkeypatch.setattr("orchestrator.app.llm.node_runner.get_llm_adapter_safe", lambda *args, **kwargs: BadAdapter())
    state = _state__test_llm_node_runner("premium")
    output, metadata = run_structured_node(
        state,
        "copy_mode_inference",
        CopyModeInferenceOutput,
        "prompt",
        fallback_fn=lambda: CopyModeInferenceOutput(copy_generation_mode="suggest_candidates", confidence=0.8, source="heuristic"),
        settings=LLMSettings(enable_api_call=True, openai_api_key="set", openai_text_model_mini="model"),
    )

    assert output.copy_generation_mode == "suggest_candidates"
    assert metadata["fallback_reason"] == "structured_output_validation_failed"


def test_node_runner_invalid_structured_output_records_single_llm_call_result(monkeypatch):
    class BadAdapter:
        def invoke_structured(self, schema, prompt, model_selection, metadata=None):
            from orchestrator.app.schemas.llm_model_policy import LLMCallResult

            return LLMCallResult(success=True, node_name=model_selection.node_name, model_selection=model_selection, output={"bad": True})

    monkeypatch.setattr("orchestrator.app.llm.node_runner.get_llm_adapter_safe", lambda *args, **kwargs: BadAdapter())
    state = _state__test_llm_node_runner("premium")

    output, metadata = run_structured_node(
        state,
        "copy_mode_inference",
        CopyModeInferenceOutput,
        "prompt",
        fallback_fn=lambda: CopyModeInferenceOutput(copy_generation_mode="suggest_candidates", confidence=0.8, source="heuristic"),
        settings=LLMSettings(enable_api_call=True, openai_api_key="set", openai_text_model_mini="model"),
    )

    assert output.copy_generation_mode == "suggest_candidates"
    assert metadata["fallback_reason"] == "structured_output_validation_failed"
    assert len(state["model_selections"]) == 1
    assert len(state["llm_call_results"]) == 1


def test_validate_output_rejects_non_mapping_with_clear_error():
    import pytest
    from pydantic import BaseModel

    from orchestrator.app.llm.node_runner import validate_output

    class _Out(BaseModel):
        value: int = 0

    with pytest.raises(ValueError, match="must be a mapping"):
        validate_output(_Out, ["not", "a", "mapping"])


def test_validate_output_accepts_none_and_mapping():
    from pydantic import BaseModel

    from orchestrator.app.llm.node_runner import validate_output

    class _Out(BaseModel):
        value: int = 0

    assert validate_output(_Out, None).value == 0
    assert validate_output(_Out, {"value": 3}).value == 3


# ===== from test_llm_router_policy.py =====
from orchestrator.app.llm.adapters.mock import MockLLMAdapter
from orchestrator.app.llm.adapters.local_openai_compat import LocalOpenAICompatAdapter
from orchestrator.app.llm.adapters.openai_compatible import OpenAICompatibleLLMAdapter
from orchestrator.app.llm.adapters.registry import ProviderNotImplementedError, get_llm_adapter
from orchestrator.app.llm.model_router import choose_model, provider_for_model_class
from orchestrator.app.schemas.llm_model_policy import ModelSelection


def test_mock_provider_resolves_to_mock_adapter():
    assert isinstance(get_llm_adapter("mock"), MockLLMAdapter)


def test_openai_compatible_provider_resolves_to_real_adapter_class():
    assert isinstance(get_llm_adapter("openai_compatible"), OpenAICompatibleLLMAdapter)


def test_local_openai_compat_provider_resolves_to_local_adapter():
    assert isinstance(get_llm_adapter("local_openai_compat"), LocalOpenAICompatAdapter)


def test_unknown_provider_falls_back_safely():
    assert isinstance(get_llm_adapter("unknown", strict=False, allow_mock_fallback=True), MockLLMAdapter)


def test_unknown_provider_strict_raises():
    try:
        get_llm_adapter("unknown", strict=True, allow_mock_fallback=False)
    except ProviderNotImplementedError:
        return
    raise AssertionError("expected ProviderNotImplementedError")


def test_legacy_provider_helper_maps_local_models_to_local_openai_compat():
    assert provider_for_model_class("local_fast") == "local_openai_compat"
    assert provider_for_model_class("local_quality") == "local_openai_compat"


def test_free_plan_does_not_select_external_llm_by_default():
    selection = choose_model("image_prompt_planner", "free", confidence=0.1, risk_level="high")

    assert selection.provider != "openai_compatible"
    assert selection.provider != "openai"
    assert not selection.selected_model_class.startswith("api_")


def test_free_plan_local_model_routes_to_local_openai_compat_when_configured(monkeypatch):
    monkeypatch.setenv("EASYADS_LOCAL_LLM_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("EASYADS_LOCAL_LLM_MODEL", "gemma4-e4b")

    selection = choose_model("copy_candidate_generation", "free")

    assert selection.selected_model_class == "local_quality"
    assert selection.provider == "local_openai_compat"
    assert selection.provider_profile == "local_gemma_e4b"
    assert selection.model_name == "gemma4-e4b"
    assert selection.metadata["direct_model_load"] is False


def test_free_plan_local_model_missing_endpoint_falls_back_to_mock(monkeypatch):
    monkeypatch.delenv("EASYADS_LOCAL_LLM_BASE_URL", raising=False)

    selection = choose_model("copy_candidate_generation", "free")

    assert selection.provider == "mock"
    assert selection.fallback_used is True
    assert selection.metadata["fallback_reason"] == "local_openai_compat_not_configured"


def test_economic_api_mini_routes_to_openai_provider(monkeypatch):
    monkeypatch.setenv("EASYADS_LLM_PROVIDER", "openai")

    selection = choose_model("copy_candidate_generation", "economic")

    assert selection.selected_model_class == "api_nano"
    assert selection.provider == "openai"


def test_model_selections_shape_is_preserved():
    selection = ModelSelection(
        node_name="copy_candidate_generation",
        user_plan="premium",
        selected_model_class="api_mini",
        provider="openai_compatible",
        structured_output=True,
        reason="shape preservation",
        metadata={"image_prompt_version": "v3"},
    )

    dumped = selection.model_dump(mode="json")

    assert dumped["node_name"] == "copy_candidate_generation"
    assert dumped["provider"] == "openai_compatible"
    assert dumped["metadata"]["image_prompt_version"] == "v3"


# ===== from test_llm_settings.py =====
from orchestrator.app.llm.settings import LLMSettings, count_api_calls, is_api_call_allowed, model_class_requires_api
from orchestrator.app.llm.model_router import choose_model
from orchestrator.app.schemas.llm_model_policy import ModelSelection


def test_llm_settings_defaults_do_not_enable_api(monkeypatch):
    monkeypatch.delenv("LLM_ENABLE_API_CALL", raising=False)
    monkeypatch.delenv("EASYADS_ENABLE_LLM_CALLS", raising=False)
    monkeypatch.delenv("EASYADS_LLM_PROVIDER", raising=False)
    settings = LLMSettings.from_env()

    assert settings.enable_api_call is False
    assert settings.default_provider == "mock"


def test_easyads_llm_settings_aliases(monkeypatch):
    monkeypatch.setenv("EASYADS_ENABLE_LLM_CALLS", "true")
    monkeypatch.setenv("EASYADS_LLM_PROVIDER", "openai_compatible")
    monkeypatch.setenv("EASYADS_LLM_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("LLM_OPENAI_TEXT_MODEL_MINI", "gpt-4o-mini")
    monkeypatch.setenv("LLM_OPENAI_TEXT_MODEL_NANO", "gpt-4o-mini")
    monkeypatch.setenv("LLM_OPENAI_TEXT_MODEL_FULL", "gpt-4o-mini")
    monkeypatch.setenv("LLM_OPENAI_VISION_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("EASYADS_LLM_BASE_URL", "https://api.example.test/v1")
    monkeypatch.setenv("EASYADS_LLM_API_STYLE", "responses")
    monkeypatch.setenv("EASYADS_LLM_TIMEOUT_SECONDS", "45")
    monkeypatch.setenv("EASYADS_LLM_MAX_RETRIES", "2")

    settings = LLMSettings.from_env()

    assert settings.enable_api_call is True
    assert settings.default_provider == "openai_compatible"
    assert settings.llm_model == "gpt-4o-mini"
    assert settings.openai_text_model_mini == "gpt-4o-mini"
    assert settings.llm_base_url == "https://api.example.test/v1"
    assert settings.llm_api_style == "responses"
    assert settings.request_timeout_seconds == 45
    assert settings.max_retries == 2


def test_llm_provider_unknown_falls_back_to_mock(monkeypatch):
    monkeypatch.setenv("EASYADS_LLM_PROVIDER", "unknown")

    settings = LLMSettings.from_env()

    assert settings.default_provider == "mock"


def test_local_llm_settings_are_loaded(monkeypatch):
    monkeypatch.setenv("EASYADS_LLM_PROVIDER", "local_openai_compat")
    monkeypatch.setenv("EASYADS_LOCAL_LLM_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("EASYADS_LOCAL_LLM_API_KEY", "local-dev")
    monkeypatch.setenv("EASYADS_LOCAL_LLM_MODEL", "gemma4-e4b")
    monkeypatch.setenv("EASYADS_LOCAL_LLM_API_STYLE", "chat_completions")
    monkeypatch.setenv("EASYADS_LOCAL_LLM_TIMEOUT_SECONDS", "60")

    settings = LLMSettings.from_env()

    assert settings.default_provider == "local_openai_compat"
    assert settings.local_llm_provider == "local_openai_compat"
    assert settings.local_llm_base_url == "http://localhost:11434/v1"
    assert settings.local_llm_api_key == "local-dev"
    assert settings.local_llm_model == "gemma4-e4b"
    assert settings.local_llm_api_style == "chat_completions"
    assert settings.local_llm_timeout_seconds == 60


def test_local_llm_model_defaults_to_gemma4_e4b(monkeypatch):
    monkeypatch.delenv("EASYADS_LOCAL_LLM_MODEL", raising=False)

    settings = LLMSettings.from_env()

    assert settings.local_llm_model == "gemma4-e4b"


def test_missing_api_key_does_not_crash_settings(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")

    settings = LLMSettings.from_env()

    assert settings.openai_api_key is None


def test_cost_guard_blocks_free_and_disabled_api():
    free_selection = ModelSelection(
        node_name="image_prompt_planner",
        user_plan="free",
        selected_model_class="api_nano",
        provider="openai",
        structured_output=True,
        reason="forced api test selection",
    )
    premium_selection = choose_model("image_prompt_planner", "premium")

    assert model_class_requires_api("api_mini") is True
    assert is_api_call_allowed({"plan_policy": {"max_api_calls_per_job": 10}}, free_selection, LLMSettings(enable_api_call=True))[0] is False
    allowed, reason = is_api_call_allowed({"plan_policy": {"max_api_calls_per_job": 10}}, premium_selection, LLMSettings(enable_api_call=False))
    assert allowed is False
    assert reason == "api_call_disabled"


def test_cost_guard_blocks_api_limit():
    selection = choose_model("image_prompt_planner", "premium")
    state = {
        "plan_policy": {"max_api_calls_per_job": 1},
        "llm_call_results": [{"success": True, "model_selection": {"selected_model_class": "api_full"}}],
    }

    assert count_api_calls(state) == 1
    allowed, reason = is_api_call_allowed(state, selection, LLMSettings(enable_api_call=True, openai_api_key="set"))
    assert allowed is False
    assert reason == "api_call_limit_exceeded"


# ===== from test_llm_usage_tracking.py =====
from types import SimpleNamespace

from orchestrator.app.llm import node_runner


def test_llm_usage_recorded_from_success_result(monkeypatch):
    calls = []
    selection = SimpleNamespace(
        provider="openai",
        model_name="gpt-4.1-mini",
        provider_profile="openai-mini",
        selected_model_class="api_fast",
        node_name="copywriter",
    )
    result = SimpleNamespace(
        success=True,
        token_usage={"input_tokens": 11, "output_tokens": 7, "total_tokens": 18},
        model_selection=selection,
        metadata={"provider_request_id": "req_123"},
    )
    state = {
        "workspace_id": "ws1",
        "thread_id": "thread1",
        "job_id": "job1",
        "usage_thread_db_id": "thread_uuid",
        "usage_job_db_id": "job_uuid",
        "user_id": "user1",
        "user_plan": "premium",
    }
    monkeypatch.setattr(node_runner.usage_service, "record_llm_usage", lambda **kwargs: calls.append(kwargs))

    node_runner.record_llm_usage_from_result(state, result)

    assert calls[0]["workspace_id"] == "ws1"
    assert calls[0]["provider"] == "openai"
    assert calls[0]["model_name"] == "gpt-4.1-mini"
    assert calls[0]["input_tokens"] == 11
    assert calls[0]["output_tokens"] == 7
    assert calls[0]["provider_request_id"] == "req_123"
    assert calls[0]["thread_id"] == "thread_uuid"
    assert calls[0]["job_id"] == "job_uuid"


def test_llm_usage_uses_internal_job_and_thread_uuid(monkeypatch):
    calls = []
    selection = SimpleNamespace(provider="openai", model_name="gpt", selected_model_class="api", node_name="copywriter")
    result = SimpleNamespace(success=True, token_usage={"input_tokens": 1, "output_tokens": 1}, model_selection=selection, metadata={})
    state = {"workspace_id": "ws1", "thread_id": "thread_public", "job_id": "job_public", "usage_thread_db_id": "thread_uuid", "usage_job_db_id": "job_uuid"}
    monkeypatch.setattr(node_runner.usage_service, "record_llm_usage", lambda **kwargs: calls.append(kwargs))

    node_runner.record_llm_usage_from_result(state, result)

    assert calls[0]["thread_id"] == "thread_uuid"
    assert calls[0]["job_id"] == "job_uuid"
    assert calls[0]["call_index"] == 0


def test_same_node_multiple_paid_calls_are_not_deduplicated(monkeypatch):
    calls = []
    selection = SimpleNamespace(provider="openai", model_name="gpt", selected_model_class="api", node_name="copywriter")
    result = SimpleNamespace(success=True, token_usage={"input_tokens": 1, "output_tokens": 1}, model_selection=selection, metadata={})
    state = {"workspace_id": "ws1", "usage_thread_db_id": "thread_uuid", "usage_job_db_id": "job_uuid", "llm_call_results": [{}]}
    monkeypatch.setattr(node_runner.usage_service, "record_llm_usage", lambda **kwargs: calls.append(kwargs))

    node_runner.record_llm_usage_from_result(state, result)

    assert calls[0]["call_index"] == 1


def test_llm_usage_skips_mock_provider(monkeypatch):
    calls = []
    selection = SimpleNamespace(provider="mock", model_name="mock", selected_model_class="mock", node_name="copywriter")
    result = SimpleNamespace(success=True, token_usage={"input_tokens": 1}, model_selection=selection, metadata={})

    monkeypatch.setattr(node_runner.usage_service, "record_llm_usage", lambda **kwargs: calls.append(kwargs))
    node_runner.record_llm_usage_from_result({"workspace_id": "ws1"}, result)

    assert calls == []
