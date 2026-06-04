import json

from orchestrator.app.graph.nodes import build_copy_mode_prompt
from orchestrator.app.graph.nodes import resolve_copy_generation_mode
from orchestrator.app.graph.state import create_initial_marketing_state
from orchestrator.app.llm.metadata_builders import (
    build_copy_generation_metadata,
    build_copy_mode_inference_metadata,
    build_copy_spec_parser_metadata,
    build_custom_copy_validation_metadata,
)
from orchestrator.app.llm.nodes.auto_pilot_copywriting import auto_pilot_copywriting_node
from orchestrator.app.llm.nodes.auto_pilot_copywriting import build_auto_pilot_prompt
from orchestrator.app.llm.nodes.copy_candidates import copy_candidate_generation_node
from orchestrator.app.llm.nodes.copy_candidates import build_candidate_prompt
from orchestrator.app.llm.nodes.copy_spec_parser import copy_spec_parser_node
from orchestrator.app.llm.nodes.custom_copy import custom_copy_validation_node
from orchestrator.app.llm.nodes.format_planner import format_planner_node
from orchestrator.app.llm.nodes.tone_binding import build_tone_binding_prompt
from orchestrator.app.llm.nodes.tone_binding import tone_binding_node
from orchestrator.app.schemas.llm_marketing import CopyCandidateListOutput, CopywritingOutput, InitialMarketingRequest, MarketingContext, MarketingCopy, ToneBindingOutput


def test_tone_binding_metadata_contains_context_format_and_layout():
    state = _state("auto_pilot")

    update = tone_binding_node(state)

    metadata = _llm_result_metadata(update["tone_binding_output"]["metadata"]["llm_metadata"])
    assert metadata["available_state"]["context"]["business_type"] == "restaurant"
    assert metadata["available_state"]["ad_format_spec"]["ad_format"] == "instagram_feed"
    assert metadata["available_state"]["layout_spec"]["layout_type"]


def test_copy_mode_inference_uses_metadata_contract_for_ambiguous_text():
    state = _state(None)

    mode, output = resolve_copy_generation_mode(state, "ambiguous request")

    metadata = state["llm_call_results"][0]["metadata"]
    assert mode is None
    assert output is None
    assert metadata["trace"]["node_name"] == "copy_mode_inference"
    assert metadata["available_state"]["latest_user_input"] == "ambiguous request"
    assert metadata["constraints"]["classify_only"] is True


def test_copy_candidate_metadata_contains_tone_policy():
    state = _state("suggest_candidates")

    update = copy_candidate_generation_node(state)

    metadata = _llm_result_metadata(update["copywriting_output"]["metadata"]["llm_metadata"])
    assert metadata["available_state"]["tone_binding_output"]["tone_profile"] == "warm"
    assert metadata["available_state"]["plan_policy"]["max_candidates"] == 2
    assert metadata["constraints"]["forbidden_claims"] == ["no fake discount"]
    assert metadata["constraints"]["channel_copy_rules"] == ["short CTA"]
    assert metadata["constraints"]["copy_constraints"] == ["no invented phone"]


def test_auto_pilot_metadata_contains_forbidden_claims():
    state = _state("auto_pilot")

    update = auto_pilot_copywriting_node(state)

    metadata = _llm_result_metadata(update["copywriting_output"]["metadata"]["llm_metadata"])
    assert metadata["trace"]["node_name"] == "auto_pilot_copywriting"
    assert metadata["available_state"]["tone_binding_output"]["forbidden_claims"] == ["no fake discount"]
    assert metadata["constraints"]["forbidden_claims"] == ["no fake discount"]


def test_custom_copy_validation_metadata_preserves_user_text():
    state = _state("custom_input")
    state["user_custom_headline"] = "Original headline"
    state["user_custom_subcopy"] = "Original subcopy"

    update = custom_copy_validation_node(state)

    full_metadata = build_custom_copy_validation_metadata(state)
    metadata = update["marketing_copy"]["metadata"]["llm_metadata_summary"]
    assert update["marketing_copy"]["headline"] == "Original headline"
    assert update["marketing_copy"]["subcopy"] == "Original subcopy"
    assert update["marketing_copy"]["metadata"]["preserved_user_copy"] is True
    assert full_metadata["available_state"]["user_custom_headline"] == "Original headline"
    assert "available_state" not in metadata
    assert metadata["constraints"]["preserve_user_copy"] is True
    assert metadata["constraints"]["no_rewrite"] is True


def test_copy_spec_parser_metadata_is_role_mapping_only():
    state = _state("auto_pilot")
    state["marketing_copy"] = MarketingCopy(headline="Original headline", subcopy="Original subcopy", cta="Book now").model_dump()

    update = copy_spec_parser_node(state)

    full_metadata = build_copy_spec_parser_metadata(state)
    metadata = update["copy_spec"]["metadata"]["llm_metadata_summary"]
    assert [item["role"] for item in update["copy_spec"]["items"]] == ["headline", "subheadline", "cta"]
    assert full_metadata["available_state"]["marketing_copy"]["headline"] == "Original headline"
    assert "available_state" not in metadata
    assert metadata["constraints"]["no_new_facts"] is True


def test_prompt_metadata_contracts_are_json_parseable():
    state = _state("auto_pilot")
    prompt_cases = [
        (build_tone_binding_prompt(state), "tone_binding"),
        (
            build_copy_mode_prompt("ambiguous request", state, build_copy_mode_inference_metadata(state, "ambiguous request")),
            "copy_mode_inference",
        ),
        (
            build_candidate_prompt(
                state,
                build_copy_generation_metadata(state, node_name="copy_candidate_generation", output_schema=CopyCandidateListOutput),
            ),
            "copy_candidate_generation",
        ),
        (
            build_auto_pilot_prompt(
                state,
                build_copy_generation_metadata(state, node_name="auto_pilot_copywriting", output_schema=CopywritingOutput),
            ),
            "auto_pilot_copywriting",
        ),
    ]

    for prompt, expected_node in prompt_cases:
        metadata = _metadata_contract_from_prompt(prompt)
        assert metadata["trace"]["node_name"] == expected_node
        assert metadata["output_rules"]["no_chain_of_thought"] is True


def _state(copy_generation_mode: str | None):
    state = create_initial_marketing_state(
        InitialMarketingRequest(
            user_input="ready",
            copy_generation_mode=copy_generation_mode,
            context=MarketingContext(
                business_type="restaurant",
                item_or_service="BBQ",
                promotion_goal="reservation_cta",
                extra={"ad_format": "instagram_feed"},
            ),
        )
    )
    state.update(format_planner_node(state))
    state["tone_binding_output"] = ToneBindingOutput(
        tone_profile="warm",
        copy_constraints=["no invented phone"],
        recommended_copy_mode=copy_generation_mode or "auto_pilot",
        forbidden_claims=["no fake discount"],
        channel_copy_rules=["short CTA"],
        typography_hint="friendly",
    ).model_dump()
    return state


def _llm_result_metadata(llm_metadata: dict):
    return llm_metadata["llm_call_result"]["metadata"]


def _metadata_contract_from_prompt(prompt: str) -> dict:
    marker = "metadata_contract="
    start = prompt.index(marker) + len(marker)
    metadata, _ = json.JSONDecoder().raw_decode(prompt[start:].strip())
    return metadata
