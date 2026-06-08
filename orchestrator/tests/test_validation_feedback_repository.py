from pathlib import Path


def test_validation_feedback_migration_contains_append_only_schema():
    sql = Path("supabase/migrations/20260608_validation_feedback_regeneration_v1.sql").read_text(encoding="utf-8")

    assert "create table if not exists validation_reports" in sql
    assert "public_validation_report_id" in sql
    assert "validation_reports_output_created_idx" in sql
    assert "regeneration_idempotency_key" in sql
    assert "previous_output_id" in sql
