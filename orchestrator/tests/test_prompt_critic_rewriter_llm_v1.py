import inspect

import pytest
from pydantic import ValidationError

from orchestrator.app.graph.state import create_initial_marketing_state
from orchestrator.app.llm.nodes.copy_spec_parser import copy_spec_parser_node
from orchestrator.app.llm.nodes.format_planner import format_planner_node
from orchestrator.app.llm.nodes.image_prompt_planner import image_prompt_planner_node
from orchestrator.app.llm.nodes.prompt_critic import critique_prompt_draft
from orchestrator.app.llm.nodes.prompt_renderer import prompt_renderer_node
from orchestrator.app.llm.nodes.result import result_node
from orchestrator.app.llm.nodes.t2i_generation import t2i_generation_node
from orchestrator.app.llm.nodes.t2i_request_builder import t2i_request_builder_node
from orchestrator.app.llm.nodes.text_layout_planner import text_layout_planner_node
from orchestrator.app.llm.nodes.text_renderer import text_renderer_node
from orchestrator.app.llm.nodes.text_style_binder import text_style_binder_node
from orchestrator.app.llm.prompt_rewrite_resolver import resolve_prompt_rewrite
from orchestrator.app.schemas.llm_marketing import InitialMarketingRequest, MarketingContext
from orchestrator.app.schemas.prompt_critic import PromptCriticIssue, PromptCriticOutput, PromptRewriteProposal


def _state(user_plan: str = "premium"):
    state = create_initial_marketing_state(
        InitialMarketingRequest(
            user_input="premium cafe strawberry latte ad background",
            user_plan=user_plan,
            context=MarketingContext(
                business_type="cafe",
                item_or_service="strawberry latte",
                promotion_goal="new_launch",
                extra={"ad_format": "instagram_feed"},
            ),
            copy_generation_mode="auto_pilot",
            selected_reference_template_id="seed_cafe_strawberry_feed_001",
        )
    )
    state.update(format_planner_node(state))
    state["marketing_copy"] = {"headline": "New latte", "subcopy": "Fresh mood", "cta": "Visit", "metadata": {}}
    state.update(copy_spec_parser_node(state))
    state.update(text_style_binder_node(state))
    state.update(text_layout_planner_node(state))
    state["selected_reference_template"] = {"template_id": "seed_cafe_strawberry_feed_001", "title": "Cafe Strawberry Feed"}
    state["reference_template_selection"] = {"style_profile_hint": {"color_palette": ["red", "cream"]}}
    return state


def _critic_output(**kwargs):
    defaults = {
        "quality_score": 0.82,
        "confidence": 0.9,
        "issues": [PromptCriticIssue(code="visual_clutter", severity="warning", message="Reduce clutter")],
        "rewrite": PromptRewriteProposal(add_fragments=["soft commercial lighting with uncluttered negative space"]),
        "preserve_no_text_policy": True,
        "preserve_reference_alignment": True,
        "preserve_business_context": True,
    }
    defaults.update(kwargs)
    return PromptCriticOutput(**defaults)


def test_prompt_critic_disabled_keeps_original_draft(monkeypatch):
    monkeypatch.delenv("EASYADS_ENABLE_LLM_CALLS", raising=False)
    output, metadata = critique_prompt_draft(
        _state(),
        prompt_draft="clean commercial background",
        target_engine="gpt_image_2",
        prompt_context={"business_type": "cafe"},
    )

    assert output is None
    assert metadata["fallback_reason"] == "prompt_critic_not_enabled"


def test_resolver_applies_allowed_visual_fragment_only():
    output = _critic_output(
        rewrite=PromptRewriteProposal(
            add_fragments=[
                "soft commercial lighting with clean composition and negative space",
                "readable Korean letters on store sign",
            ]
        )
    )

    resolved = resolve_prompt_rewrite("Create a text-free advertising background.", output, {"business_type": "cafe"})

    assert resolved.rewrite_applied is True
    assert "soft commercial lighting" in resolved.prompt
    assert "readable Korean letters" not in resolved.prompt
    assert "no readable text" in resolved.prompt
    assert resolved.rejected_change_codes == ["add_rejected"]


def test_resolver_rejects_no_text_policy_weakening():
    resolved = resolve_prompt_rewrite("clean commercial background", _critic_output(preserve_no_text_policy=False), {"business_type": "cafe"})

    assert resolved.fallback_used is True
    assert resolved.fallback_reason == "prompt_critic_policy_not_preserved"


def test_resolver_rejects_business_or_reference_mutation():
    output = _critic_output(rewrite=PromptRewriteProposal(add_fragments=["business_type=restaurant commercial lighting"]))

    resolved = resolve_prompt_rewrite("clean commercial background", output, {"business_type": "cafe"})

    assert resolved.rewrite_applied is False
    assert "business_type=restaurant" not in resolved.prompt
    assert "add_rejected" in resolved.rejected_change_codes


def test_image_prompt_planner_uses_critic_metadata_without_raw_prompt(monkeypatch):
    critic = _critic_output()
    monkeypatch.setattr(
        "orchestrator.app.llm.nodes.image_prompt_planner.critique_prompt_draft",
        lambda *args, **kwargs: (
            critic,
            {"llm_attempted": True, "fallback_used": False, "provider": "local_openai_compat", "selected_model_class": "local_quality"},
        ),
    )

    update = image_prompt_planner_node(_state())
    spec = update["image_prompt_spec"]
    metadata = spec["metadata"]["prompt_critic"]

    assert "soft commercial lighting" in spec["positive_prompt_en"]
    assert metadata["attempted"] is True
    assert metadata["success"] is True
    assert metadata["quality_score"] == 0.82
    assert metadata["issue_codes"] == ["visual_clutter"]
    assert metadata["rewrite_applied"] is True
    assert "prompt_draft" not in metadata
    assert spec["metadata"]["render_text_in_image"] is False
    assert spec["metadata"]["selected_reference_template"]["template_id"] == "seed_cafe_strawberry_feed_001"


def test_prompt_critic_fallback_does_not_add_llm_call_results(monkeypatch):
    monkeypatch.delenv("EASYADS_ENABLE_LLM_CALLS", raising=False)

    update = image_prompt_planner_node(_state())

    assert update["image_prompt_spec"]["metadata"]["prompt_critic"]["fallback_used"] is True
    assert update["llm_call_results"] == []


def test_low_confidence_critic_does_not_apply_rewrite():
    resolved = resolve_prompt_rewrite("clean commercial background", _critic_output(confidence=0.2), {"business_type": "cafe"})

    assert resolved.fallback_used is True
    assert resolved.fallback_reason == "prompt_critic_low_confidence"


def test_deterministic_downstream_nodes_do_not_call_structured_llm_runner():
    for node in [prompt_renderer_node, t2i_request_builder_node, t2i_generation_node, text_renderer_node, result_node]:
        assert "run_structured_node" not in inspect.getsource(node)


def test_resolver_never_applies_full_rewritten_prompt_directly():
    output = _critic_output(rewrite=PromptRewriteProposal(rewritten_prompt="soft commercial lighting and clean composition"))

    resolved = resolve_prompt_rewrite(
        "strawberry latte advertising background",
        output,
        {"business_type": "cafe", "item_or_service": "strawberry latte"},
    )

    assert resolved.rewrite_applied is False
    assert "strawberry latte" in resolved.prompt
    assert "rewritten_prompt_direct_apply_blocked" in resolved.rejected_change_codes


def test_resolver_rejects_product_subject_removal():
    output = _critic_output(rewrite=PromptRewriteProposal(remove_fragments=["strawberry latte"]))

    resolved = resolve_prompt_rewrite(
        "strawberry latte commercial photography",
        output,
        {"business_type": "cafe", "item_or_service": "strawberry latte", "primary_subject": "strawberry latte"},
    )

    assert "strawberry latte" in resolved.prompt
    assert "remove_protected_context_rejected" in resolved.rejected_change_codes


def test_resolver_rejects_product_subject_replacement():
    output = _critic_output(rewrite=PromptRewriteProposal(replace_fragments={"strawberry latte": "premium lighting"}))

    resolved = resolve_prompt_rewrite(
        "strawberry latte commercial photography",
        output,
        {"business_type": "cafe", "item_or_service": "strawberry latte"},
    )

    assert "strawberry latte" in resolved.prompt
    assert "replace_protected_context_rejected" in resolved.rejected_change_codes


def test_resolver_rejects_hangul_text_injection():
    output = _critic_output(rewrite=PromptRewriteProposal(add_fragments=["soft commercial lighting with 신메뉴 출시 signage"]))

    resolved = resolve_prompt_rewrite("cafe advertising background", output, {"business_type": "cafe"})

    assert "신메뉴" not in resolved.prompt
    assert "add_rejected" in resolved.rejected_change_codes


def test_resolver_rejects_phone_price_and_discount_injection():
    output = _critic_output(
        rewrite=PromptRewriteProposal(
            add_fragments=[
                "premium commercial scene with 010-1234-5678",
                "clean composition with 30% discount",
                "realistic photography with 15,000 price tag",
            ]
        )
    )

    resolved = resolve_prompt_rewrite("restaurant advertising background", output, {"business_type": "restaurant"})

    assert "010-1234-5678" not in resolved.prompt
    assert "30%" not in resolved.prompt
    assert "15,000" not in resolved.prompt


def test_prompt_critic_schema_rejects_spec_override_fields():
    with pytest.raises(ValidationError):
        PromptCriticOutput.model_validate(
            {
                "quality_score": 0.9,
                "confidence": 0.9,
                "render_text_in_image": True,
                "rewrite": {},
            }
        )
