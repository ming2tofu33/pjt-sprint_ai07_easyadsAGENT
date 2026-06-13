create extension if not exists pgcrypto;

alter table usage_events
add column if not exists idempotency_key text;

alter table usage_events
alter column quantity set default 1;

update usage_events
set quantity = 1
where quantity is null;

update usage_events
set event_type = 'modal_gpu_runtime'
where event_type = 'modal_gpu_seconds';

update usage_events
set unit = 'second'
where unit = 'seconds';

alter table usage_events
alter column quantity set not null;

do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'usage_events_quantity_nonnegative_chk'
  ) then
    alter table usage_events
    add constraint usage_events_quantity_nonnegative_chk
    check (quantity is null or quantity >= 0);
  end if;

  if not exists (
    select 1 from pg_constraint where conname = 'usage_events_cost_nonnegative_chk'
  ) then
    alter table usage_events
    add constraint usage_events_cost_nonnegative_chk
    check (cost_usd is null or cost_usd >= 0);
  end if;

  if not exists (
    select 1 from pg_constraint where conname = 'usage_events_event_type_chk'
  ) then
    alter table usage_events
    add constraint usage_events_event_type_chk
    check (event_type in (
      'llm_call',
      't2i_generation',
      'r2_upload',
      'r2_storage_added',
      'r2_storage_removed',
      'modal_gpu_runtime'
    ));
  end if;

  if not exists (
    select 1 from pg_constraint where conname = 'usage_events_unit_chk'
  ) then
    alter table usage_events
    add constraint usage_events_unit_chk
    check (unit in ('call', 'image', 'byte', 'second'));
  end if;

  if not exists (
    select 1 from pg_constraint where conname = 'usage_events_plan_chk'
  ) then
    alter table usage_events
    add constraint usage_events_plan_chk
    check (plan is null or plan in ('free', 'economic', 'premium', 'internal_benchmark'));
  end if;
end $$;

create unique index if not exists usage_events_workspace_idempotency_key_idx
on usage_events (workspace_id, idempotency_key)
where idempotency_key is not null;

create index if not exists usage_events_workspace_user_created_idx
on usage_events (workspace_id, created_by, created_at desc);

create index if not exists usage_events_workspace_type_created_idx
on usage_events (workspace_id, event_type, created_at desc);

create index if not exists usage_events_job_created_idx
on usage_events (job_id, created_at desc);
