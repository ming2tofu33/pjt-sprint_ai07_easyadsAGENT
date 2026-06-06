-- Add public_output_id to generation_outputs
alter table generation_outputs
add column if not exists public_output_id text;

update generation_outputs
set public_output_id = 'output_' || replace(gen_random_uuid()::text, '-', '')
where public_output_id is null;

alter table generation_outputs
    alter column public_output_id set not null,
    alter column public_output_id set default ('output_' || replace(gen_random_uuid()::text, '-', ''));

create unique index if not exists generation_outputs_public_output_id_unique_idx
on generation_outputs (public_output_id);

-- Add public_archive_id to archive_items
alter table archive_items
add column if not exists public_archive_id text;

update archive_items
set public_archive_id = 'archive_' || replace(gen_random_uuid()::text, '-', '')
where public_archive_id is null;

alter table archive_items
    alter column public_archive_id set not null,
    alter column public_archive_id set default ('archive_' || replace(gen_random_uuid()::text, '-', ''));

create unique index if not exists archive_items_public_archive_id_unique_idx
on archive_items (public_archive_id);
