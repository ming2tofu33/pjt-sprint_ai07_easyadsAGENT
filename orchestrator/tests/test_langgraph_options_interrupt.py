import json

from langgraph.types import Command

from orchestrator.app.graph.builder import build_intake_graph
from orchestrator.app.graph.nodes import options_node
from orchestrator.app.graph.state import create_initial_marketing_state
from orchestrator.app.schemas.llm_marketing import InitialMarketingRequest


def test_graph_interrupt_payload_is_json_serializable():
    graph = build_intake_graph()
    config = {"configurable": {"thread_id": "thread-interrupt-json"}}

    result = graph.invoke({"user_input": "우리 삼겹살집 인스타 광고", "thread_id": "thread-interrupt-json"}, config=config)
    interrupt_obj = result["__interrupt__"][0]
    payload = interrupt_obj.value

    assert payload["type"] == "option_question"
    assert payload["thread_id"] == "thread-interrupt-json"
    assert payload["option_question"]["field"] == "promotion_goal"
    assert "question" in payload["option_question"]
    assert "title" not in payload["option_question"]
    json.dumps(payload, ensure_ascii=False)
