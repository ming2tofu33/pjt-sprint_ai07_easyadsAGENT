create table if not exists validation_reports (
  id uuid primary key default gen_random_uuid(),
  public_validation_report_id text unique not null,
  workspace_id uuid not null references workspaces(id) on delete cascade,
  thread_id uuid null references chat_threads(id) on delete set null,
  job_id uuid not null references generation_jobs(id) on delete cascade,
  output_id uuid not null references generation_outputs(id) on delete cascade,
  created_by text,
  status text not null,
  decision text not null,
  validation_summary jsonb not null default '{}'::jsonb,
  failure_types jsonb not null default '[]'::jsonb,
  suggested_actions jsonb not null default '[]'::jsonb,
  source_reports jsonb not null default '{}'::jsonb,
  schema_version text not null default 'validation_feedback_v1',
  created_at timestamptz not null default now()
);

alter table generation_jobs
  add column if not exists parent_job_id uuid null references generation_jobs(id) on delete set null,
  add column if not exists previous_output_id uuid null references generation_outputs(id) on delete set null,
  add column if not exists regeneration_depth integer not null default 0,
  add column if not exists regeneration_idempotency_key text null;

alter table generation_outputs
  add column if not exists previous_output_id uuid null references generation_outputs(id) on delete set null;

create index if not exists validation_reports_workspace_created_idx
on validation_reports (workspace_id, created_at desc);

create index if not exists validation_reports_output_created_idx
on validation_reports (output_id, created_at desc);

create index if not exists validation_reports_job_created_idx
on validation_reports (job_id, created_at desc);

create unique index if not exists generation_jobs_regeneration_idempotency_idx
on generation_jobs (workspace_id, regeneration_idempotency_key)
where regeneration_idempotency_key is not null;
