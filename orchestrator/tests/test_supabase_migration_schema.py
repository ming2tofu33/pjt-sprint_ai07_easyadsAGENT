from pathlib import Path


MIGRATION = Path("supabase/migrations/20260602_core_schema_v1.sql")
ARCHIVE_PERFORMANCE_MIGRATION = Path("supabase/migrations/20260611_archive_items_user_recent_idx.sql")
TENANT_RLS_MIGRATION = Path("supabase/migrations/20260702_tenant_rls_v1.sql")

TENANT_RLS_TABLES = [
    "workspaces",
    "workspace_members",
    "projects",
    "brand_kits",
    "chat_threads",
    "chat_messages",
    "assets",
    "chat_message_assets",
    "generation_jobs",
    "generation_outputs",
    "generation_job_events",
    "archive_items",
    "usage_events",
    "feedback_events",
    "chat_state_snapshots",
    "validation_reports",
]


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
        "archive_items",
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
        "archive_items_workspace_saved_idx",
        "archive_items_workspace_public_job_unique_idx",
    ]:
        assert index in sql

    assert "public_job_id text unique not null" in sql
    assert "public_thread_id text unique not null" in sql


def test_archive_user_recent_index_migration_exists():
    sql = ARCHIVE_PERFORMANCE_MIGRATION.read_text(encoding="utf-8")

    assert "archive_items_workspace_created_by_saved_idx" in sql
    assert "on archive_items (workspace_id, created_by, saved_at desc)" in sql
    assert "where deleted_at is null" in sql


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
    assert "public_job_id text" in sql
    assert "source text not null default 'generated'" in sql
    assert "saved_at timestamptz not null default now()" in sql


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


def test_tenant_rls_migration_enables_workspace_scoped_tables():
    sql = TENANT_RLS_MIGRATION.read_text(encoding="utf-8")

    assert "create or replace function public.easyads_has_workspace_access" in sql
    assert "security definer" in sql
    assert "auth.uid() is not null" in sql
    assert "from public.workspaces w" in sql
    assert "from public.workspace_members wm" in sql

    for table in TENANT_RLS_TABLES:
        assert f"alter table if exists public.{table} enable row level security" in sql
        assert f'drop policy if exists "{table}_workspace_isolation" on public.{table}' in sql
        assert f'create policy "{table}_workspace_isolation"' in sql
        assert f"on public.{table}\nfor all\nto authenticated" in sql
