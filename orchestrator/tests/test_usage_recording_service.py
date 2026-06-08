import pytest
from datetime import datetime, timezone

from orchestrator.app.usage import service
from orchestrator.app.usage.errors import InvalidUsagePlan, InvalidUsageRange


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


def test_usage_summary_without_plan_includes_all_event_plans(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "memory")
    service.record_usage_event(workspace_id="ws1", event_type="t2i_generation", quantity=1, unit="image", plan="free")
    service.record_usage_event(workspace_id="ws1", event_type="t2i_generation", quantity=2, unit="image", plan="premium")

    summary = service.get_usage_summary(
        workspace_id="ws1",
        quota_plan="premium",
        start_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end_at=datetime(2027, 1, 1, tzinfo=timezone.utc),
    )

    assert summary["plan"] == "premium"
    assert summary["totals"]["t2iImages"] == 3
    assert {row["key"] for row in summary["byEventPlan"]} == {"free", "premium"}


def test_invalid_usage_plan_does_not_fall_back_to_free(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "memory")

    with pytest.raises(InvalidUsagePlan):
        service.record_usage_event(workspace_id="ws1", event_type="llm_call", unit="call", plan="enterprise")


def test_partial_custom_range_is_rejected():
    with pytest.raises(InvalidUsageRange):
        service.get_usage_summary(workspace_id="ws1", start_at=datetime(2026, 1, 1, tzinfo=timezone.utc))


def test_quota_uses_all_window_usage_after_plan_change(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "memory")
    service.record_usage_event(workspace_id="ws1", event_type="t2i_generation", quantity=1, unit="image", plan="free")
    service.record_usage_event(workspace_id="ws1", event_type="t2i_generation", quantity=4, unit="image", plan="economic")

    summary = service.get_usage_summary(
        workspace_id="ws1",
        quota_plan="premium",
        start_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end_at=datetime(2027, 1, 1, tzinfo=timezone.utc),
    )

    assert summary["totals"]["t2iImages"] == 5


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


def test_metadata_sanitizer_removes_access_token_and_password():
    sanitized = service.sanitize_usage_metadata(
        {
            "access_token": "secret",
            "refresh_token": "secret",
            "authorization_header": "Bearer secret",
            "password": "secret",
            "credentials": {"client_secret": "secret"},
            "keyboard_layout": "ko",
        }
    )

    assert "access_token" not in sanitized
    assert "refresh_token" not in sanitized
    assert "authorization_header" not in sanitized
    assert "password" not in sanitized
    assert "credentials" not in sanitized
    assert sanitized["keyboard_layout"] == "ko"


def test_negative_quantity_rejected_in_memory_and_postgres(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "memory")
    with pytest.raises(ValueError):
        service.record_usage_event(workspace_id="ws1", event_type="llm_call", unit="call", quantity=-1)

    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")
    with pytest.raises(ValueError):
        service.record_usage_event(workspace_id="ws1", event_type="llm_call", unit="call", cost_usd="-0.01")


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
