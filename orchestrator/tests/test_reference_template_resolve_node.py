from orchestrator.app.graph.state import create_initial_marketing_state
from orchestrator.app.reference_catalog.nodes import reference_template_resolve_node
from orchestrator.app.schemas.llm_marketing import InitialMarketingRequest


def test_reference_template_resolve_node_stores_template_and_artifact():
    state = create_initial_marketing_state(
        InitialMarketingRequest(
            user_input="ready",
            selected_reference_template_id="seed_cafe_strawberry_feed_001",
        )
    )

    update = reference_template_resolve_node(state)

    assert update["selected_reference_template"]["template_id"] == "seed_cafe_strawberry_feed_001"
    assert update["reference_template_selection"]["template_id"] == "seed_cafe_strawberry_feed_001"
    assert update["current_brief"]["reference_template_selected"] is True
    assert update["artifact_refs"][0]["artifact_type"] == "reference_template"
    assert "reference_template_warning" in update["current_brief"]


def test_reference_template_resolve_node_invalid_id_does_not_crash():
    state = create_initial_marketing_state(
        InitialMarketingRequest(
            user_input="ready",
            selected_reference_template_id="missing_template",
        )
    )

    update = reference_template_resolve_node(state)

    assert update["reference_template_selection"]["warnings"] == ["reference_template_not_found"]
    assert update["current_brief"]["reference_template_error"] == "reference_template_not_found"
    assert "missing_template" in update["error_message"]


def test_reference_template_resolve_node_no_id_is_noop():
    state = create_initial_marketing_state(InitialMarketingRequest(user_input="ready"))

    assert reference_template_resolve_node(state) == {}
