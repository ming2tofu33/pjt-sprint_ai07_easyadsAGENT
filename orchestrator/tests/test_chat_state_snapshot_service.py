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
