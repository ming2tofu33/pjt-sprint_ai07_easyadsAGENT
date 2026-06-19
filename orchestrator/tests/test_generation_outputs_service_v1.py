from unittest.mock import MagicMock

import pytest

from orchestrator.app.archive.service import ArchivePersistenceUnavailable
from orchestrator.app.generation_outputs.service import (
    GenerationOutputNotFound,
    _row_to_response,
    get_generation_output,
    list_generation_outputs,
    select_final_generation_output,
)
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
    repo_mock.get_generation_output_by_public_id.side_effect = [mock_row, mock_row]
    repo_mock.mark_output_final.return_value = {"id": "uuid1"}
    monkeypatch.setattr("orchestrator.app.generation_outputs.service.output_repo", repo_mock)

    sync_mock = MagicMock()
    monkeypatch.setattr("orchestrator.app.generation_outputs.service.sync_archive_for_output", sync_mock)

    tx_conn = MagicMock()
    db_tx_mock = MagicMock()
    db_tx_mock.return_value.__enter__.return_value = tx_conn
    monkeypatch.setattr("orchestrator.app.generation_outputs.service.db_transaction", db_tx_mock)

    res = select_final_generation_output("out1", workspace_id=DEFAULT_WORKSPACE_ID)

    assert res.output_id == "out1"
    assert res.job_id == "job1"
    assert res.model_dump().get("id") is None
    assert repo_mock.get_generation_output_by_public_id.call_args_list[0].kwargs == {
        "public_output_id": "out1",
        "workspace_id": DEFAULT_WORKSPACE_ID,
        "connection": tx_conn,
    }
    repo_mock.mark_output_final.assert_called_once_with(
        output_id="uuid1",
        workspace_id=DEFAULT_WORKSPACE_ID,
        connection=tx_conn,
    )
    sync_mock.assert_called_once_with(
        workspace_id=DEFAULT_WORKSPACE_ID,
        internal_output_id="uuid1",
        connection=tx_conn,
    )
    assert repo_mock.get_generation_output_by_public_id.call_args_list[1].kwargs == {
        "public_output_id": "out1",
        "workspace_id": DEFAULT_WORKSPACE_ID,
        "connection": tx_conn,
    }


def test_generation_output_no_uuid_fallback(monkeypatch):
    mock_row = _generation_output_row(public_output_id=None)
    repo_mock = MagicMock()
    repo_mock.get_generation_output_by_public_id.return_value = mock_row
    monkeypatch.setattr("orchestrator.app.generation_outputs.service.output_repo", repo_mock)

    from orchestrator.app.generation_outputs.service import GenerationOutputPersistenceUnavailable

    with pytest.raises(GenerationOutputPersistenceUnavailable):
        get_generation_output("out1", workspace_id="ws1")


@pytest.mark.parametrize("payload", [None, [], "invalid", 7])
def test_generation_output_normalizes_malformed_result_payload(payload):
    response = _row_to_response(_generation_output_row(result_payload=payload))

    assert response.result_payload == {}
    assert response.download_url is None
    assert response.image_url is None


def test_generation_output_handles_none_from_sanitizer(monkeypatch):
    monkeypatch.setattr(
        "orchestrator.app.generation_outputs.service.sanitize_result_artifact_payload_for_api",
        lambda payload: None,
    )

    response = _row_to_response(_generation_output_row(result_payload={"download_url": "https://example.com/image.png"}))

    assert response.result_payload == {}
    assert response.download_url is None


def test_generation_output_payload_does_not_expose_internal_or_binary_fields():
    response = _row_to_response(
        _generation_output_row(
            result_payload={
                "download_url": "https://example.com/image.png",
                "object_key": "private/result.png",
                "local_path": "data/outputs/job/result.png",
                "base64": "encoded",
                "b64_json": "encoded",
                "raw_image": b"binary",
                "nested": {"object_key": "private/nested.png"},
            }
        )
    )

    assert response.download_url == "https://example.com/image.png"
    assert response.result_payload == {
        "download_url": "https://example.com/image.png",
        "nested": {},
    }


def test_generation_output_lookup_is_scoped_to_requested_workspace(monkeypatch):
    repo_mock = MagicMock()
    repo_mock.get_generation_output_by_public_id.return_value = None
    monkeypatch.setattr("orchestrator.app.generation_outputs.service.output_repo", repo_mock)

    with pytest.raises(GenerationOutputNotFound):
        get_generation_output("out_other_workspace", workspace_id="workspace_a")

    repo_mock.get_generation_output_by_public_id.assert_called_once_with(
        public_output_id="out_other_workspace",
        workspace_id="workspace_a",
    )
