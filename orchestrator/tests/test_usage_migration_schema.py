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
    assert "where event_type = 'modal_gpu_seconds'" in sql
    assert "where unit = 'seconds'" in sql
