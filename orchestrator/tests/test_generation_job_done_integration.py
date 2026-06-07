"""GenerationJob 완료 시 Output/Archive 연결 통합 테스트 (Section 11.4 요구사항)."""

import pytest
from unittest.mock import MagicMock
from contextlib import contextmanager


# ---------------------------------------------------------------------------
# _create_output_records_for_done_job_db: Asset→Output→Final→Archive 순서
# ---------------------------------------------------------------------------

@pytest.fixture
def patched_done_job(monkeypatch):
    """R2 업로드 없이 _create_output_records_for_done_job_db를 실행할 수 있도록 patch."""
    call_order = []

    monkeypatch.setattr(
        "orchestrator.app.generation_jobs.service._should_attempt_r2_upload",
        lambda: False,
    )

    def mock_create_asset(*args, **kwargs):
        call_order.append("create_asset")
        return {"id": "asset_uuid", "storage_provider": "local_dev"}

    monkeypatch.setattr(
        "orchestrator.app.generation_jobs.service.asset_repo.create_asset",
        mock_create_asset,
    )

    def mock_create_output(*args, **kwargs):
        call_order.append("create_output")
        return {"id": "output_uuid", "public_output_id": "out_pub_1"}

    monkeypatch.setattr(
        "orchestrator.app.generation_jobs.service.generation_output_repo.create_generation_output",
        mock_create_output,
    )

    def mock_mark_final(*args, **kwargs):
        call_order.append("mark_final")
        return {"id": "output_uuid", "is_final": True}

    monkeypatch.setattr(
        "orchestrator.app.generation_jobs.service.generation_output_repo.mark_output_final",
        mock_mark_final,
    )

    def mock_sync_archive(*args, **kwargs):
        call_order.append("archive_sync")

    monkeypatch.setattr(
        "orchestrator.app.generation_jobs.service.archive_service.sync_archive_for_output",
        mock_sync_archive,
    )

    def mock_update_job(*args, **kwargs):
        call_order.append("update_job")
        return None

    monkeypatch.setattr(
        "orchestrator.app.generation_jobs.service.generation_job_repo.update_generation_job_row",
        mock_update_job,
    )

    monkeypatch.setattr(
        "orchestrator.app.generation_jobs.service._record_generation_job_event_db",
        MagicMock(),
    )
    monkeypatch.setattr(
        "orchestrator.app.artifacts.service.merge_final_asset_into_result_payload",
        lambda **kwargs: kwargs.get("result_payload", {}),
    )

    return call_order


def test_done_job_execution_order(patched_done_job):
    """Asset → Output → Final → Archive 순서로 실행."""
    from orchestrator.app.generation_jobs.service import _create_output_records_for_done_job_db

    row = {
        "id": "job_uuid",
        "workspace_id": "ws1",
        "thread_id": "th1",
        "public_job_id": "pub1",
        "requested_by": "u1",
    }
    result_payload = {"final_image_path": "data/outputs/pub1/final.png"}

    output, _ = _create_output_records_for_done_job_db(
        row, result_payload, "data/outputs/pub1/final.png", connection=MagicMock()
    )

    assert "create_asset" in patched_done_job
    assert "create_output" in patched_done_job
    assert "mark_final" in patched_done_job
    assert "archive_sync" in patched_done_job

    idx = {step: patched_done_job.index(step) for step in ["create_asset", "create_output", "mark_final", "archive_sync"]}
    assert idx["create_asset"] < idx["create_output"]
    assert idx["create_output"] < idx["mark_final"]
    assert idx["mark_final"] < idx["archive_sync"]


def test_done_job_no_path_returns_none_output(monkeypatch):
    """final_path가 없으면 output None 반환 (early exit)."""
    from orchestrator.app.generation_jobs.service import _create_output_records_for_done_job_db

    row = {
        "id": "job_uuid",
        "workspace_id": "ws1",
        "thread_id": "th1",
        "public_job_id": "pub1",
        "requested_by": "u1",
    }

    output, _ = _create_output_records_for_done_job_db(
        row, {}, None, connection=MagicMock()
    )
    assert output is None


def test_done_job_archive_failure_propagates(patched_done_job, monkeypatch):
    """Archive sync 실패 시 예외 전파 (best-effort 아님)."""
    from orchestrator.app.generation_jobs.service import _create_output_records_for_done_job_db

    def fail_sync(*args, **kwargs):
        raise RuntimeError("Archive DB error")

    monkeypatch.setattr(
        "orchestrator.app.generation_jobs.service.archive_service.sync_archive_for_output",
        fail_sync,
    )

    row = {
        "id": "job_uuid",
        "workspace_id": "ws1",
        "thread_id": "th1",
        "public_job_id": "pub1",
        "requested_by": "u1",
    }

    with pytest.raises(RuntimeError, match="Archive DB error"):
        _create_output_records_for_done_job_db(
            row, {"final_image_path": "data/outputs/pub1/final.png"},
            "data/outputs/pub1/final.png",
            connection=MagicMock(),
        )


# ---------------------------------------------------------------------------
# Archive upsert idempotency: ON CONFLICT 활용
# ---------------------------------------------------------------------------

def test_upsert_generated_archive_item_uses_on_conflict(monkeypatch):
    """동일 workspace+public_job_id로 upsert하면 기존 row 갱신 (중복 생성 안 됨)."""
    from orchestrator.app.db.repositories import archive_items as repo

    @contextmanager
    def fake_tx(connection=None):
        yield connection

    monkeypatch.setattr(repo, "db_transaction", fake_tx)

    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    cur.fetchone.return_value = {
        "id": "archive_uuid",
        "public_archive_id": "archive_pub_1",
        "public_job_id": "job_1",
    }

    repo.upsert_generated_archive_item_row(
        workspace_id="ws1",
        public_job_id="job_1",
        created_by="u1",
        title="광고 1",
        job_id="job_uuid",
        output_id="out_uuid",
        connection=conn,
    )

    sql, _ = cur.execute.call_args_list[0]
    assert "on conflict" in sql[0].lower()
    assert "do update set" in sql[0].lower()


# ---------------------------------------------------------------------------
# mark_generation_job_done_db idempotency
# ---------------------------------------------------------------------------

def test_mark_generation_job_done_db_idempotent(monkeypatch):
    """완료 callback 중복 호출 시 stale_completion_ignored 처리되며 output 생성을 중복하지 않음."""
    from orchestrator.app.generation_jobs.service import _mark_generation_job_done_db
    import orchestrator.app.generation_jobs.service as job_svc

    # 1. Fake DB Transaction
    @contextmanager
    def fake_tx(connection=None):
        yield connection

    monkeypatch.setattr(job_svc, "db_transaction", fake_tx)

    # 2. Mock _create_output_records_for_done_job_db (호출 횟수 측정용)
    mock_create_records = MagicMock(return_value=({"id": "output_1"}, {"final_image_path": "foo.png"}))
    monkeypatch.setattr(job_svc, "_create_output_records_for_done_job_db", mock_create_records)

    # 3. Mock Repositories
    mock_job_repo = MagicMock()
    mock_thread_repo = MagicMock()
    
    # job이 이미 done 상태라고 가정 (existing_status="done")
    mock_job_repo.get_generation_job_row.return_value = {
        "id": "job_uuid_1",
        "public_job_id": "job_pub_1",
        "workspace_id": "ws1",
        "status": "done",
        "thread_id": "thread_uuid_1",
        "public_thread_id": "thread_pub_1",
        "created_at": "2026-06-07T00:00:00Z",
        "updated_at": "2026-06-07T00:00:00Z",
        "metadata": {}
    }

    # thread는 active_job_id가 다른 값(혹은 None)으로 풀려있다고 가정 (stale 상태)
    mock_thread_repo.get_chat_thread_by_public_id.return_value = {
        "id": "thread_uuid_1",
        "active_job_id": None
    }

    monkeypatch.setattr(job_svc, "generation_job_repo", mock_job_repo)
    monkeypatch.setattr(job_svc, "chat_thread_repo", mock_thread_repo)

    mock_record_event = MagicMock()
    monkeypatch.setattr(job_svc, "_record_generation_job_event_db", mock_record_event)

    # Execute
    res = _mark_generation_job_done_db("job_uuid_1", "ws1", {"some": "payload"})

    # Check
    # Output create (Asset/Archive 등 포함하는 helper) 함수는 호출되지 않아야 함
    mock_create_records.assert_not_called()

    # _record_generation_job_event_db는 stale_completion_ignored 로 불려야 함
    mock_record_event.assert_called_once()
    event_type = mock_record_event.call_args[0][1]
    assert event_type == "stale_completion_ignored"
