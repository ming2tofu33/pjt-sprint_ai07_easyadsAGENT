from orchestrator.app.archive import service as archive_service


def test_list_archive_items_can_skip_exact_count(monkeypatch):
    calls = {}

    monkeypatch.setattr(archive_service, "_ensure_postgres_enabled", lambda: None)
    monkeypatch.setattr(archive_service, "_resolve_user_id", lambda user_id=None: user_id)
    monkeypatch.setattr(archive_service, "_resolve_workspace_id", lambda workspace_id=None, **_: workspace_id or "workspace_uuid")

    def fake_list_archive_item_rows(*, workspace_id, created_by=None, limit=50, offset=0):
        calls["list"] = {
            "workspace_id": workspace_id,
            "created_by": created_by,
            "limit": limit,
            "offset": offset,
        }
        return [
            {
                "public_archive_id": "archive_1",
                "title": "첫 번째 광고",
                "thumbnail_public_url": "https://cdn.example.com/thumb-1.png",
                "status": "saved",
                "source": "generated",
            },
            {
                "public_archive_id": "archive_2",
                "title": "두 번째 광고",
                "thumbnail_public_url": "https://cdn.example.com/thumb-2.png",
                "status": "saved",
                "source": "generated",
            },
        ]

    def fail_count_archive_item_rows(**_kwargs):
        raise AssertionError("count query should be skipped")

    monkeypatch.setattr(archive_service.archive_item_repo, "list_archive_item_rows", fake_list_archive_item_rows)
    monkeypatch.setattr(archive_service.archive_item_repo, "count_archive_item_rows", fail_count_archive_item_rows)

    items, total = archive_service.list_archive_items(
        workspace_id="workspace_uuid",
        user_id="user_1",
        limit=1,
        offset=0,
        include_total=False,
    )

    assert [item.ad_id for item in items] == ["archive_1"]
    assert total == 2
    assert calls["list"] == {
        "workspace_id": "workspace_uuid",
        "created_by": "user_1",
        "limit": 2,
        "offset": 0,
    }
