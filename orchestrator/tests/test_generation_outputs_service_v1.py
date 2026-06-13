import pytest
from unittest.mock import MagicMock
from orchestrator.app.generation_outputs.service import select_final_generation_output, get_generation_output, list_generation_outputs
from orchestrator.app.archive.service import ArchivePersistenceUnavailable
from orchestrator.tests.factories.generation_jobs import DEFAULT_WORKSPACE_ID


def _generation_output_row(**overrides):
    row = {
        "id": "uuid1",
        "public_output_id": "out1",
        "public_job_id": "job1",
        "job_id": "internal_job1",
        "workspace_id": DEFAULT_WORKSPACE_ID,
    }
    row.update(overrides)
    return row

def test_select_final_generation_output_transaction(monkeypatch):
    mock_row = _generation_output_row()
    
    repo_mock = MagicMock()
    repo_mock.get_generation_output_by_public_id.return_value = mock_row
    repo_mock.mark_output_final.return_value = {"id": "uuid1"}
    monkeypatch.setattr("orchestrator.app.generation_outputs.service.output_repo", repo_mock)
    
    sync_mock = MagicMock()
    monkeypatch.setattr("orchestrator.app.generation_outputs.service.sync_archive_for_output", sync_mock)
    
    db_tx_mock = MagicMock()
    db_tx_mock.return_value.__enter__.return_value = MagicMock()
    monkeypatch.setattr("orchestrator.app.generation_outputs.service.db_transaction", db_tx_mock)
    
    res = select_final_generation_output("out1", workspace_id=DEFAULT_WORKSPACE_ID)
    
    repo_mock.mark_output_final.assert_called_once()
    sync_mock.assert_called_once()
    assert res.output_id == "out1"

def test_generation_output_no_uuid_fallback(monkeypatch):
    mock_row = _generation_output_row(public_output_id=None)
    repo_mock = MagicMock()
    repo_mock.get_generation_output_by_public_id.return_value = mock_row
    monkeypatch.setattr("orchestrator.app.generation_outputs.service.output_repo", repo_mock)
    
    from orchestrator.app.generation_outputs.service import GenerationOutputPersistenceUnavailable
    with pytest.raises(GenerationOutputPersistenceUnavailable):
        get_generation_output("out1", workspace_id="ws1")
