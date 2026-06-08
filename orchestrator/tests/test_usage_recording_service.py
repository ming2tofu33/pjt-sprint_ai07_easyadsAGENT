from datetime import datetime, timezone

from orchestrator.app.usage import service


def setup_function():
    service.reset_usage_store_for_tests()


def teardown_function():
    service.reset_usage_store_for_tests()


def test_memory_usage_idempotency_and_summary(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "memory")
    service.record_usage_event(
        workspace_id="ws1",
        event_type="t2i_generation",
        quantity=1,
        unit="image",
        provider="openai",
        model_name="gpt-image-2",
        plan="premium",
        cost_usd="0.04",
        idempotency_key="same",
    )
    service.record_usage_event(
        workspace_id="ws1",
        event_type="t2i_generation",
        quantity=1,
        unit="image",
        provider="openai",
        model_name="gpt-image-2",
        plan="premium",
        cost_usd="0.04",
        idempotency_key="same",
    )

    summary = service.get_usage_summary(
        workspace_id="ws1",
        plan="premium",
        start_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end_at=datetime(2027, 1, 1, tzinfo=timezone.utc),
    )

    assert summary["totals"]["t2iImages"] == 1
    assert summary["totals"]["estimatedCostUsd"] == "0.04000000"
    assert summary["byEventType"][0]["quantity"] == "1"


def test_usage_metadata_sanitizes_secrets_paths_and_object_keys():
    sanitized = service.sanitize_usage_metadata(
        {
            "api_key": "sk-secret",
            "object_key": "workspaces/ws/asset.png",
            "safe": "visible",
            "nested": {"raw_prompt": "do not leak", "local_path": "data/outputs/x.png"},
        }
    )

    assert "api_key" not in sanitized
    assert "object_key" not in sanitized
    assert sanitized["safe"] == "visible"
    assert "raw_prompt" not in sanitized["nested"]
    assert sanitized["nested"]["local_path"] == "hidden"


def test_record_t2i_skips_mock_engine(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "memory")

    row = service.record_t2i_usage(
        workspace_id="ws1",
        engine="mock",
        model_name="mock",
        image_count=1,
        plan="free",
    )

    assert row is None
