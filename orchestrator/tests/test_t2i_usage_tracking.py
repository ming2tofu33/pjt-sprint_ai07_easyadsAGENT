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


def test_t2i_usage_skips_failed_or_mock_result(monkeypatch):
    calls = []
    monkeypatch.setattr(t2i_generation.usage_service, "record_t2i_usage", lambda **kwargs: calls.append(kwargs))

    t2i_generation._record_t2i_usage({"workspace_id": "ws1"}, SimpleNamespace(error="failed", image_paths=[], engine="gpt_image_2"))
    t2i_generation._record_t2i_usage({"workspace_id": "ws1"}, SimpleNamespace(error=None, image_paths=["x"], engine="mock"))

    assert calls == []
