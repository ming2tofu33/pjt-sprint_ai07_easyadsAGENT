from orchestrator.app.graph.builder import build_marketing_graph
from orchestrator.app.graph.routers import route_after_layout_refiner
from orchestrator.app.graph.state import create_initial_marketing_state
from orchestrator.app.schemas.llm_marketing import InitialMarketingRequest


def test_marketing_graph_registers_image_aware_layout_nodes():
    graph = build_marketing_graph()
    graph_data = graph.get_graph()
    node_names = {getattr(node, "id", None) for node in graph_data.nodes.values()} | set(graph_data.nodes)

    assert "image_layout_analyzer" in node_names
    assert "post_t2i_layout_refiner" in node_names


def test_initial_marketing_state_has_image_aware_layout_defaults():
    state = create_initial_marketing_state(InitialMarketingRequest(user_input="카페 딸기라떼 광고 만들어줘"))

    assert state["image_layout_analysis"] is None
    assert state["layout_candidate_scores"] == []
    assert state["layout_refinement_result"] is None
    assert state["layout_copy_fit_report"] is None
    assert state["layout_revision_attempts"] == 0


def test_route_after_layout_refiner_honors_actions():
    assert route_after_layout_refiner({"layout_refinement_result": {"action": "render"}}) == "safe_area_gate"
    assert route_after_layout_refiner({"layout_refinement_result": {"action": "reduce_information"}}) == "safe_area_gate"
    assert route_after_layout_refiner({"layout_refinement_result": {"action": "regenerate_background"}, "layout_revision_attempts": 1}) == "image_prompt_planner"
    assert route_after_layout_refiner({"layout_refinement_result": {"action": "manual_review"}}) == "result"
    assert route_after_layout_refiner({"layout_refinement_result": {"action": "rewrite_copy"}}) == "result"
