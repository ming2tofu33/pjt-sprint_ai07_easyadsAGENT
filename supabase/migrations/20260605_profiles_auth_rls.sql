create extension if not exists pgcrypto;

create table if not exists public.profiles (
  id uuid primary key default gen_random_uuid(),
  user_id text unique,
  email text,
  display_name text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.profiles enable row level security;

drop policy if exists "profiles can read own record" on public.profiles;
create policy "profiles can read own record"
on public.profiles
for select
to authenticated
using (user_id = auth.uid()::text);

drop policy if exists "profiles can insert own record" on public.profiles;
create policy "profiles can insert own record"
on public.profiles
for insert
to authenticated
with check (user_id = auth.uid()::text);

drop policy if exists "profiles can update own record" on public.profiles;
create policy "profiles can update own record"
on public.profiles
for update
to authenticated
using (user_id = auth.uid()::text)
with check (user_id = auth.uid()::text);
