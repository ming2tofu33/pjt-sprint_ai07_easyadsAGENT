-- Enable tenant row-level security for workspace-scoped application tables.
-- The helper avoids recursive RLS checks between workspaces and workspace_members.

create or replace function public.easyads_has_workspace_access(target_workspace_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select auth.uid() is not null
    and exists (
      select 1
      from public.workspaces w
      where w.id = target_workspace_id
        and (
          w.owner_user_id = auth.uid()::text
          or exists (
            select 1
            from public.workspace_members wm
            where wm.workspace_id = target_workspace_id
              and wm.user_id = auth.uid()::text
          )
        )
    );
$$;

revoke all on function public.easyads_has_workspace_access(uuid) from public;
grant execute on function public.easyads_has_workspace_access(uuid) to authenticated;

alter table if exists public.workspaces enable row level security;
drop policy if exists "workspaces_workspace_isolation" on public.workspaces;
create policy "workspaces_workspace_isolation"
on public.workspaces
for all
to authenticated
using (public.easyads_has_workspace_access(id))
with check (
  owner_user_id = auth.uid()::text
  or public.easyads_has_workspace_access(id)
);

alter table if exists public.workspace_members enable row level security;
drop policy if exists "workspace_members_workspace_isolation" on public.workspace_members;
create policy "workspace_members_workspace_isolation"
on public.workspace_members
for all
to authenticated
using (public.easyads_has_workspace_access(workspace_id))
with check (public.easyads_has_workspace_access(workspace_id));

alter table if exists public.projects enable row level security;
drop policy if exists "projects_workspace_isolation" on public.projects;
create policy "projects_workspace_isolation"
on public.projects
for all
to authenticated
using (public.easyads_has_workspace_access(workspace_id))
with check (public.easyads_has_workspace_access(workspace_id));

alter table if exists public.brand_kits enable row level security;
drop policy if exists "brand_kits_workspace_isolation" on public.brand_kits;
create policy "brand_kits_workspace_isolation"
on public.brand_kits
for all
to authenticated
using (public.easyads_has_workspace_access(workspace_id))
with check (public.easyads_has_workspace_access(workspace_id));

alter table if exists public.chat_threads enable row level security;
drop policy if exists "chat_threads_workspace_isolation" on public.chat_threads;
create policy "chat_threads_workspace_isolation"
on public.chat_threads
for all
to authenticated
using (public.easyads_has_workspace_access(workspace_id))
with check (public.easyads_has_workspace_access(workspace_id));

alter table if exists public.chat_messages enable row level security;
drop policy if exists "chat_messages_workspace_isolation" on public.chat_messages;
create policy "chat_messages_workspace_isolation"
on public.chat_messages
for all
to authenticated
using (public.easyads_has_workspace_access(workspace_id))
with check (public.easyads_has_workspace_access(workspace_id));

alter table if exists public.assets enable row level security;
drop policy if exists "assets_workspace_isolation" on public.assets;
create policy "assets_workspace_isolation"
on public.assets
for all
to authenticated
using (public.easyads_has_workspace_access(workspace_id))
with check (public.easyads_has_workspace_access(workspace_id));

alter table if exists public.chat_message_assets enable row level security;
drop policy if exists "chat_message_assets_workspace_isolation" on public.chat_message_assets;
create policy "chat_message_assets_workspace_isolation"
on public.chat_message_assets
for all
to authenticated
using (public.easyads_has_workspace_access(workspace_id))
with check (public.easyads_has_workspace_access(workspace_id));

alter table if exists public.generation_jobs enable row level security;
drop policy if exists "generation_jobs_workspace_isolation" on public.generation_jobs;
create policy "generation_jobs_workspace_isolation"
on public.generation_jobs
for all
to authenticated
using (public.easyads_has_workspace_access(workspace_id))
with check (public.easyads_has_workspace_access(workspace_id));

alter table if exists public.generation_outputs enable row level security;
drop policy if exists "generation_outputs_workspace_isolation" on public.generation_outputs;
create policy "generation_outputs_workspace_isolation"
on public.generation_outputs
for all
to authenticated
using (public.easyads_has_workspace_access(workspace_id))
with check (public.easyads_has_workspace_access(workspace_id));

alter table if exists public.generation_job_events enable row level security;
drop policy if exists "generation_job_events_workspace_isolation" on public.generation_job_events;
create policy "generation_job_events_workspace_isolation"
on public.generation_job_events
for all
to authenticated
using (public.easyads_has_workspace_access(workspace_id))
with check (public.easyads_has_workspace_access(workspace_id));

alter table if exists public.archive_items enable row level security;
drop policy if exists "archive_items_workspace_isolation" on public.archive_items;
create policy "archive_items_workspace_isolation"
on public.archive_items
for all
to authenticated
using (public.easyads_has_workspace_access(workspace_id))
with check (public.easyads_has_workspace_access(workspace_id));

alter table if exists public.usage_events enable row level security;
drop policy if exists "usage_events_workspace_isolation" on public.usage_events;
create policy "usage_events_workspace_isolation"
on public.usage_events
for all
to authenticated
using (public.easyads_has_workspace_access(workspace_id))
with check (public.easyads_has_workspace_access(workspace_id));

alter table if exists public.feedback_events enable row level security;
drop policy if exists "feedback_events_workspace_isolation" on public.feedback_events;
create policy "feedback_events_workspace_isolation"
on public.feedback_events
for all
to authenticated
using (public.easyads_has_workspace_access(workspace_id))
with check (public.easyads_has_workspace_access(workspace_id));

alter table if exists public.chat_state_snapshots enable row level security;
drop policy if exists "chat_state_snapshots_workspace_isolation" on public.chat_state_snapshots;
create policy "chat_state_snapshots_workspace_isolation"
on public.chat_state_snapshots
for all
to authenticated
using (public.easyads_has_workspace_access(workspace_id))
with check (public.easyads_has_workspace_access(workspace_id));

alter table if exists public.validation_reports enable row level security;
drop policy if exists "validation_reports_workspace_isolation" on public.validation_reports;
create policy "validation_reports_workspace_isolation"
on public.validation_reports
for all
to authenticated
using (public.easyads_has_workspace_access(workspace_id))
with check (public.easyads_has_workspace_access(workspace_id));
