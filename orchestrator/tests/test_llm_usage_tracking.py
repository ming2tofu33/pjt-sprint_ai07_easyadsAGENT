from types import SimpleNamespace

from orchestrator.app.llm import node_runner


def test_llm_usage_recorded_from_success_result(monkeypatch):
    calls = []
    selection = SimpleNamespace(
        provider="openai",
        model_name="gpt-4.1-mini",
        provider_profile="openai-mini",
        selected_model_class="api_fast",
        node_name="copywriter",
    )
    result = SimpleNamespace(
        success=True,
        token_usage={"input_tokens": 11, "output_tokens": 7, "total_tokens": 18},
        model_selection=selection,
        metadata={"provider_request_id": "req_123"},
    )
    state = {
        "workspace_id": "ws1",
        "thread_id": "thread1",
        "job_id": "job1",
        "user_id": "user1",
        "user_plan": "premium",
    }
    monkeypatch.setattr(node_runner.usage_service, "record_llm_usage", lambda **kwargs: calls.append(kwargs))

    node_runner.record_llm_usage_from_result(state, result)

    assert calls[0]["workspace_id"] == "ws1"
    assert calls[0]["provider"] == "openai"
    assert calls[0]["model_name"] == "gpt-4.1-mini"
    assert calls[0]["input_tokens"] == 11
    assert calls[0]["output_tokens"] == 7
    assert calls[0]["provider_request_id"] == "req_123"


def test_llm_usage_skips_mock_provider(monkeypatch):
    calls = []
    selection = SimpleNamespace(provider="mock", model_name="mock", selected_model_class="mock", node_name="copywriter")
    result = SimpleNamespace(success=True, token_usage={"input_tokens": 1}, model_selection=selection, metadata={})

    monkeypatch.setattr(node_runner.usage_service, "record_llm_usage", lambda **kwargs: calls.append(kwargs))
    node_runner.record_llm_usage_from_result({"workspace_id": "ws1"}, result)

    assert calls == []
