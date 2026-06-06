import pytest
from unittest.mock import MagicMock
from orchestrator.app.archive.service import create_archive_item, ArchiveInvalidGeneratedSource, ArchiveGenerationOutputNotReady
from orchestrator.app.api.schemas.archive import ArchiveItemCreateRequest

def test_archive_invalid_generated_source(monkeypatch):
    monkeypatch.setattr("orchestrator.app.archive.service._ensure_postgres_enabled", lambda: None)
    monkeypatch.setattr("orchestrator.app.archive.service._resolve_workspace_id", lambda *a, **k: "ws1")
    
    req = ArchiveItemCreateRequest(
        title="test",
        source="generated",
        public_job_id=None,
    )
    
    with pytest.raises(ArchiveInvalidGeneratedSource):
        create_archive_item(req)

def test_archive_generation_output_not_ready(monkeypatch):
    monkeypatch.setattr("orchestrator.app.archive.service._ensure_postgres_enabled", lambda: None)
    monkeypatch.setattr("orchestrator.app.archive.service._resolve_workspace_id", lambda *a, **k: "ws1")
    
    mock_job_repo = MagicMock()
    mock_job_repo.get_generation_job_db.return_value = None
    monkeypatch.setattr("orchestrator.app.archive.service.job_repo", mock_job_repo)
    
    req = ArchiveItemCreateRequest(
        title="test",
        source="generated",
        public_job_id="job1",
    )
    
    with pytest.raises(ArchiveGenerationOutputNotReady):
        create_archive_item(req)

def test_done_does_not_ignore_archive_sync_failure(monkeypatch):
    from orchestrator.app.generation_jobs.service import _create_output_records_for_done_job_db
    
    monkeypatch.setattr("orchestrator.app.generation_jobs.service.generation_job_repo.update_generation_job_row", lambda *args, **kwargs: row)
    monkeypatch.setattr("orchestrator.app.generation_jobs.service.asset_repo.create_asset", lambda *args, **kwargs: {"id": "asset1"})
    monkeypatch.setattr("orchestrator.app.generation_jobs.service.generation_output_repo.create_generation_output", lambda *args, **kwargs: {"id": "out1", "public_output_id": "out1"})
    monkeypatch.setattr("orchestrator.app.generation_jobs.service.generation_output_repo.mark_output_final", lambda *args, **kwargs: {"id": "out1"})
    monkeypatch.setattr("orchestrator.app.generation_jobs.service._record_generation_job_event_db", MagicMock())
    
    def mock_sync(*args, **kwargs):
        raise RuntimeError("Archive sync failed")
        
    monkeypatch.setattr("orchestrator.app.archive.service.sync_archive_for_output", mock_sync)
    
    row = {"id": "1", "workspace_id": "ws1", "public_job_id": "pub1", "thread_id": "th1", "requested_by": "u1"}
    output = {"id": "out1", "public_output_id": "public_out1"}
    
    with pytest.raises(RuntimeError, match="Archive sync failed"):
        _create_output_records_for_done_job_db(row, output, "fake/path", connection=MagicMock())

def test_select_final_rolls_back_when_archive_sync_fails(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")
    
    from contextlib import contextmanager
    @contextmanager
    def fake_db_transaction(*args, **kwargs):
        conn = MagicMock()
        yield conn
    monkeypatch.setattr("orchestrator.app.generation_outputs.service.db_transaction", fake_db_transaction)
    
    from orchestrator.app.generation_outputs.service import select_final_generation_output
    
    mock_repo = MagicMock()
    mock_repo.get_generation_output_by_public_id.return_value = {"id": "1"}
    mock_repo.mark_output_final.return_value = {"id": "1"}
    monkeypatch.setattr("orchestrator.app.generation_outputs.service.output_repo", mock_repo)
    
    def mock_sync(*args, **kwargs):
        raise RuntimeError("Archive sync failed")
        
    monkeypatch.setattr("orchestrator.app.archive.service.sync_archive_for_output", mock_sync)
    
    with pytest.raises(RuntimeError, match="Archive sync failed"):
        select_final_generation_output("out1", workspace_id="ws1")
