from orchestrator.app.usage import service


def test_r2_upload_usage_records_upload_and_storage_added_once(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "memory")
    service.reset_usage_store_for_tests()

    first = service.record_r2_upload_usage(
        workspace_id="ws1",
        quantity=1024,
        provider="cloudflare_r2",
        idempotency_key="asset-upload-1",
        metadata={"source": "test", "bucket": "hidden-bucket", "object_key": "workspaces/ws/x.png"},
    )
    second = service.record_r2_upload_usage(
        workspace_id="ws1",
        quantity=1024,
        provider="cloudflare_r2",
        idempotency_key="asset-upload-1",
        metadata={"source": "test"},
    )

    assert first[0]["id"] == second[0]["id"]
    assert first[1]["id"] == second[1]["id"]
    assert "bucket" not in first[0]["metadata"]
    assert "object_key" not in first[0]["metadata"]

    summary = service.get_usage_summary(workspace_id="ws1")
    assert summary["totals"]["r2UploadBytes"] == 1024
    assert summary["totals"]["r2StorageBytesAdded"] == 1024
