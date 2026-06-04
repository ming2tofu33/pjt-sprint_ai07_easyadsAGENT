from pathlib import Path


MIGRATION = Path("supabase/migrations/20260602_core_schema_v1.sql")


def test_core_schema_migration_exists_and_contains_tables():
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "create extension if not exists pgcrypto" in sql
    for table in [
        "profiles",
        "workspaces",
        "workspace_members",
        "projects",
        "brand_kits",
        "chat_threads",
        "chat_messages",
        "chat_message_assets",
        "assets",
        "generation_jobs",
        "generation_outputs",
        "generation_job_events",
        "usage_events",
        "feedback_events",
    ]:
        assert f"create table if not exists {table}" in sql


def test_core_schema_migration_contains_required_indexes_and_public_ids():
    sql = MIGRATION.read_text(encoding="utf-8")

    for index in [
        "chat_threads_workspace_recent_idx",
        "chat_messages_thread_sequence_idx",
        "generation_jobs_thread_created_idx",
        "generation_jobs_active_idx",
        "generation_outputs_thread_created_idx",
        "generation_outputs_one_final_per_thread_idx",
        "assets_workspace_created_idx",
        "assets_bucket_object_key_idx",
        "usage_events_workspace_created_idx",
        "generation_job_events_job_created_idx",
        "generation_job_events_thread_created_idx",
    ]:
        assert index in sql

    assert "public_job_id text unique not null" in sql
    assert "public_thread_id text unique not null" in sql


def test_core_schema_assets_usage_and_events_are_workspace_scoped():
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "kind text not null" in sql
    assert "storage_provider text not null default 'r2'" in sql
    assert "mime_type text" in sql
    assert "size_bytes bigint" in sql
    assert "checksum_sha256 text" in sql
    assert "public_url text" in sql
    assert "deleted_at timestamptz null" in sql
    assert "create table if not exists chat_message_assets" in sql
    assert "create table if not exists generation_job_events" in sql
    assert "message text" in sql
    assert "provider text" in sql
    assert "model_name text" in sql
    assert "cost_usd numeric" in sql
    assert "thumbnail_asset_id uuid references assets(id) on delete set null" in sql
    assert "variant_index integer not null default 0" in sql


def test_core_schema_generation_jobs_has_future_execution_columns():
    sql = MIGRATION.read_text(encoding="utf-8")

    for column in [
        "attempt_no integer not null default 1",
        "request_key text",
        "input_asset_id uuid null references assets(id) on delete set null",
        "reference_asset_id uuid null references assets(id) on delete set null",
        "run_mode text",
        "engine text",
        "model_provider text",
        "model_name text",
        "model_version text",
        "prompt_text text",
        "prompt_hash text",
        "prompt_preview text",
        "brief jsonb not null default '{}'::jsonb",
        "brand_kit_snapshot jsonb not null default '{}'::jsonb",
        "params jsonb not null default '{}'::jsonb",
        "request_payload jsonb not null default '{}'::jsonb",
        "modal_call_id text",
        "retry_count integer not null default 0",
        "queued_at timestamptz",
        "started_at timestamptz",
        "finished_at timestamptz",
    ]:
        assert column in sql
