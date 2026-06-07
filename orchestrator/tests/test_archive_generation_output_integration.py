import pytest
from unittest.mock import MagicMock
from orchestrator.app.archive.service import (
    create_archive_item,
    ArchiveInvalidGeneratedSource,
    ArchiveGenerationOutputNotReady,
    ArchiveItemNotFound,
)
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

def test_archive_generation_job_not_found(monkeypatch):
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
    
    with pytest.raises(ArchiveItemNotFound):
        create_archive_item(req)

def test_archive_generation_output_not_ready(monkeypatch):
    monkeypatch.setattr("orchestrator.app.archive.service._ensure_postgres_enabled", lambda: None)
    monkeypatch.setattr("orchestrator.app.archive.service._resolve_workspace_id", lambda *a, **k: "ws1")
    
    mock_job_repo = MagicMock()
    mock_job_repo.get_generation_job_db.return_value = {
        "id": "job_uuid",
        "public_job_id": "job1",
    }
    monkeypatch.setattr("orchestrator.app.archive.service.job_repo", mock_job_repo)
    
    monkeypatch.setattr(
        "orchestrator.app.archive.service.sync_archive_for_job",
        lambda *a, **k: (_ for _ in ()).throw(
            ArchiveGenerationOutputNotReady("Final output not ready")
        ),
    )
    
    req = ArchiveItemCreateRequest(
        title="test",
        source="generated",
        public_job_id="job1",
    )
    
    with pytest.raises(ArchiveGenerationOutputNotReady):
        create_archive_item(req)

def test_done_does_not_ignore_archive_sync_failure(monkeypatch):
    """Archive sync 실패 시 _create_output_records_for_done_job_db가 예외를 전파해야 함."""
    from orchestrator.app.generation_jobs.service import _create_output_records_for_done_job_db

    # R2 업로드 비활성화 (local asset 경로로 진행)
    monkeypatch.setattr("orchestrator.app.generation_jobs.service._should_attempt_r2_upload", lambda: False)
    monkeypatch.setattr(
        "orchestrator.app.generation_jobs.service.asset_repo.create_asset",
        lambda *args, **kwargs: {"id": "asset1", "storage_provider": "local_dev"},
    )
    monkeypatch.setattr(
        "orchestrator.app.generation_jobs.service.generation_output_repo.create_generation_output",
        lambda *args, **kwargs: {"id": "out1", "public_output_id": "public_out1"},
    )
    monkeypatch.setattr(
        "orchestrator.app.generation_jobs.service.generation_output_repo.mark_output_final",
        lambda *args, **kwargs: {"id": "out1"},
    )
    monkeypatch.setattr(
        "orchestrator.app.generation_jobs.service.generation_job_repo.update_generation_job_row",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "orchestrator.app.generation_jobs.service._record_generation_job_event_db",
        MagicMock(),
    )
    monkeypatch.setattr(
        "orchestrator.app.artifacts.service.merge_final_asset_into_result_payload",
        lambda **kwargs: kwargs.get("result_payload", {}),
    )

    def mock_sync(*args, **kwargs):
        raise RuntimeError("Archive sync failed")

    # archive_service 모듈 attribute로 참조하므로, 해당 경로로 patch
    monkeypatch.setattr("orchestrator.app.generation_jobs.service.archive_service.sync_archive_for_output", mock_sync)

    row = {"id": "1", "workspace_id": "ws1", "public_job_id": "pub1", "thread_id": "th1", "requested_by": "u1"}
    result_payload = {"final_image_path": "data/outputs/pub1/final.png"}

    with pytest.raises(RuntimeError, match="Archive sync failed"):
        _create_output_records_for_done_job_db(row, result_payload, "data/outputs/pub1/final.png", connection=MagicMock())

