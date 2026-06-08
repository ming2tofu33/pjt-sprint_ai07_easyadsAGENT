create extension if not exists pgcrypto;

alter table usage_events
add column if not exists idempotency_key text;

alter table usage_events
alter column quantity set default 1;

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
