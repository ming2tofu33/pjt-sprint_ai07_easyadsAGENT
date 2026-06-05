create table if not exists public.admin_users (
  user_id uuid primary key references auth.users(id) on delete cascade,
  email text not null,
  role text not null default 'admin' check (role in ('owner', 'admin', 'editor')),
  active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists admin_users_active_role_idx
on public.admin_users (active, role)
where active = true;

alter table public.admin_users enable row level security;

drop policy if exists "admin users can read own active record" on public.admin_users;
create policy "admin users can read own active record"
on public.admin_users
for select
to authenticated
using (user_id = auth.uid() and active = true);
