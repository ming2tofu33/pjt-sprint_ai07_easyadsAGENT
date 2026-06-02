# Supabase DB Schema v1

## Purpose

This schema adds the Postgres foundation for EasyAds while preserving the current in-memory backend as the default path.

The migration is stored at `supabase/migrations/20260602_core_schema_v1.sql`. It is not applied to a remote Supabase project by this work.

## Tables

- `profiles`
- `workspaces`
- `workspace_members`
- `projects`
- `brand_kits`
- `chat_threads`
- `chat_messages`
- `chat_message_assets`
- `assets`
- `generation_jobs`
- `generation_outputs`
- `generation_job_events`
- `usage_events`
- `feedback_events`

## API Compatibility IDs

The API already exposes string ids such as `job_...` and `thread_...`. The DB schema keeps internal UUID primary keys and adds public ids for compatibility:

- `generation_jobs.id`: internal UUID primary key
- `generation_jobs.public_job_id`: public API id such as `job_xxx`
- `chat_threads.id`: internal UUID primary key
- `chat_threads.public_thread_id`: public API id such as `thread_xxx`

Frontend and BFF code should continue to treat `job_id` and `thread_id` as public string ids.

## Asset Columns

The `assets` table is prepared for the upcoming R2/object storage milestone:

- `kind`
- `storage_provider`
- `bucket`
- `object_key`
- `mime_type`
- `size_bytes`
- `checksum_sha256`
- `public_url`
- `signed_url_expires_at`
- `deleted_at`

`assets.kind` can support values such as `result`, `thumbnail`, `upload`, `reference`, and `logo` in later application logic.

## Workspace Scope

User-owned data tables carry `workspace_id` directly where practical. `chat_message_assets` and `generation_job_events` include both `workspace_id` and `thread_id` so workspace-scoped RLS, cleanup, and archive queries do not require avoidable joins.

## Generation Job Future Columns

`generation_jobs` includes nullable/default columns for upcoming Modal/R2/model tracking:

- attempt/request tracking: `attempt_no`, `request_key`, `retry_count`
- asset references: `input_asset_id`, `reference_asset_id`
- model metadata: `run_mode`, `engine`, `model_provider`, `model_name`, `model_version`
- prompt trace: `prompt_text`, `prompt_hash`, `prompt_preview`
- request snapshots: `brief`, `brand_kit_snapshot`, `params`, `request_payload`
- execution timing: `queued_at`, `started_at`, `finished_at`
- external call trace: `modal_call_id`

The current service fills only the fields available at GenerationJob creation time.

## Status Values

Status values are stored as `text` with lightweight check constraints instead of Postgres enums.

`chat_threads.status`:

- `draft`
- `generating`
- `completed`
- `failed`
- `archived`

`generation_jobs.status`:

- `queued`
- `running`
- `done`
- `failed`
- `canceled`

## Required Indexes

- `chat_threads_workspace_recent_idx`
- `chat_messages_thread_sequence_idx`
- `generation_jobs_thread_created_idx`
- `generation_jobs_active_idx`
- `generation_outputs_thread_created_idx`
- `generation_outputs_one_final_per_thread_idx`
- `assets_workspace_created_idx`
- `assets_bucket_object_key_idx`
- `usage_events_workspace_created_idx`
- `generation_job_events_job_created_idx`
- `generation_job_events_thread_created_idx`

## Scope Limits

- RLS policy design is not included in this migration.
- Supabase Auth integration is not enforced yet.
- R2/object storage upload is not implemented.
- Modal execution and evaluation pipelines are not implemented.
- Generated result static serving and signed URL generation remain separate follow-up work.
