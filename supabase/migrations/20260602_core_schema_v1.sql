create extension if not exists pgcrypto;

create table if not exists profiles (
  id uuid primary key default gen_random_uuid(),
  user_id text unique,
  email text,
  display_name text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists workspaces (
  id uuid primary key default gen_random_uuid(),
  name text not null default 'Demo Workspace',
  owner_user_id text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists workspace_members (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references workspaces(id) on delete cascade,
  user_id text not null,
  role text not null default 'owner',
  created_at timestamptz not null default now(),
  unique (workspace_id, user_id)
);

create table if not exists projects (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references workspaces(id) on delete cascade,
  name text not null,
  status text not null default 'active',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists brand_kits (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references workspaces(id) on delete cascade,
  name text not null,
  business_type text,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists chat_threads (
  id uuid primary key default gen_random_uuid(),
  public_thread_id text unique not null,
  workspace_id uuid not null references workspaces(id) on delete cascade,
  created_by text,
  title text,
  status text not null default 'draft' check (status in ('draft', 'generating', 'completed', 'failed', 'archived')),
  brand_kit_id uuid,
  project_id uuid,
  final_brief jsonb,
  active_job_id uuid,
  final_output_id uuid,
  last_message_at timestamptz not null default now(),
  archived_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists chat_messages (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references workspaces(id) on delete cascade,
  thread_id uuid not null references chat_threads(id) on delete cascade,
  sequence_no integer not null,
  role text not null,
  content text,
  payload jsonb not null default '{}'::jsonb,
  created_by text,
  created_at timestamptz not null default now(),
  unique (thread_id, sequence_no)
);

create table if not exists assets (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references workspaces(id) on delete cascade,
  thread_id uuid null references chat_threads(id) on delete set null,
  project_id uuid null references projects(id) on delete set null,
  created_by text,
  kind text not null,
  storage_provider text not null default 'r2',
  bucket text not null,
  object_key text not null,
  mime_type text,
  size_bytes bigint,
  width integer,
  height integer,
  checksum_sha256 text,
  public_url text,
  signed_url_expires_at timestamptz null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  deleted_at timestamptz null,
  unique (bucket, object_key)
);

create table if not exists chat_message_assets (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references workspaces(id) on delete cascade,
  thread_id uuid not null references chat_threads(id) on delete cascade,
  message_id uuid not null references chat_messages(id) on delete cascade,
  asset_id uuid not null references assets(id) on delete cascade,
  role text,
  created_at timestamptz not null default now(),
  unique (message_id, asset_id)
);

create table if not exists generation_jobs (
  id uuid primary key default gen_random_uuid(),
  public_job_id text unique not null,
  workspace_id uuid not null references workspaces(id) on delete cascade,
  thread_id uuid references chat_threads(id) on delete set null,
  requested_by text,
  status text not null default 'queued' check (status in ('queued', 'running', 'done', 'failed', 'canceled')),
  current_stage text not null default 'queued',
  progress_percent integer not null default 0 check (progress_percent between 0 and 100),
  selected_reference_template_id text,
  attempt_no integer not null default 1,
  request_key text,
  input_asset_id uuid null references assets(id) on delete set null,
  reference_asset_id uuid null references assets(id) on delete set null,
  run_mode text,
  engine text,
  model_provider text,
  model_name text,
  model_version text,
  prompt_text text,
  prompt_hash text,
  prompt_preview text,
  brief jsonb not null default '{}'::jsonb,
  brand_kit_snapshot jsonb not null default '{}'::jsonb,
  params jsonb not null default '{}'::jsonb,
  request_payload jsonb not null default '{}'::jsonb,
  modal_call_id text,
  retry_count integer not null default 0,
  queued_at timestamptz,
  started_at timestamptz,
  finished_at timestamptz,
  output_path text,
  result_payload jsonb,
  error jsonb,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists generation_outputs (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references workspaces(id) on delete cascade,
  thread_id uuid not null references chat_threads(id) on delete cascade,
  job_id uuid references generation_jobs(id) on delete set null,
  asset_id uuid references assets(id) on delete set null,
  thumbnail_asset_id uuid references assets(id) on delete set null,
  variant_index integer not null default 0,
  output_type text not null default 'final_image',
  result_payload jsonb not null default '{}'::jsonb,
  is_final boolean not null default false,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists generation_job_events (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references workspaces(id) on delete cascade,
  thread_id uuid not null references chat_threads(id) on delete cascade,
  job_id uuid not null references generation_jobs(id) on delete cascade,
  event_type text not null,
  message text,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists usage_events (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references workspaces(id) on delete cascade,
  thread_id uuid null references chat_threads(id) on delete set null,
  job_id uuid null references generation_jobs(id) on delete set null,
  created_by text,
  event_type text not null,
  provider text,
  model_name text,
  plan text,
  quantity numeric,
  unit text,
  cost_usd numeric,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists feedback_events (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references workspaces(id) on delete cascade,
  user_id text,
  thread_id uuid references chat_threads(id) on delete set null,
  job_id uuid references generation_jobs(id) on delete set null,
  output_id uuid references generation_outputs(id) on delete set null,
  rating integer,
  feedback_type text,
  comment text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists chat_threads_workspace_recent_idx
on chat_threads (workspace_id, last_message_at desc)
where archived_at is null;

create index if not exists chat_messages_thread_sequence_idx
on chat_messages (thread_id, sequence_no);

create index if not exists generation_jobs_thread_created_idx
on generation_jobs (thread_id, created_at desc);

create index if not exists generation_jobs_active_idx
on generation_jobs (created_at)
where status in ('queued', 'running');

create index if not exists generation_outputs_thread_created_idx
on generation_outputs (thread_id, created_at desc);

create unique index if not exists generation_outputs_one_final_per_thread_idx
on generation_outputs (thread_id)
where is_final = true;

create index if not exists assets_workspace_created_idx
on assets (workspace_id, created_at desc);

create unique index if not exists assets_bucket_object_key_idx
on assets (bucket, object_key);

create index if not exists usage_events_workspace_created_idx
on usage_events (workspace_id, created_at desc);

create index if not exists generation_job_events_job_created_idx
on generation_job_events (job_id, created_at);

create index if not exists generation_job_events_thread_created_idx
on generation_job_events (thread_id, created_at);
