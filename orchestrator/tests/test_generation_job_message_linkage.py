from orchestrator.app.api.schemas.chat_threads import ChatMessageResponse

def test_chat_message_schema_allows_job_and_event():
    msg = ChatMessageResponse(
        message_id="msg_1",
        thread_id="thread_1",
        role="user",
        content="hello",
        job_id="job_1",
        event_type="user_input",
        sequence_no=1,
        created_at="2026-06-05T00:00:00Z",
        updated_at="2026-06-05T00:00:00Z"
    )
    assert msg.job_id == "job_1"
    assert msg.event_type == "user_input"
