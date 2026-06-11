-- Speed up user-scoped archive lists ordered by recent saved items.
create index if not exists archive_items_workspace_created_by_saved_idx
on archive_items (workspace_id, created_by, saved_at desc)
where deleted_at is null;
