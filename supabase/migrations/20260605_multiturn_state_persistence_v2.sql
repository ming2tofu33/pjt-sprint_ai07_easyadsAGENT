-- Migration to update generation_jobs status constraint and chat_state_snapshots created_by type

-- Drop the old status check
alter table generation_jobs
drop constraint if exists generation_jobs_status_check;

-- Add the new status check that includes 'waiting_user_input'
alter table generation_jobs
add constraint generation_jobs_status_check
check (
  status in (
    'queued',
    'running',
    'waiting_user_input',
    'done',
    'failed',
    'canceled'
  )
);

-- Change created_by type from uuid to text
alter table chat_state_snapshots
alter column created_by type text using created_by::text;
