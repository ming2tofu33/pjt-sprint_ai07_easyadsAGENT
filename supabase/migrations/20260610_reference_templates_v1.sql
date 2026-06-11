create table if not exists public.reference_templates (
  id uuid primary key default gen_random_uuid(),
  template_id text not null unique,
  title text not null,
  description text,
  category text not null,
  sub_category text,
  tags text[] not null default '{}',
  business_types text[] not null default '{}',
  ad_formats text[] not null default '{}',
  platforms text[] not null default '{}',
  aspect_ratio text,
  width integer,
  height integer,
  asset_public_id text references public.assets(public_asset_id) on delete set null,
  thumbnail_url text,
  preview_url text,
  source_image_path text,
  style_keywords text[] not null default '{}',
  color_palette text[] not null default '{}',
  layout_hint text,
  typography_hint text,
  background_style text,
  popularity_score numeric not null default 0,
  status text not null default 'draft' check (status in ('active', 'inactive', 'draft')),
  source text not null default 'admin_upload',
  license_note text,
  metadata jsonb not null default '{}'::jsonb,
  created_by text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  deleted_at timestamptz
);

create index if not exists reference_templates_status_created_at_idx
on public.reference_templates (status, created_at desc)
where deleted_at is null;

create index if not exists reference_templates_category_status_idx
on public.reference_templates (category, status)
where deleted_at is null;
