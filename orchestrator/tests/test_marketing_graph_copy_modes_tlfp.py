from langgraph.types import Command

from orchestrator.app.graph.builder import build_marketing_graph


def _request(mode: str, job_id: str):
    return {
        "user_input": "ready",
        "job_id": job_id,
        "thread_id": job_id,
        "copy_generation_mode": mode,
        "context": {
            "business_type": "restaurant",
            "item_or_service": "삼겹살",
            "promotion_goal": "reservation_cta",
            "extra": {"ad_format": "instagram_feed"},
        },
    }


def test_auto_pilot_mode_runs_through_tlfp_to_mock():
    result = build_marketing_graph().invoke(_request("auto_pilot", "copy-mode-auto"), config={"configurable": {"thread_id": "copy-mode-auto"}})

    assert result["status"] == "done"
    assert result["copy_spec"]["items"][0]["role"] == "headline"
    assert result["t2i_result"]["engine"] == "mock"


def test_no_copy_mode_runs_without_marketing_copy_to_mock():
    result = build_marketing_graph().invoke(_request("no_copy", "copy-mode-none"), config={"configurable": {"thread_id": "copy-mode-none"}})

    assert result["status"] == "done"
    assert result["marketing_copy"] is None
    assert result["copy_spec"]["copy_mode"] == "no_copy"
    assert result["text_layout_spec"]["template"] == "no_text"
    assert result["t2i_request"]["metadata"]["text_overlay_pending"] is False
    assert result["t2i_result"]["engine"] == "mock"


def test_suggest_candidates_interrupt_then_resume_to_mock():
    graph = build_marketing_graph()
    config = {"configurable": {"thread_id": "copy-mode-suggest"}}
    first = graph.invoke(_request("suggest_candidates", "copy-mode-suggest"), config=config)
    payload = first["__interrupt__"][0].value

    assert payload["type"] == "copy_candidate_selection"
    assert [candidate["id"] for candidate in payload["candidates"]] == ["copy_1", "copy_2", "copy_3"]

    result = graph.invoke(Command(resume={"selected_copy_id": "copy_2"}), config=config)

    assert result["status"] == "done"
    assert result["selected_copy_id"] == "copy_2"
    assert result["copy_spec"]["items"][0]["text"] == "회식은 역시 삼겹살"
    assert result["t2i_result"]["engine"] == "mock"


def test_custom_input_interrupt_then_resume_to_mock():
    graph = build_marketing_graph()
    config = {"configurable": {"thread_id": "copy-mode-custom"}}
    first = graph.invoke(_request("custom_input", "copy-mode-custom"), config=config)
    payload = first["__interrupt__"][0].value

    assert payload["type"] == "custom_copy_input"

    result = graph.invoke(
        Command(resume={"user_custom_headline": "봄처럼 달콤한 딸기 케이크", "user_custom_subcopy": "이번 주 한정 메뉴"}),
        config=config,
    )

    assert result["status"] == "done"
    assert result["marketing_copy"]["headline"] == "봄처럼 달콤한 딸기 케이크"
    assert result["copy_spec"]["items"][0]["text"] == "봄처럼 달콤한 딸기 케이크"
    assert result["t2i_result"]["engine"] == "mock"


def test_custom_input_with_initial_headline_skips_interrupt():
    request = _request("custom_input", "copy-mode-custom-direct")
    request["user_custom_headline"] = "직접 준비한 문구"
    result = build_marketing_graph().invoke(request, config={"configurable": {"thread_id": "copy-mode-custom-direct"}})

    assert "__interrupt__" not in result
    assert result["status"] == "done"
    assert result["marketing_copy"]["headline"] == "직접 준비한 문구"
