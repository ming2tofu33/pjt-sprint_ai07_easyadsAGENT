from datetime import datetime, timezone

from orchestrator.app.chat_threads import state_service


def test_snapshot_response_accepts_database_datetime_created_at():
    snapshot = state_service._to_response(
        {
            "snapshot_id": "snapshot_1",
            "thread_id": "thread_1",
            "snapshot_version": 1,
            "schema_version": 1,
            "snapshot_kind": "input",
            "state_payload": {"user_input": "hello"},
            "changed_fields": ["user_input"],
            "reference_template_snapshot": {},
            "brand_kit_snapshot": {},
            "metadata": {},
            "created_at": datetime(2026, 6, 6, tzinfo=timezone.utc),
        }
    )

    assert snapshot.created_at == "2026-06-06T00:00:00+00:00"


def test_memory_snapshot_service():
    state_service.reset_chat_state_snapshot_store_for_tests()
    
    # Mock get_chat_thread
    from orchestrator.app.chat_threads import service as chat_service
    
    class MockThread:
        thread_id = "t1"
        
    original_get_chat_thread = chat_service.get_chat_thread
    chat_service.get_chat_thread = lambda *args, **kwargs: MockThread()
    
    try:
        snap1 = state_service.save_thread_state_snapshot(
            public_thread_id="t1",
            workspace_id="w1",
            snapshot_kind="input",
            state_payload={"user_input": "hello"},
            changed_fields=["user_input"],
        )
        assert snap1.snapshot_version == 1
        assert snap1.state_payload["user_input"] == "hello"
        
        snap2 = state_service.save_thread_state_snapshot(
            public_thread_id="t1",
            workspace_id="w1",
            snapshot_kind="job_completed",
            state_payload={"final_brief": {"a": 1}},
            changed_fields=["final_brief"],
        )
        assert snap2.snapshot_version == 2

        latest = state_service.get_latest_thread_state_snapshot("t1", "w1")
        assert latest.snapshot_version == 2
        assert latest.state_payload["final_brief"] == {"a": 1}
        
        lst, total = state_service.list_thread_state_snapshots("t1", "w1")
        assert total == 2
        assert len(lst) == 2
    finally:
        chat_service.get_chat_thread = original_get_chat_thread


def test_snapshot_serialization_keeps_ui_visible_generation_state():
    from orchestrator.app.chat_threads.state_snapshot import serialize_marketing_state_snapshot

    snapshot = serialize_marketing_state_snapshot(
        {
            "job_id": "job_ui_state",
            "thread_id": "thread_ui_state",
            "user_input": "카페 신메뉴 광고 만들어줘",
            "copy_candidates": [{"id": "copy_1", "headline": "오늘만 신메뉴"}],
            "copy_candidate_origin": "llm",
            "selected_copy_id": "copy_1",
            "progress_state": {"progress_percent": 65, "current_stage": "modal_running", "message": "이미지를 만들고 있어요."},
            "ocr_gate_decision": "manual_review",
            "ocr_gate_status": "fail",
            "ocr_gate_retry_feedback": ["문구 위치를 다시 확인해주세요."],
            "quality_gate_decision": "warn",
            "quality_gate_status": "manual_review",
            "result_payload": {
                "status": "done",
                "final_image_url": "https://assets.example.com/final.png",
                "qualityDecision": "manual_review",
                "requiresManualReview": True,
                "qualityRejected": False,
            },
            "raw_provider_response": {"api_key": "sk-hidden"},
        }
    )

    assert snapshot["copy_candidate_origin"] == "llm"
    assert snapshot["selected_copy_id"] == "copy_1"
    assert snapshot["progress_state"]["current_stage"] == "modal_running"
    assert snapshot["ocr_gate_decision"] == "manual_review"
    assert snapshot["ocr_gate_retry_feedback"] == ["문구 위치를 다시 확인해주세요."]
    assert snapshot["quality_gate_decision"] == "warn"
    assert snapshot["result_payload"]["requiresManualReview"] is True
    assert "raw_provider_response" not in snapshot
    assert "sk-hidden" not in str(snapshot)
