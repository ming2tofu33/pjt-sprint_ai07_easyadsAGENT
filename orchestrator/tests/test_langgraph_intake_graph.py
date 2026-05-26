import pytest

from langgraph.types import Command

from orchestrator.app.graph.builder import build_intake_graph


def _interrupt_payload(result):
    return result["__interrupt__"][0].value


def test_intake_graph_interrupt_resume_updates_context_with_same_thread_id():
    graph = build_intake_graph()
    config = {"configurable": {"thread_id": "thread-resume-ok"}}
    first = graph.invoke({"user_input": "우리 삼겹살집 인스타 광고", "thread_id": "thread-resume-ok"}, config=config)
    payload = _interrupt_payload(first)

    resumed = graph.invoke(
        Command(resume={"job_id": payload["job_id"], "thread_id": payload["thread_id"], "field": "promotion_goal", "value": "discount_event"}),
        config=config,
    )

    assert resumed["context"]["promotion_goal"] == "discount_event"
    assert "promotion_goal" not in resumed["missing_fields"]


def test_intake_graph_requires_same_thread_id_for_resume():
    graph = build_intake_graph()
    config = {"configurable": {"thread_id": "thread-resume-source"}}
    first = graph.invoke({"user_input": "우리 삼겹살집 인스타 광고", "thread_id": "thread-resume-source"}, config=config)
    payload = _interrupt_payload(first)

    wrong_config = {"configurable": {"thread_id": "thread-resume-other"}}
    with pytest.raises(Exception):
        graph.invoke(
            Command(resume={"job_id": payload["job_id"], "thread_id": payload["thread_id"], "field": "promotion_goal", "value": "discount_event"}),
            config=wrong_config,
        )


def test_intake_graph_ends_ready_for_planning_when_no_missing_fields():
    graph = build_intake_graph()
    config = {"configurable": {"thread_id": "thread-ready"}}
    result = graph.invoke(
        {
            "user_input": "삼겹살 할인 인스타 광고",
            "thread_id": "thread-ready",
            "context": {"business_type": "restaurant", "item_or_service": "삼겹살", "promotion_goal": "discount_event", "extra": {"ad_format": "instagram_feed"}},
        },
        config=config,
    )

    assert "__interrupt__" not in result
    assert result["missing_fields"] == []
    assert result["current_brief"]["ready_for_planning"] is True
