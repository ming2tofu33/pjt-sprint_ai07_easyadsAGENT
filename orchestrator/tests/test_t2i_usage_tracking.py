from types import SimpleNamespace

from orchestrator.app.llm.nodes import t2i_generation


def test_t2i_usage_records_successful_actual_result(monkeypatch):
    calls = []
    result = SimpleNamespace(
        error=None,
        image_paths=["data/outputs/job/final_0.png"],
        engine="gpt_image_2",
        metadata={"model": "gpt-image-2", "quality": "high", "requested_run_mode": "gpt_image_2"},
        width=1024,
        height=1024,
    )
    state = {
        "workspace_id": "ws1",
        "thread_id": "thread1",
        "job_id": "job1",
        "usage_thread_db_id": "thread_uuid",
        "usage_job_db_id": "job_uuid",
        "user_id": "user1",
        "user_plan": "premium",
    }
    monkeypatch.setattr(t2i_generation.usage_service, "record_t2i_usage", lambda **kwargs: calls.append(kwargs))

    t2i_generation._record_t2i_usage(state, result)

    assert calls[0]["workspace_id"] == "ws1"
    assert calls[0]["engine"] == "gpt_image_2"
    assert calls[0]["image_count"] == 1
    assert calls[0]["width"] == 1024
    assert calls[0]["height"] == 1024
    assert calls[0]["thread_id"] == "thread_uuid"
    assert calls[0]["job_id"] == "job_uuid"


def test_t2i_usage_uses_internal_job_and_thread_uuid(monkeypatch):
    calls = []
    result = SimpleNamespace(error=None, image_paths=["x"], engine="flux", metadata={"generation_attempt": 2}, width=512, height=512)
    state = {"workspace_id": "ws1", "thread_id": "thread_public", "job_id": "job_public", "usage_thread_db_id": "thread_uuid", "usage_job_db_id": "job_uuid"}
    monkeypatch.setattr(t2i_generation.usage_service, "record_t2i_usage", lambda **kwargs: calls.append(kwargs))

    t2i_generation._record_t2i_usage(state, result)

    assert calls[0]["thread_id"] == "thread_uuid"
    assert calls[0]["job_id"] == "job_uuid"
    assert calls[0]["attempt_index"] == 2


def test_t2i_usage_skips_failed_or_mock_result(monkeypatch):
    calls = []
    monkeypatch.setattr(t2i_generation.usage_service, "record_t2i_usage", lambda **kwargs: calls.append(kwargs))

    t2i_generation._record_t2i_usage({"workspace_id": "ws1"}, SimpleNamespace(error="failed", image_paths=[], engine="gpt_image_2"))
    t2i_generation._record_t2i_usage({"workspace_id": "ws1"}, SimpleNamespace(error=None, image_paths=["x"], engine="mock"))

    assert calls == []
