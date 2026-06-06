import pytest
from unittest.mock import MagicMock
from orchestrator.app.archive.service import sync_archive_for_job

def test_sync_archive_for_job_success(monkeypatch):
    mock_job = {
        "id": "job_uuid",
        "thread_id": "thread_uuid",
        "public_job_id": "job_public",
        "requested_by": "user1",
        "brief": {"item_or_service": "Cool product"},
    }
    
    mock_thread = {
        "id": "thread_uuid",
        "title": "Thread Title",
    }
    
    mock_outputs = [{
        "id": "output_uuid",
        "asset_id": "asset_uuid",
        "image_url": "local/image.png",
        "thumbnail_url": "local/thumb.png",
    }]
    
    mock_archive_row = {
        "public_archive_id": "archive_public",
        "id": "archive_uuid"
    }

    job_repo_mock = MagicMock()
    job_repo_mock.get_generation_job_db_by_id.return_value = mock_job
    monkeypatch.setattr("orchestrator.app.archive.service.job_repo", job_repo_mock)
    
    thread_repo_mock = MagicMock()
    thread_repo_mock.get_chat_thread.return_value = mock_thread
    monkeypatch.setattr("orchestrator.app.archive.service.thread_repo", thread_repo_mock)
    
    output_repo_mock = MagicMock()
    output_repo_mock.return_value = mock_outputs
    monkeypatch.setattr("orchestrator.app.db.repositories.generation_outputs.list_generation_outputs", output_repo_mock)
    
    archive_repo_mock = MagicMock()
    archive_repo_mock.upsert_generated_archive_item_row.return_value = mock_archive_row
    
    archive_repo_mock.get_archive_item_row.return_value = {
        **mock_archive_row,
        "workspace_id": "ws1",
        "title": "Thread Title",
        "j_public_job_id": "job_public",
        "public_output_id": "out_public",
        "public_thread_id": "thread_public",
    }
    monkeypatch.setattr("orchestrator.app.archive.service.archive_item_repo", archive_repo_mock)
    
    monkeypatch.setattr("orchestrator.app.archive.service._ensure_postgres_enabled", lambda: None)
    
    res = sync_archive_for_job(workspace_id="ws1", internal_job_id="job_uuid")
    
    assert res is not None
    assert res.title == "Thread Title"
    assert res.job_id == "job_public"
    
    archive_repo_mock.upsert_generated_archive_item_row.assert_called_once()
    called_kwargs = archive_repo_mock.upsert_generated_archive_item_row.call_args[1]
    assert called_kwargs["title"] == "Thread Title"
    assert called_kwargs["source"] == "generated"
    assert called_kwargs["output_id"] == "output_uuid"
