-- Add public_asset_id to assets table for external reference
alter table assets add column public_asset_id text;

-- Backfill existing rows with random asset_ IDs
update assets
set public_asset_id = 'asset_' || replace(gen_random_uuid()::text, '-', '')
where public_asset_id is null;

-- Enforce constraints
alter table assets alter column public_asset_id set not null;
alter table assets add constraint assets_public_asset_id_key unique (public_asset_id);

-- Add index for fast lookup
create index if not exists assets_public_asset_id_idx on assets(public_asset_id);

-- Enforce size and status constraints
alter table assets add constraint assets_size_bytes_check check (size_bytes is null or size_bytes > 0);
alter table assets add constraint assets_upload_status_check check (
    metadata is null or
    metadata->'upload' is null or
    metadata->'upload'->>'status' is null or
    metadata->'upload'->>'status' in ('pending', 'ready', 'failed')
);
