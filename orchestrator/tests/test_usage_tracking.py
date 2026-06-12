"""Consolidated usage tracking tests.

Merged from:
- orchestrator/tests/test_usage_events_repository.py
- orchestrator/tests/test_usage_idempotency.py
- orchestrator/tests/test_usage_migration_schema.py
- orchestrator/tests/test_usage_pricing.py
- orchestrator/tests/test_usage_quota_policy.py
- orchestrator/tests/test_usage_recording_service.py
"""



# ===== from test_usage_events_repository.py =====
from orchestrator.app.db.repositories import usage_events


class FakeCursor:
    def __init__(self, rows):
        self.rows = list(rows)
        self.executed = []

    def execute(self, sql, params=()):
        self.executed.append((sql, params))

    def fetchone(self):
        if self.rows:
            return self.rows.pop(0)
        return None

    def fetchall(self):
        if self.rows:
            row = self.rows.pop(0)
            return row if isinstance(row, list) else [row]
        return []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeConnection:
    def __init__(self, rows):
        self.cursor_obj = FakeCursor(rows)

    def cursor(self):
        return self.cursor_obj

    def transaction(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_record_usage_event_once_uses_jsonb_and_idempotent_conflict():
    conn = FakeConnection(rows=[{"id": "usage_uuid", "event_type": "llm_call"}])

    row = usage_events.record_usage_event_once(
        workspace_id="ws1",
        event_type="llm_call",
        quantity=1,
        unit="call",
        idempotency_key="usage-key",
        metadata={"input_tokens": 1},
        connection=conn,
    )

    sql, params = conn.cursor_obj.executed[0]
    assert row["id"] == "usage_uuid"
    assert "on conflict (workspace_id, idempotency_key)" in sql
    assert "%s::jsonb" in sql
    assert params[-1] == '{"input_tokens": 1}'


def test_record_usage_event_once_fetches_existing_duplicate():
    conn = FakeConnection(rows=[None, {"id": "existing_usage"}])

    row = usage_events.record_usage_event_once(
        workspace_id="ws1",
        event_type="r2_upload",
        quantity=10,
        unit="byte",
        idempotency_key="duplicate",
        connection=conn,
    )

    assert row["id"] == "existing_usage"
    assert len(conn.cursor_obj.executed) == 2


def test_aggregate_usage_summary_returns_breakdowns():
    conn = FakeConnection(
        rows=[
            {
                "llm_calls": 1,
                "llm_input_tokens": 10,
                "llm_output_tokens": 5,
                "llm_total_tokens": 15,
                "t2i_images": 2,
                "r2_upload_bytes": 3,
                "r2_storage_bytes_added": 3,
                "r2_storage_bytes_removed": 1,
                "modal_gpu_seconds": 4,
                "estimated_cost_usd": 0,
                "unpriced_event_count": 1,
            },
            [{"key": "llm_call", "quantity": 1, "estimated_cost_usd": 0}],
            [{"key": "openai", "quantity": 1, "estimated_cost_usd": 0}],
            [{"key": "gpt", "quantity": 1, "estimated_cost_usd": 0}],
            [{"key": "premium", "quantity": 1, "estimated_cost_usd": 0}],
        ]
    )

    totals = usage_events.aggregate_usage_summary(workspace_id="ws1", connection=conn)

    assert totals["estimated_net_storage_bytes"] == 2
    assert totals["by_event_type"][0]["key"] == "llm_call"
    assert "group by event_type, unit" in conn.cursor_obj.executed[1][0]
    assert len(conn.cursor_obj.executed) == 5


# ===== from test_usage_idempotency.py =====
from orchestrator.app.usage import service


def test_r2_upload_usage_records_upload_and_storage_added_once(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "memory")
    service.reset_usage_store_for_tests()

    first = service.record_r2_upload_usage(
        workspace_id="ws1",
        quantity=1024,
        provider="cloudflare_r2",
        idempotency_key="asset-upload-1",
        metadata={"source": "test", "bucket": "hidden-bucket", "object_key": "workspaces/ws/x.png"},
    )
    second = service.record_r2_upload_usage(
        workspace_id="ws1",
        quantity=1024,
        provider="cloudflare_r2",
        idempotency_key="asset-upload-1",
        metadata={"source": "test"},
    )

    assert first[0]["id"] == second[0]["id"]
    assert first[1]["id"] == second[1]["id"]
    assert "bucket" not in first[0]["metadata"]
    assert "object_key" not in first[0]["metadata"]

    summary = service.get_usage_summary(workspace_id="ws1")
    assert summary["totals"]["r2UploadBytes"] == 1024
    assert summary["totals"]["r2StorageBytesAdded"] == 1024


def test_usage_breakdown_preserves_unit(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "memory")
    service.reset_usage_store_for_tests()

    service.record_usage_event(workspace_id="ws1", event_type="r2_upload", quantity=10, unit="byte", provider="cloudflare_r2")
    service.record_usage_event(workspace_id="ws1", event_type="modal_gpu_runtime", quantity=2, unit="second", provider="modal")

    summary = service.get_usage_summary(workspace_id="ws1")

    provider_units = {(row["key"], row["unit"]) for row in summary["byProvider"]}
    assert ("cloudflare_r2", "byte") in provider_units
    assert ("modal", "second") in provider_units


# ===== from test_usage_migration_schema.py =====
from pathlib import Path


MIGRATION = Path("supabase/migrations/20260608_usage_tracking_v1.sql")


def test_usage_tracking_migration_adds_idempotency_and_indexes():
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "alter table usage_events" in sql
    assert "idempotency_key" in sql
    assert "usage_events_workspace_idempotency_key_idx" in sql
    assert "where idempotency_key is not null" in sql
    assert "usage_events_workspace_user_created_idx" in sql
    assert "usage_events_workspace_type_created_idx" in sql
    assert "usage_events_job_created_idx" in sql
    assert "usage_events_quantity_nonnegative_chk" in sql
    assert "usage_events_cost_nonnegative_chk" in sql
    assert "alter column quantity set not null" in sql
    assert "usage_events_event_type_chk" in sql
    assert "usage_events_unit_chk" in sql
    assert "usage_events_plan_chk" in sql


# ===== from test_usage_pricing.py =====
from decimal import Decimal

from orchestrator.app.usage import pricing


def test_llm_cost_uses_configured_token_rates():
    catalog = {
        "llm": {
            "openai:gpt-4.1-mini": {
                "input_per_1m_tokens_usd": "0.40",
                "output_per_1m_tokens_usd": "1.60",
            }
        }
    }

    cost, metadata = pricing.calculate_llm_cost(
        provider="openai",
        model_name="gpt-4.1-mini",
        input_tokens=1000,
        output_tokens=500,
        catalog=catalog,
    )

    assert cost == Decimal("0.0012")
    assert metadata["cost_source"] == "configured_estimate"


def test_missing_t2i_price_is_unpriced_not_zero():
    cost, metadata = pricing.calculate_t2i_cost(
        provider="openai",
        model_name="gpt-image-2",
        image_count=3,
        catalog={},
    )

    assert cost is None
    assert metadata["cost_source"] == "unpriced"


def test_modal_cost_uses_gpu_seconds():
    cost, metadata = pricing.calculate_modal_cost(
        gpu_type="a10g",
        runtime_seconds="12.5",
        catalog={"modal": {"a10g": {"per_second_usd": "0.002"}}},
    )

    assert cost == Decimal("0.0250")
    assert metadata["cost_source"] == "configured_estimate"


# ===== from test_usage_quota_policy.py =====
from datetime import datetime, timezone

from orchestrator.app.usage.quota_policy import current_utc_month_window, evaluate_plan_quota


def test_current_utc_month_window_uses_utc_month_bounds():
    start, end = current_utc_month_window(datetime(2026, 6, 8, 12, tzinfo=timezone.utc))

    assert start.isoformat() == "2026-06-01T00:00:00+00:00"
    assert end.isoformat() == "2026-07-01T00:00:00+00:00"


def test_quota_without_config_is_not_enforced():
    rows = evaluate_plan_quota(plan="free", totals={"llmCalls": 5}, quota_config={})

    llm_calls = next(row for row in rows if row["metric"] == "llmCalls")
    assert llm_calls["enforced"] is False
    assert llm_calls["exceeded"] is False


def test_quota_reports_exceeded_limit():
    rows = evaluate_plan_quota(
        plan="free",
        totals={"t2iImages": 3},
        quota_config={"free": {"t2iImages": 2}},
    )

    t2i = next(row for row in rows if row["metric"] == "t2iImages")
    assert t2i["configured"] is True
    assert t2i["enforced"] is False
    assert t2i["exceeded"] is True
    assert t2i["remaining"] == 0


def test_quota_is_not_marked_enforced_when_guard_is_disabled(monkeypatch):
    monkeypatch.setenv("EASYADS_ENFORCE_USAGE_QUOTAS", "false")

    rows = evaluate_plan_quota(plan="free", totals={"llmCalls": 9}, quota_config={"free": {"llmCalls": 1}})

    llm_calls = next(row for row in rows if row["metric"] == "llmCalls")
    assert llm_calls["configured"] is True
    assert llm_calls["exceeded"] is True
    assert llm_calls["enforced"] is False


# ===== from test_usage_recording_service.py =====
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
