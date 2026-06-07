-- Migration for multiturn state persistence v1

-- 1. chat_messages 확장
alter table chat_messages
  add column if not exists generation_job_id uuid
    references generation_jobs(id)
    on delete set null,
  add column if not exists event_type text;

-- 중복 lifecycle event 방지용 partial unique index
create unique index if not exists chat_messages_job_event_unique_idx
on chat_messages (generation_job_id, event_type)
where generation_job_id is not null
  and event_type in (
    'user_input',
    'generation_queued',
    'generation_started',
    'generation_completed',
    'generation_failed'
  );

create index if not exists chat_messages_generation_job_idx
on chat_messages (generation_job_id, created_at);

-- 2. chat_state_snapshots 테이블
create table if not exists chat_state_snapshots (
  id uuid primary key default gen_random_uuid(),

  public_snapshot_id text not null unique,

  workspace_id uuid not null
    references workspaces(id)
    on delete cascade,

  thread_id uuid not null
    references chat_threads(id)
    on delete cascade,

  generation_job_id uuid
    references generation_jobs(id)
    on delete set null,

  source_message_id uuid
    references chat_messages(id)
    on delete set null,

  parent_snapshot_id uuid
    references chat_state_snapshots(id)
    on delete set null,

  snapshot_version bigint not null,
  schema_version integer not null default 1,

  snapshot_kind text not null,

  state_payload jsonb not null default '{}'::jsonb,
  changed_fields text[] not null default '{}',

  selected_reference_template_id text,
  reference_template_snapshot jsonb not null default '{}'::jsonb,
  brand_kit_snapshot jsonb not null default '{}'::jsonb,

  snapshot_key text,
  metadata jsonb not null default '{}'::jsonb,

  created_by uuid,
  created_at timestamptz not null default now(),

  unique (thread_id, snapshot_version),

  constraint chat_state_snapshots_kind_check check (
    snapshot_kind in (
      'input',
      'restored_input',
      'graph_completed',
      'waiting_user_input',
      'job_completed',
      'job_failed',
      'manual'
    )
  )
);

create unique index if not exists chat_state_snapshots_thread_key_unique_idx
on chat_state_snapshots (thread_id, snapshot_key)
where snapshot_key is not null;

create index if not exists chat_state_snapshots_thread_version_idx
on chat_state_snapshots (thread_id, snapshot_version desc);

create index if not exists chat_state_snapshots_generation_job_idx
on chat_state_snapshots (generation_job_id, created_at desc);
