"""Consolidated tests (real physical merge of source files).

Merged from:
- orchestrator/tests/test_generation_job_actual_lanes.py
- orchestrator/tests/test_generation_job_asset_inputs.py
- orchestrator/tests/test_generation_job_db_repository.py
- orchestrator/tests/test_generation_job_done_integration.py
- orchestrator/tests/test_generation_job_events_repository.py
- orchestrator/tests/test_generation_job_execution_bridge.py
- orchestrator/tests/test_generation_job_flux_lane.py
- orchestrator/tests/test_generation_job_graph_execution.py
- orchestrator/tests/test_generation_job_message_linkage.py
- orchestrator/tests/test_generation_job_modal_execution.py
- orchestrator/tests/test_generation_job_persistence_db_backend.py
- orchestrator/tests/test_generation_job_r2_persistence.py
- orchestrator/tests/test_generation_job_run_mode_mapping.py
- orchestrator/tests/test_generation_job_service.py
- orchestrator/tests/test_generation_job_service_db_backend.py
- orchestrator/tests/test_generation_job_tenant_isolation.py
"""


# ===== from test_generation_job_actual_lanes.py =====
from pathlib import Path

import pytest
from PIL import Image

from orchestrator.app.api.schemas.generation_jobs import GenerationJobCreateRequest
from orchestrator.app.generation_jobs.execution import execute_generation_job_t2i
from orchestrator.app.generation_jobs.service import create_generation_job, reset_generation_job_store_for_tests
from orchestrator.app.t2i.engines.base import T2IGenerationOutput


@pytest.fixture(autouse=True)
def reset_store():
    reset_generation_job_store_for_tests()
    yield
    reset_generation_job_store_for_tests()


class FakeEngine:
    def __init__(self, engine_name: str) -> None:
        self.engine_name = engine_name

    def generate(self, request):
        path = Path(request.output_dir) / f"{self.engine_name}_generated.png"
        Image.new("RGB", (128, 128), "#ABCDEF").save(path)
        return T2IGenerationOutput(engine=self.engine_name, image_paths=[path.as_posix()], latency_ms=3, metadata={"api_key": "blocked"})


def test_gpt_image_1_mocked_success_path(monkeypatch):
    monkeypatch.setattr("orchestrator.app.generation_jobs.execution.get_t2i_engine", lambda name: FakeEngine(name))
    request = GenerationJobCreateRequest(user_input="Create a cafe ad", run_mode="gpt_image_1_smoke")
    job = create_generation_job(request)

    done = execute_generation_job_t2i(job.job_id, request, "gpt_image_1")

    assert done.status == "done"
    assert done.result_payload["schema_version"] == "result_artifact_v1"
    assert done.result_payload["engine"] == "gpt_image_1"
    assert done.output_path == f"data/outputs/{job.job_id}/final_0.png"
    assert Path(done.output_path).exists()
    assert "blocked" not in str(done.model_dump(mode="json"))


def test_sd35_mocked_success_path(monkeypatch):
    monkeypatch.setattr("orchestrator.app.generation_jobs.execution.get_t2i_engine", lambda name: FakeEngine(name))
    request = GenerationJobCreateRequest(user_input="Create a bbq ad", run_mode="sd35_local_smoke")
    job = create_generation_job(request)

    done = execute_generation_job_t2i(job.job_id, request, "sd35_large")

    assert done.status == "done"
    assert done.result_payload["schema_version"] == "result_artifact_v1"
    assert done.result_payload["engine"] == "sd35_large"
    assert Path(done.result_payload["metadata_path"]).exists()


# ===== from test_generation_job_asset_inputs.py =====
import pytest
from orchestrator.app.generation_jobs.service import _resolve_generation_input_asset
from orchestrator.app.generation_jobs.errors import (
    GenerationJobAssetKindInvalid,
    GenerationJobAssetNotFound,
    GenerationJobAssetNotReady,
)

def test_resolve_input_asset_not_found(monkeypatch):
    class MockRepo:
        def get_asset_by_public_id(self, *a, **k):
            return None
    monkeypatch.setattr("orchestrator.app.db.repositories.assets.get_asset_by_public_id", MockRepo().get_asset_by_public_id)

    with pytest.raises(GenerationJobAssetNotFound):
        _resolve_generation_input_asset(
            public_asset_id="asset_123",
            workspace_id="ws1",
            expected_kind="source",
            connection=None
        )

def test_resolve_input_asset_invalid_kind(monkeypatch):
    class MockRepo:
        def get_asset_by_public_id(self, *a, **k):
            return {"kind": "reference"}
    monkeypatch.setattr("orchestrator.app.db.repositories.assets.get_asset_by_public_id", MockRepo().get_asset_by_public_id)

    with pytest.raises(GenerationJobAssetKindInvalid):
        _resolve_generation_input_asset(
            public_asset_id="asset_123",
            workspace_id="ws1",
            expected_kind="source",
            connection=None
        )

def test_resolve_input_asset_not_ready(monkeypatch):
    class MockRepo:
        def get_asset_by_public_id(self, *a, **k):
            return {"kind": "source", "metadata": {"upload": {"status": "pending"}}}
    monkeypatch.setattr("orchestrator.app.db.repositories.assets.get_asset_by_public_id", MockRepo().get_asset_by_public_id)

    with pytest.raises(GenerationJobAssetNotReady):
        _resolve_generation_input_asset(
            public_asset_id="asset_123",
            workspace_id="ws1",
            expected_kind="source",
            connection=None
        )

def test_resolve_input_asset_success(monkeypatch):
    class MockRepo:
        def get_asset_by_public_id(self, *a, **k):
            return {"id": "internal-uuid", "kind": "source", "metadata": {"upload": {"status": "ready"}}}
    monkeypatch.setattr("orchestrator.app.db.repositories.assets.get_asset_by_public_id", MockRepo().get_asset_by_public_id)

    row = _resolve_generation_input_asset(
        public_asset_id="asset_123",
        workspace_id="ws1",
        expected_kind="source",
        connection=None
    )
    assert row["id"] == "internal-uuid"

def test_create_generation_job_db_asset_integration(monkeypatch):
    from orchestrator.app.generation_jobs.service import _create_generation_job_db
    from orchestrator.app.api.schemas.generation_jobs import GenerationJobCreateRequest
    import uuid

    req = GenerationJobCreateRequest(
        source_asset_id="asset_" + "a"*32,
        reference_asset_id="asset_" + "b"*32,
        user_input="Test",
        user_id="demo",
        workspace_id="11111111-1111-1111-1111-111111111111",
    )

    def fake_resolve(*, public_asset_id, expected_kind, **kwargs):
        if expected_kind == "source":
            return {"id": "int-src"}
        return {"id": "int-ref"}

    monkeypatch.setattr("orchestrator.app.generation_jobs.service._resolve_generation_input_asset", fake_resolve)

    class MockJobRepo:
        def create_generation_job_row(self, **kwargs):
            self.kwargs = kwargs
            return {
                "id": uuid.uuid4(),
                "public_job_id": "job_123",
                "status": "queued",
                "request_payload": kwargs.get("request_payload")
            }
    mock_repo = MockJobRepo()
    monkeypatch.setattr("orchestrator.app.generation_jobs.service.generation_job_repo", mock_repo)
    monkeypatch.setattr("orchestrator.app.generation_jobs.service.db_transaction", lambda: __import__("contextlib").nullcontext())
    monkeypatch.setattr("orchestrator.app.db.settings.get_demo_user_id", lambda: "demo")
    monkeypatch.setattr("orchestrator.app.db.settings.get_db_backend", lambda: "postgres")
    monkeypatch.setattr("orchestrator.app.generation_jobs.service.workspace_repo", type("W", (), {"get_workspace_for_user": lambda *a, **k: {"id": "11111111-1111-1111-1111-111111111111", "owner_user_id": None}})())
    monkeypatch.setattr("orchestrator.app.generation_jobs.service.chat_thread_repo", type("T", (), {"get_chat_thread_by_public_id": lambda *a, **k: {"id": "t1"}, "create_chat_thread": lambda *a, **k: {"id": "t1"}, "set_chat_thread_active_job": lambda *a, **k: True})())
    monkeypatch.setattr("orchestrator.app.generation_jobs.service.chat_message_repo", type("M", (), {"append_chat_message": lambda *a, **k: {"id": "m1"}, "append_generation_job_chat_event": lambda *a, **k: {"id": "m2"}})())
    monkeypatch.setattr("orchestrator.app.generation_jobs.service.state_service", type("S", (), {"save_thread_state_snapshot": lambda *a, **k: None, "get_latest_thread_state_snapshot": lambda *a, **k: None, "restore_thread_state": lambda *a, **k: {}})())

    _create_generation_job_db(req)

    assert mock_repo.kwargs["input_asset_id"] == "int-src"
    assert mock_repo.kwargs["reference_asset_id"] == "int-ref"
    assert mock_repo.kwargs["request_payload"]["source_asset_id"] == req.source_asset_id
    assert mock_repo.kwargs["request_payload"]["reference_asset_id"] == req.reference_asset_id


# ===== from test_generation_job_db_repository.py =====
from contextlib import contextmanager

from orchestrator.app.db.repositories import generation_jobs as repo


class FakeCursor:
    def __init__(self):
        self.calls = []
        self.row = {"public_job_id": "job_db", "status": "queued"}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), params))

    def fetchone(self):
        return self.row


class FakeConnection:
    def __init__(self):
        self.cursor_obj = FakeCursor()

    def cursor(self):
        return self.cursor_obj


@contextmanager
def fake_transaction(connection=None):
    yield connection


def test_create_generation_job_row_inserts_expected_fields(monkeypatch):
    conn = FakeConnection()
    monkeypatch.setattr(repo, "db_transaction", fake_transaction)

    row = repo.create_generation_job_row(
        public_job_id="job_db",
        workspace_id="workspace_id",
        thread_id="thread_id",
        requested_by="demo_user",
        status="queued",
        current_stage="queued",
        progress_percent=0,
        selected_reference_template_id="seed_1",
        output_path=None,
        result_payload=None,
        error=None,
        metadata={"requested_run_mode": "queued_only"},
        connection=conn,
    )

    sql, params = conn.cursor_obj.calls[0]
    assert "insert into generation_jobs" in sql
    assert "public_job_id" in sql
    assert "result_payload, error, metadata" in sql
    assert "%s::jsonb" in sql
    assert params[0] == "job_db"
    assert params[1] == "workspace_id"
    assert row["public_job_id"] == "job_db"


def test_get_generation_job_row_selects_by_public_job_id(monkeypatch):
    conn = FakeConnection()
    monkeypatch.setattr(repo, "db_transaction", fake_transaction)

    row = repo.get_generation_job_row("job_db", connection=conn)

    sql, params = conn.cursor_obj.calls[0]
    assert "from generation_jobs gj" in sql
    assert "left join chat_threads ct on ct.id = gj.thread_id" in sql
    assert "where gj.public_job_id = %s" in sql
    assert params == ("job_db",)
    assert row["public_job_id"] == "job_db"


def test_get_generation_job_by_public_id_scopes_by_workspace(monkeypatch):
    conn = FakeConnection()
    monkeypatch.setattr(repo, "db_transaction", fake_transaction)

    row = repo.get_generation_job_by_public_id("job_db", workspace_id="workspace_id", connection=conn)

    sql, params = conn.cursor_obj.calls[0]
    assert "where gj.public_job_id = %s and gj.workspace_id = %s::uuid" in sql
    assert params == ("job_db", "workspace_id")
    assert row["public_job_id"] == "job_db"


def test_update_generation_job_row_can_scope_by_workspace(monkeypatch):
    conn = FakeConnection()
    monkeypatch.setattr(repo, "db_transaction", fake_transaction)

    repo.update_generation_job_row("job_db", workspace_id="workspace_id", status="running", connection=conn)

    sql, params = conn.cursor_obj.calls[0]
    assert "where public_job_id = %s and workspace_id = %s::uuid" in sql
    assert params[-2:] == ("job_db", "workspace_id")


def test_mark_running_done_failed_update_status(monkeypatch):
    conn = FakeConnection()
    monkeypatch.setattr(repo, "db_transaction", fake_transaction)

    repo.mark_generation_job_running_row("job_db", current_stage="t2i_running", connection=conn)
    repo.mark_generation_job_done_row("job_db", {"schema_version": "result_artifact_v1"}, output_path="data/outputs/job/final_0.png", connection=conn)
    repo.mark_generation_job_failed_row("job_db", {"error_code": "x", "message": "failed"}, connection=conn)

    joined = "\n".join(call[0] for call in conn.cursor_obj.calls)
    assert "status = %s" in joined
    assert "progress_percent = %s" in joined
    assert "result_payload = %s::jsonb" in joined
    assert "error = %s::jsonb" in joined


# ===== from test_generation_job_done_integration.py =====
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


# ===== from test_generation_job_events_repository.py =====
from contextlib import contextmanager

from orchestrator.app.db.repositories import generation_job_events as repo__test_generation_job_events_repository


class FakeCursor__test_generation_job_events_repository:
    def __init__(self):
        self.calls = []
        self.row = {"id": "event_uuid", "event_type": "queued"}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), params))

    def fetchone(self):
        return self.row

    def fetchall(self):
        return [self.row]


class FakeConnection__test_generation_job_events_repository:
    def __init__(self):
        self.cursor_obj = FakeCursor__test_generation_job_events_repository()

    def cursor(self):
        return self.cursor_obj


@contextmanager
def fake_transaction__test_generation_job_events_repository(connection=None):
    yield connection


def test_record_generation_job_event_uses_jsonb_payload(monkeypatch):
    conn = FakeConnection__test_generation_job_events_repository()
    monkeypatch.setattr(repo__test_generation_job_events_repository, "db_transaction", fake_transaction__test_generation_job_events_repository)

    row = repo__test_generation_job_events_repository.record_generation_job_event(
        workspace_id="workspace_uuid",
        thread_id="thread_uuid",
        job_id="job_uuid",
        event_type="running",
        message="t2i_running",
        payload={"current_stage": "t2i_running"},
        connection=conn,
    )

    sql, params = conn.cursor_obj.calls[0]
    assert "insert into generation_job_events" in sql
    assert "%s::jsonb" in sql
    assert params[0] == "workspace_uuid"
    assert params[3] == "running"
    assert '"current_stage": "t2i_running"' in params[5]
    assert row["id"] == "event_uuid"


def test_list_generation_job_events_orders_by_created(monkeypatch):
    conn = FakeConnection__test_generation_job_events_repository()
    monkeypatch.setattr(repo__test_generation_job_events_repository, "db_transaction", fake_transaction__test_generation_job_events_repository)

    rows = repo__test_generation_job_events_repository.list_generation_job_events("job_uuid", limit=10, connection=conn)

    sql, params = conn.cursor_obj.calls[0]
    assert "where job_id = %s" in sql
    assert "order by created_at desc" in sql
    assert params == ("job_uuid", 10)
    assert rows[0]["event_type"] == "queued"

def test_list_generation_job_events_by_public_job_id_joins_generation_jobs(monkeypatch):
    conn = FakeConnection__test_generation_job_events_repository()
    monkeypatch.setattr(repo__test_generation_job_events_repository, "db_transaction", fake_transaction__test_generation_job_events_repository)

    rows = repo__test_generation_job_events_repository.list_generation_job_events_by_public_job_id("job_db", limit=10, connection=conn)

    sql, params = conn.cursor_obj.calls[0]
    assert "join generation_jobs j on j.id = e.job_id" in sql
    assert "where j.public_job_id = %s" in sql
    assert "order by e.created_at desc" in sql
    assert params == ("job_db", 10)
    assert rows[0]["event_type"] == "queued"


# ===== from test_generation_job_execution_bridge.py =====
from pathlib import Path

import pytest
from PIL import Image

from orchestrator.app.api.schemas.generation_jobs import GenerationJobCreateRequest
from orchestrator.app.generation_jobs.execution import execute_generation_job_immediate, get_generation_job_output_dir
from orchestrator.app.generation_jobs.service import (
    create_generation_job,
    get_generation_job,
    mark_generation_job_failed,
    reset_generation_job_store_for_tests,
)


@pytest.fixture(autouse=True)
def reset_store__test_generation_job_execution_bridge():
    reset_generation_job_store_for_tests()
    yield
    reset_generation_job_store_for_tests()


def test_queued_only_does_not_execute():
    request = GenerationJobCreateRequest(user_input="Create an ad", run_mode="queued_only")
    job = create_generation_job(request)

    assert job.status == "queued"
    assert job.progress.progress_percent == 0
    assert job.output_path is None
    assert job.result_payload is None


def test_mock_immediate_writes_artifacts_under_job_output_dir():
    request = GenerationJobCreateRequest(user_input="Create an ad", run_mode="mock_immediate", ad_format="instagram_feed")
    job = create_generation_job(request)
    done = execute_generation_job_immediate(job.job_id, request)

    assert done.status == "done"
    assert done.progress.progress_percent == 100
    assert done.progress.current_stage == "completed"
    assert done.output_path == f"data/outputs/{job.job_id}/final_0.png"
    assert done.result_payload is not None
    assert done.result_payload["schema_version"] == "result_artifact_v1"
    assert done.result_payload["download_url"] is None
    assert done.result_payload["final_image_url"] is None
    assert done.result_payload["prompt_summary"]
    assert done.result_payload["validation_summary"]["overall_pass"] is True
    assert done.metadata["requested_run_mode"] == "mock_immediate"
    assert done.metadata["effective_run_mode"] == "mock_immediate"
    assert done.metadata["execution_mode"] == "deterministic_mock"

    output_dir = Path(f"data/outputs/{job.job_id}")
    expected = [
        output_dir / "background_0.png",
        output_dir / "final_0.png",
        output_dir / "metadata.json",
        output_dir / "prompt.json",
        output_dir / "validation.json",
        output_dir / "copy.json",
        output_dir / "layout.json",
        output_dir / "render_result.json",
    ]
    for path in expected:
        assert path.exists()
        assert output_dir in path.parents

    with Image.open(output_dir / "final_0.png") as image:
        assert image.width == 1024
        assert image.height == 1024

    fetched = get_generation_job(job.job_id)
    assert fetched is not None
    assert fetched.status == "done"


def test_graph_job_pending_metadata_without_execution():
    request = GenerationJobCreateRequest(user_input="Create an ad", run_mode="graph_job")
    job = create_generation_job(request)

    assert job.status == "queued"
    assert job.output_path is None
    assert job.result_payload is None
    assert job.metadata["requested_run_mode"] == "graph_job"
    assert job.metadata["effective_run_mode"] == "graph_job"
    assert job.metadata["execution_mode"] == "pending_graph_execution"


def test_failed_job_sets_failed_stage():
    request = GenerationJobCreateRequest(user_input="Create an ad", run_mode="mock_immediate")
    job = create_generation_job(request)
    failed = mark_generation_job_failed(job.job_id, {"error_code": "mock_failed", "message": "Mock failed"})

    assert failed is not None
    assert failed.status == "failed"
    assert failed.progress.current_stage == "failed"
    assert failed.error is not None
    assert failed.error.error_code == "mock_failed"


def test_path_traversal_job_id_rejected():
    for job_id in ["job_../bad", "job_bad/path", "job_bad\\path", "bad_job"]:
        with pytest.raises(ValueError):
            get_generation_job_output_dir(job_id)


# ===== from test_generation_job_flux_lane.py =====
from pathlib import Path

import pytest
from PIL import Image

from orchestrator.app.api.schemas.generation_jobs import GenerationJobCreateRequest
from orchestrator.app.generation_jobs.execution import execute_generation_job_t2i
from orchestrator.app.generation_jobs.service import create_generation_job, reset_generation_job_store_for_tests
from orchestrator.app.t2i.engines.base import T2IGenerationOutput
from orchestrator.app.t2i.engines.flux_local import FluxPromptTokenBudgetError


@pytest.fixture(autouse=True)
def reset_store__test_generation_job_flux_lane():
    reset_generation_job_store_for_tests()
    yield
    reset_generation_job_store_for_tests()


class FakeFluxEngine:
    engine_name = "flux"

    def generate(self, request):
        path = Path(request.output_dir) / "flux_0.png"
        Image.new("RGB", (128, 128), "#DDEEFF").save(path)
        return T2IGenerationOutput(
            engine="flux",
            image_paths=[path.as_posix()],
            latency_ms=5,
            metadata={"hf_token": "blocked", "model_source": "model_id", "local_path_present": False},
        )


class CapturingFluxEngine(FakeFluxEngine):
    last_request = None

    def generate(self, request):
        CapturingFluxEngine.last_request = request
        return super().generate(request)


class FailingFluxEngine:
    engine_name = "flux"

    def generate(self, request):
        raise FluxPromptTokenBudgetError("budget failed")


def test_flux_mocked_success_path(monkeypatch):
    monkeypatch.setattr("orchestrator.app.generation_jobs.execution.get_t2i_engine", lambda name: FakeFluxEngine())
    request = GenerationJobCreateRequest(user_input="Create a cafe ad", run_mode="flux_local_smoke")
    job = create_generation_job(request)

    done = execute_generation_job_t2i(job.job_id, request, "flux")

    assert done.status == "done"
    assert done.result_payload["schema_version"] == "result_artifact_v1"
    assert done.result_payload["engine"] == "flux"
    assert done.result_payload["final_image_path"] == f"data/outputs/{job.job_id}/final_0.png"
    assert done.result_payload["download_url"] is None
    assert done.result_payload["final_image_url"] is None
    assert done.metadata["effective_run_mode"] == "flux_local"
    assert done.metadata["t2i_engine"] == "flux"
    assert Path(done.result_payload["final_image_path"]).exists()
    assert "blocked" not in str(done.model_dump(mode="json"))


def test_flux_request_metadata_is_forwarded_to_engine_with_allowlist(monkeypatch):
    monkeypatch.setattr("orchestrator.app.generation_jobs.execution.get_t2i_engine", lambda name: CapturingFluxEngine())
    request = GenerationJobCreateRequest(
        user_input="Create a cafe ad",
        run_mode="flux_local_smoke",
        metadata={
            "business_type": "cafe",
            "case_id": "cafe_dessert_001",
            "primary_subject": "strawberry latte",
            "api_key": "sk-blocked",
            "debug": {"safe": "not-forwarded"},
        },
    )
    job = create_generation_job(request)

    execute_generation_job_t2i(job.job_id, request, "flux")

    metadata = CapturingFluxEngine.last_request.metadata
    assert metadata["business_type"] == "cafe"
    assert metadata["case_id"] == "cafe_dessert_001"
    assert metadata["primary_subject"] == "strawberry latte"
    assert "api_key" not in metadata
    assert "debug" not in metadata


def test_flux_prompt_budget_error_preserves_specific_error_code(monkeypatch):
    monkeypatch.setattr("orchestrator.app.generation_jobs.execution.get_t2i_engine", lambda name: FailingFluxEngine())
    request = GenerationJobCreateRequest(user_input="Create a cafe ad", run_mode="flux_local_smoke")
    job = create_generation_job(request)

    failed = execute_generation_job_t2i(job.job_id, request, "flux")

    assert failed.status == "failed"
    assert failed.error.error_code == "flux_prompt_token_budget_unresolvable"
    assert failed.error.error_type == "FluxPromptTokenBudgetError"


# ===== from test_generation_job_graph_execution.py =====
"""Tests for execute_generation_job_graph and state restoration."""

from contextlib import contextmanager

import pytest
from orchestrator.app.api.schemas.generation_jobs import (
    GenerationJobAnswerRequest,
    GenerationJobCreateRequest,
    GenerationJobResponse,
    GenerationProgress,
)
from orchestrator.app.generation_jobs.service import create_generation_job, reset_generation_job_store_for_tests
from orchestrator.app.chat_threads.service import list_chat_messages, reset_chat_thread_store_for_tests
from orchestrator.app.schemas.chat_state_snapshots import ChatStateSnapshotResponse
from orchestrator.app.generation_jobs.execution import (
    execute_generation_job_graph,
    poll_and_process_graph_modal_generation_job,
    resume_generation_job_graph,
)
from orchestrator.app.generation_jobs import execution

@pytest.fixture(autouse=True)
def reset_stores():
    reset_generation_job_store_for_tests()
    reset_chat_thread_store_for_tests()
    from orchestrator.app.chat_threads.state_service import _SNAPSHOTS_MEM_LOCK, _SNAPSHOTS_MEM
    with _SNAPSHOTS_MEM_LOCK:
        _SNAPSHOTS_MEM.clear()
    yield


class FakeInterrupt:
    def __init__(self, value):
        self.value = value


@contextmanager
def fake_db_transaction(connection=None):
    yield object()


def _graph_job_response(**overrides):
    payload = {
        "job_id": "job_graph_db",
        "thread_id": "thread_graph_db",
        "user_id": None,
        "brand_kit_id": None,
        "status": "queued",
        "progress": GenerationProgress(progress_percent=0, current_stage="queued"),
        "selected_reference_template_id": None,
        "output_path": None,
        "result_payload": {},
        "error": None,
        "created_at": "2026-06-06T00:00:00+00:00",
        "updated_at": "2026-06-06T00:00:00+00:00",
        "metadata": {},
    }
    payload.update(overrides)
    return GenerationJobResponse(**payload)


def test_execute_generation_job_graph_uses_job_workspace_for_input_snapshot(monkeypatch):
    captured = {}

    class MockGraph:
        def invoke(self, payload: dict, config: dict | None = None) -> dict:
            state = dict(payload)
            state["status"] = "done"
            state["result_payload"] = {"final_image_path": "/fake/db-workspace.png"}
            state["final_image_path"] = "/fake/db-workspace.png"
            return state

    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")
    monkeypatch.setattr("orchestrator.app.db.session.db_transaction", fake_db_transaction)
    monkeypatch.setattr(execution, "get_generation_job", lambda job_id: _graph_job_response(job_id=job_id))
    monkeypatch.setattr(execution, "mark_generation_job_running", lambda *args, **kwargs: None)
    monkeypatch.setattr(execution, "mark_generation_job_done", lambda job_id, **kwargs: _graph_job_response(job_id=job_id, status="done"))
    monkeypatch.setattr("orchestrator.app.db.repositories.generation_jobs.get_generation_job_row", lambda *args, **kwargs: {
        "id": "internal_job_uuid",
        "public_job_id": "job_graph_db",
        "workspace_id": "workspace_from_job_row",
    })
    monkeypatch.setattr("orchestrator.app.generation_jobs.execution.get_generation_job_graph", lambda: MockGraph())

    def get_snapshot(**kwargs):
        captured.update(kwargs)
        return ChatStateSnapshotResponse(
            snapshot_id="snapshot_input",
            thread_id="thread_graph_db",
            job_id="job_graph_db",
            snapshot_version=1,
            schema_version=1,
            snapshot_kind="input",
            state_payload={"user_input": "카페 광고"},
            changed_fields=["user_input"],
            created_at="2026-06-06T00:00:00+00:00",
        )

    monkeypatch.setattr("orchestrator.app.chat_threads.state_service.get_chat_state_snapshot_by_key", get_snapshot)
    monkeypatch.setattr("orchestrator.app.chat_threads.state_service.save_thread_state_snapshot", lambda **kwargs: None)

    request = GenerationJobCreateRequest(userInput="카페 광고", runMode="graph_job")
    result = execute_generation_job_graph("job_graph_db", request)

    assert result.status == "done"
    assert captured["workspace_id"] == "workspace_from_job_row"
    assert captured["snapshot_key"] == "job_graph_db:input"


def test_execute_generation_job_graph_state_restoration(monkeypatch):
    class MockGraph:
        def invoke(self, payload: dict, config: dict | None = None) -> dict:
            state = dict(payload)
            state["status"] = "done"
            state["result_payload"] = {"final_image_path": "/fake/path.png", "final_brief": {"user_input": state["user_input"]}}
            state["final_image_path"] = "/fake/path.png"
            return state

    monkeypatch.setattr("orchestrator.app.generation_jobs.execution.get_generation_job_graph", lambda: MockGraph())

    req1 = GenerationJobCreateRequest(
        user_input="turn 1 prompt",
        run_mode="graph_job",
        copy_generation_mode="auto_pilot",
    )
    job1 = create_generation_job(req1)
    assert job1.status == "queued"

    executed1 = execute_generation_job_graph(job1.job_id, req1)
    if executed1.status == "failed":
        print("ERROR1:", executed1.error)
    assert executed1.status == "done"

    received_payload = {}
    class MockGraph2:
        def invoke(self, payload: dict, config: dict | None = None) -> dict:
            nonlocal received_payload
            received_payload = dict(payload)
            state = dict(payload)
            state["status"] = "done"
            state["result_payload"] = {"final_image_path": "/fake/path2.png", "final_brief": {"user_input": state["user_input"]}}
            state["final_image_path"] = "/fake/path2.png"
            return state

    monkeypatch.setattr("orchestrator.app.generation_jobs.execution.get_generation_job_graph", lambda: MockGraph2())

    req2 = GenerationJobCreateRequest(
        user_input="turn 2 prompt",
        run_mode="graph_job",
        thread_id=job1.thread_id,
        user_id=job1.user_id,
        copy_generation_mode="custom_input",
    )
    job2 = create_generation_job(req2)
    executed2 = execute_generation_job_graph(job2.job_id, req2)

    assert executed2.status == "done"
    assert received_payload["user_input"] == "turn 2 prompt"
    assert received_payload["copy_generation_mode"] == "custom_input"
    assert received_payload["job_id"] == job2.job_id
    assert received_payload["thread_id"] == job1.thread_id


def test_execute_generation_job_graph_receives_selected_engine(monkeypatch):
    received_payload = {}

    class MockGraph:
        def invoke(self, payload: dict, config: dict | None = None) -> dict:
            nonlocal received_payload
            received_payload = dict(payload)
            state = dict(payload)
            state["status"] = "done"
            state["result_payload"] = {
                "final_image_path": "/fake/graph-engine.png",
                "final_brief": {"user_input": state["user_input"]},
            }
            state["final_image_path"] = "/fake/graph-engine.png"
            return state

    monkeypatch.setattr("orchestrator.app.generation_jobs.execution.get_generation_job_graph", lambda: MockGraph())

    request = GenerationJobCreateRequest(
        user_input="정교한 베이커리 광고 만들어줘",
        run_mode="graph_job",
        metadata={
            "selected_engine": "sd35_large",
            "requested_engine": "sd35_large",
            "t2i_engine": "sd35_large",
        },
    )
    job = create_generation_job(request)

    executed = execute_generation_job_graph(job.job_id, request)

    assert executed.status == "done"
    assert received_payload["engine"] == "sd35_large"
    assert received_payload["current_brief"]["requested_engine"] == "sd35_large"


def test_execute_generation_job_graph_persists_modal_pending_state(monkeypatch, tmp_path):
    class MockGraph:
        def invoke(self, payload: dict, config: dict | None = None) -> dict:
            state = dict(payload)
            state.update(
                {
                    "status": "modal_running",
                    "copy_generation_mode": "no_copy",
                    "copy_required": False,
                    "text_overlay_pending": False,
                    "copy_spec": {"schema_version": "1.0", "copy_mode": "no_copy", "items": []},
                    "text_layout_spec": {
                        "schema_version": "1.0",
                        "template": "no_text",
                        "canvas_width": 2,
                        "canvas_height": 2,
                        "slots": [],
                        "reserved_text_areas": [],
                    },
                    "t2i_request": {
                        "prompt": "clean cafe poster background",
                        "negative_prompt": "",
                        "width": 2,
                        "height": 2,
                        "num_images": 1,
                        "output_dir": str(tmp_path / "job-modal-pending"),
                        "metadata": {"requested_engine": "flux"},
                    },
                    "t2i_result": {
                        "engine": "flux",
                        "image_paths": [],
                        "seed": None,
                        "latency_ms": 12,
                        "width": 2,
                        "height": 2,
                        "prompt": "clean cafe poster background",
                        "negative_prompt": "",
                        "metadata": {
                            "execution_backend": "modal",
                            "modal_call_id_present": True,
                            "modal_call_id": "modal_call_graph_1",
                            "requested_engine": "flux",
                        },
                        "error": None,
                    },
                }
            )
            return state

    monkeypatch.setattr("orchestrator.app.generation_jobs.execution.get_generation_job_graph", lambda: MockGraph())

    request = GenerationJobCreateRequest(user_input="카페 광고", run_mode="graph_job")
    job = create_generation_job(request)
    executed = execute_generation_job_graph(job.job_id, request)

    assert executed.status == "running"
    assert executed.progress.current_stage == "modal_running"
    assert executed.metadata["graph_modal_pending"] is True
    assert executed.metadata["modal_call_id"] == "modal_call_graph_1"

    from orchestrator.app.chat_threads.state_service import get_chat_state_snapshot_by_key

    snapshot = get_chat_state_snapshot_by_key(
        snapshot_key=f"{job.job_id}:graph_modal_pending",
        public_thread_id=job.thread_id,
        workspace_id="mem_workspace",
        user_id=job.user_id,
    )
    assert snapshot is not None
    assert snapshot.state_payload["t2i_request"]["output_dir"] == str(tmp_path / "job-modal-pending")
    assert snapshot.state_payload["t2i_result"]["metadata"]["modal_call_id"] == "modal_call_graph_1"


def test_graph_modal_poll_completion_runs_post_t2i_nodes(monkeypatch, tmp_path):
    class MockGraph:
        def invoke(self, payload: dict, config: dict | None = None) -> dict:
            state = dict(payload)
            state.update(
                {
                    "status": "modal_running",
                    "copy_generation_mode": "no_copy",
                    "copy_required": False,
                    "text_overlay_pending": False,
                    "copy_spec": {"schema_version": "1.0", "copy_mode": "no_copy", "items": []},
                    "text_layout_spec": {
                        "schema_version": "1.0",
                        "template": "no_text",
                        "canvas_width": 2,
                        "canvas_height": 2,
                        "slots": [],
                        "reserved_text_areas": [],
                    },
                    "t2i_request": {
                        "prompt": "clean cafe poster background",
                        "negative_prompt": "",
                        "width": 2,
                        "height": 2,
                        "num_images": 1,
                        "output_dir": str(tmp_path / "job-modal-complete"),
                        "metadata": {"requested_engine": "flux"},
                    },
                    "t2i_result": {
                        "engine": "flux",
                        "image_paths": [],
                        "seed": None,
                        "latency_ms": 12,
                        "width": 2,
                        "height": 2,
                        "prompt": "clean cafe poster background",
                        "negative_prompt": "",
                        "metadata": {
                            "execution_backend": "modal",
                            "modal_call_id_present": True,
                            "modal_call_id": "modal_call_graph_2",
                            "requested_engine": "flux",
                        },
                        "error": None,
                    },
                }
            )
            return state

    from orchestrator.app.modal.schemas import ModalPollResult

    png_b64 = (
        "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAYAAABytg0kAAAAEklEQVR42mP8z8AARLJgYGBgAAA2AQH/"
        "wH9tWQAAAABJRU5ErkJggg=="
    )
    monkeypatch.setattr("orchestrator.app.generation_jobs.execution.get_generation_job_graph", lambda: MockGraph())
    monkeypatch.setattr(
        "orchestrator.app.modal.client.poll_modal_t2i_result",
        lambda modal_call_id: ModalPollResult(
            status="succeeded",
            modal_call_id=modal_call_id,
            image_b64=png_b64,
            metadata={"modal_test": True},
        ),
    )

    request = GenerationJobCreateRequest(user_input="카페 광고", run_mode="graph_job")
    job = create_generation_job(request)
    pending = execute_generation_job_graph(job.job_id, request)
    assert pending.status == "running"

    completed = poll_and_process_graph_modal_generation_job(job.job_id)

    assert completed is not None
    assert completed.status == "done"
    assert completed.metadata["execution_mode"] == "graph_modal_completed"
    assert completed.result_payload["status"] == "done"
    assert completed.result_payload["output_path"].replace("\\", "/") == str(tmp_path / "job-modal-complete" / "final_0.png").replace("\\", "/")
    assert completed.result_payload["validation_summary"]["background"]["overall_pass"] is True


def test_execute_generation_job_graph_receives_source_asset_id(monkeypatch):
    received_payload = {}

    class MockGraph:
        def invoke(self, payload: dict, config: dict | None = None) -> dict:
            nonlocal received_payload
            received_payload = dict(payload)
            state = dict(payload)
            state["status"] = "done"
            state["result_payload"] = {
                "final_image_path": "/fake/photo-source.png",
                "final_brief": {"user_input": state["user_input"]},
            }
            state["final_image_path"] = "/fake/photo-source.png"
            return state

    monkeypatch.setattr("orchestrator.app.generation_jobs.execution.get_generation_job_graph", lambda: MockGraph())
    monkeypatch.setattr("orchestrator.app.generation_jobs.execution.get_generation_job", lambda j: type("J", (), {"job_id": j, "request_payload": {}, "status": "done", "thread_id": "t", "user_id": "u", "metadata": {}})())
    monkeypatch.setattr("orchestrator.app.generation_jobs.execution.mark_generation_job_running", lambda j, **k: None)
    monkeypatch.setattr("orchestrator.app.generation_jobs.execution.mark_generation_job_done", lambda j, **k: None)
    monkeypatch.setattr("orchestrator.app.generation_jobs.execution.append_generation_job_user_answer_message", lambda j, **k: None)

    class MockSnapshotService:
        def get_chat_state_snapshot_by_key(self, **kwargs):
            return type("S", (), {"state_payload": {}})()
    monkeypatch.setattr("orchestrator.app.chat_threads.state_service", MockSnapshotService())

    request = GenerationJobCreateRequest(
        user_input="이 사진으로 신메뉴 광고 만들어줘",
        run_mode="graph_job",
        source_asset_id="asset_" + "a"*32,
    )

    executed = execute_generation_job_graph("job_123", request)

    assert executed.status == "done"
    assert received_payload["source_asset_id"] == "asset_" + "a"*32


def test_execute_generation_job_graph_receives_reference_asset_id(monkeypatch):
    received_payload = {}

    class MockGraph:
        def invoke(self, payload: dict, config: dict | None = None) -> dict:
            nonlocal received_payload
            received_payload = dict(payload)
            state = dict(payload)
            state["status"] = "done"
            state["result_payload"] = {
                "final_image_path": "/fake/reference-style.png",
                "final_brief": {"user_input": state["user_input"]},
            }
            state["final_image_path"] = "/fake/reference-style.png"
            return state

    monkeypatch.setattr("orchestrator.app.generation_jobs.execution.get_generation_job_graph", lambda: MockGraph())
    monkeypatch.setattr("orchestrator.app.generation_jobs.execution.get_generation_job", lambda j: type("J", (), {"job_id": j, "request_payload": {}, "status": "done", "thread_id": "t", "user_id": "u", "metadata": {}})())
    monkeypatch.setattr("orchestrator.app.generation_jobs.execution.mark_generation_job_running", lambda j, **k: None)
    monkeypatch.setattr("orchestrator.app.generation_jobs.execution.mark_generation_job_done", lambda j, **k: None)
    monkeypatch.setattr("orchestrator.app.generation_jobs.execution.append_generation_job_user_answer_message", lambda j, **k: None)

    class MockSnapshotService:
        def get_chat_state_snapshot_by_key(self, **kwargs):
            return type("S", (), {"state_payload": {}})()
    monkeypatch.setattr("orchestrator.app.chat_threads.state_service", MockSnapshotService())

    request = GenerationJobCreateRequest(
        user_input="이 레퍼런스 분위기로 광고 만들어줘",
        run_mode="graph_job",
        reference_asset_id="asset_" + "b"*32,
    )

    executed = execute_generation_job_graph("job_123", request)

    assert executed.status == "done"
    assert received_payload["reference_asset_id"] == "asset_" + "b"*32


def test_execute_generation_job_graph_receives_selected_ui_values(monkeypatch):
    received_payload = {}

    class MockGraph:
        def invoke(self, payload: dict, config: dict | None = None) -> dict:
            nonlocal received_payload
            received_payload = dict(payload)
            state = dict(payload)
            state["status"] = "done"
            state["result_payload"] = {
                "final_image_path": "/fake/selected-ui-values.png",
                "final_brief": {"user_input": state["user_input"]},
            }
            state["final_image_path"] = "/fake/selected-ui-values.png"
            return state

    monkeypatch.setattr("orchestrator.app.generation_jobs.execution.get_generation_job_graph", lambda: MockGraph())

    request = GenerationJobCreateRequest(
        user_input="선택값으로 광고 만들어줘",
        run_mode="graph_job",
        selectedCopyId="copy_2",
        selectedChannelId="instagram-story",
        selectedTone="상큼한",
        customDirection="제품을 화면 중앙에 크게",
        userCustomHeadline="오늘만 딸기라떼 반값",
        userCustomSubcopy="오후 2시부터 5시까지",
    )
    job = create_generation_job(request)

    executed = execute_generation_job_graph(job.job_id, request)

    assert executed.status == "done"
    assert received_payload["selected_copy_id"] == "copy_2"
    assert received_payload["selected_channel_id"] == "instagram-story"
    assert received_payload["selected_ad_format"] == "instagram_story"
    assert received_payload["selected_tone"] == "상큼한"
    assert received_payload["custom_direction"] == "제품을 화면 중앙에 크게"
    assert received_payload["user_custom_headline"] == "오늘만 딸기라떼 반값"
    assert received_payload["user_custom_subcopy"] == "오후 2시부터 5시까지"
    assert received_payload["current_brief"]["requested_ad_format"] == "instagram_story"
    assert received_payload["current_brief"]["selected_tone"] == "상큼한"
    assert received_payload["current_brief"]["custom_direction"] == "제품을 화면 중앙에 크게"
    assert received_payload["context"]["brand_tone"] == "상큼한"
    assert received_payload["context"]["extra"]["ad_format"] == "instagram_story"


def test_suggest_candidates_create_clears_stale_copy_state():
    state = {
        "copy_generation_mode": "suggest_candidates",
        "selected_copy_id": "copy_1",
        "copy_selection": {"selected_copy_id": "copy_1"},
        "marketing_copy": {"headline": "stale"},
        "copy_candidates": [{"id": "copy_1", "headline": "stale"}],
        "copywriting_output": {"recommended_candidate_id": "copy_1"},
        "copy_candidate_origin": "rule_based",
    }
    request = GenerationJobCreateRequest(userInput="새 광고", copyGenerationMode="suggest_candidates", selectedCopyId=None)

    execution._clear_stale_suggest_copy_state(state, request)

    assert state["selected_copy_id"] is None
    assert state["copy_selection"] is None
    assert state["marketing_copy"] is None
    assert state["copy_candidates"] == []
    assert state["copywriting_output"] is None
    assert state["copy_candidate_origin"] is None


def test_execute_generation_job_graph_waiting_user_input(monkeypatch):
    class MockGraphWaiting:
        def invoke(self, payload: dict, config: dict | None = None) -> dict:
            state = dict(payload)
            state["__interrupt__"] = True
            state["status"] = "waiting_user_input"
            state["messages"] = [{"role": "assistant", "content": "Please answer this."}]
            return state

    monkeypatch.setattr("orchestrator.app.generation_jobs.execution.get_generation_job_graph", lambda: MockGraphWaiting())

    req = GenerationJobCreateRequest(
        user_input="start",
        run_mode="graph_job",
    )
    job = create_generation_job(req)
    executed = execute_generation_job_graph(job.job_id, req)

    if executed.status == "failed":
        print("ERROR:", executed.error)

    assert executed.status == "waiting_user_input"
    assert executed.progress.current_stage == "waiting_user_input"

def test_execute_generation_job_graph_waiting_and_resume(monkeypatch):
    class MockGraphWaiting:
        def invoke(self, payload: dict, config: dict | None = None) -> dict:
            state = dict(payload)
            state["__interrupt__"] = True
            state["status"] = "waiting_user_input"
            state["messages"] = [{"role": "assistant", "content": "Please provide more details."}]
            state["business_type"] = "cafe" # Ensure context is kept
            return state

    monkeypatch.setattr("orchestrator.app.generation_jobs.execution.get_generation_job_graph", lambda: MockGraphWaiting())

    req1 = GenerationJobCreateRequest(
        user_input="start cafe ad",
        run_mode="graph_job",
    )
    job1 = create_generation_job(req1)
    executed1 = execute_generation_job_graph(job1.job_id, req1)

    assert executed1.status == "waiting_user_input"

    from orchestrator.app.chat_threads.service import get_chat_thread
    thread = get_chat_thread(job1.thread_id, job1.user_id)
    assert thread.active_job_id is None

    # 5. 동일 thread로 두 번째 GenerationJob 생성 성공
    req2 = GenerationJobCreateRequest(
        user_input="resume with more details",
        run_mode="graph_job",
        thread_id=job1.thread_id,
        user_id=job1.user_id,
    )
    job2 = create_generation_job(req2)
    assert job2.job_id != job1.job_id

    # Check input snapshot
    from orchestrator.app.chat_threads.state_service import get_latest_thread_state_for_user
    snap = get_latest_thread_state_for_user(job1.thread_id, job1.user_id)
    assert snap.snapshot_kind == "restored_input"
    assert snap.state_payload["business_type"] == "cafe"
    assert snap.state_payload["user_input"] == "resume with more details"


def test_waiting_generation_job_exposes_pending_option_question(monkeypatch):
    class MockGraphWaiting:
        def invoke(self, payload: dict, config: dict | None = None) -> dict:
            state = dict(payload)
            state["__interrupt__"] = [
                FakeInterrupt(
                    {
                        "type": "option_question",
                        "job_id": state["job_id"],
                        "thread_id": state["thread_id"],
                        "option_question": {
                            "field": "business_type",
                            "question": "어떤 업종의 광고인가요?",
                            "options": [
                                {"id": 1, "label": "카페", "value": "cafe"},
                                {"id": 2, "label": "직접 입력", "value": "custom"},
                            ],
                        },
                    }
                )
            ]
            state["status"] = "waiting_user_input"
            state["context"] = {"business_type": "beauty_nail"}
            state["missing_fields"] = ["item_or_service"]
            state["messages"] = []
            return state

    monkeypatch.setattr("orchestrator.app.generation_jobs.execution.get_generation_job_graph", lambda: MockGraphWaiting())

    request = GenerationJobCreateRequest(user_input="광고 만들어줘", run_mode="graph_job")
    job = create_generation_job(request)
    executed = execute_generation_job_graph(job.job_id, request)

    assert executed.status == "waiting_user_input"
    assert executed.metadata["pending_interrupt"]["type"] == "option_question"
    assert executed.metadata["pending_interrupt"]["option_question"]["field"] == "business_type"
    assert executed.metadata["context"]["business_type"] == "beauty_nail"
    assert executed.metadata["missing_fields"] == ["item_or_service"]
    messages, _total = list_chat_messages(job.thread_id, user_id=job.user_id)
    assert messages[-1].content == "어떤 업종의 광고인가요?"


def test_resume_generation_job_graph_continues_waiting_job(monkeypatch):
    calls = []
    expected_job_id = None
    expected_thread_id = None

    class MockSharedGraph:
        def invoke(self, payload, config: dict | None = None) -> dict:
            nonlocal expected_job_id, expected_thread_id
            calls.append(payload)
            if len(calls) == 1:
                state = dict(payload)
                expected_job_id = state["job_id"]
                expected_thread_id = state["thread_id"]
                state["__interrupt__"] = [
                    FakeInterrupt(
                        {
                            "type": "option_question",
                            "job_id": state["job_id"],
                            "thread_id": state["thread_id"],
                            "option_question": {
                                "field": "business_type",
                                "question": "어떤 업종인가요?",
                                "options": [{"id": 1, "label": "카페", "value": "cafe"}],
                            },
                        }
                    )
                ]
                state["status"] = "waiting_user_input"
                state["messages"] = [{"role": "assistant", "content": "어떤 업종인가요?"}]
                return state

            assert getattr(payload, "resume", None) == {
                "job_id": expected_job_id,
                "thread_id": expected_thread_id,
                "field": "business_type",
                "value": "cafe",
                "display_text": "카페",
            }
            return {
                "job_id": expected_job_id,
                "thread_id": expected_thread_id,
                "status": "done",
                "result_payload": {"final_image_path": "/fake/final.png"},
                "final_image_path": "/fake/final.png",
            }

    shared_graph = MockSharedGraph()
    monkeypatch.setattr("orchestrator.app.generation_jobs.execution.get_generation_job_graph", lambda: shared_graph)

    request = GenerationJobCreateRequest(user_input="광고 만들어줘", run_mode="graph_job")
    job = create_generation_job(request)
    job = execute_generation_job_graph(job.job_id, request)
    assert job.status == "waiting_user_input"

    answer = GenerationJobAnswerRequest(field="business_type", value="cafe", display_text="카페")
    resumed = resume_generation_job_graph(job.job_id, answer)

    assert resumed.status == "done"
    assert len(calls) == 2
    messages, _total = list_chat_messages(job.thread_id)
    assert [message.content for message in messages if message.role in {"user", "assistant"}] == [
        "광고 만들어줘",
        "어떤 업종인가요?",
        "카페",
    ]


def test_resume_generation_job_graph_passes_scope_to_next_interrupt_waiting_update(monkeypatch):
    captured = {}
    job = _graph_job_response(
        job_id="job_waiting",
        thread_id="thread_waiting",
        user_id="user_a",
        status="running",
        progress=GenerationProgress(progress_percent=50, current_stage="planning"),
    )

    class MockGraph:
        def invoke(self, payload, config: dict | None = None) -> dict:
            return {
                "job_id": "job_waiting",
                "thread_id": "thread_waiting",
                "status": "waiting_user_input",
                "__interrupt__": [
                    FakeInterrupt(
                        {
                            "type": "option_question",
                            "job_id": "job_waiting",
                            "thread_id": "thread_waiting",
                            "option_question": {
                                "field": "item_or_service",
                                "question": "홍보할 상품이나 서비스는 무엇인가요?",
                                "options": [{"id": 1, "label": "대표 메뉴", "value": "대표 메뉴"}],
                            },
                        }
                    )
                ],
                "messages": [{"role": "assistant", "content": "홍보할 상품이나 서비스는 무엇인가요?"}],
            }

    def mark_waiting(*args, **kwargs):
        captured.update(kwargs)
        return _graph_job_response(
            job_id="job_waiting",
            thread_id="thread_waiting",
            user_id="user_a",
            status="waiting_user_input",
            progress=GenerationProgress(progress_percent=50, current_stage="waiting_user_input"),
        )

    monkeypatch.setattr(execution, "get_generation_job", lambda job_id, **kwargs: job)
    monkeypatch.setattr("orchestrator.app.generation_jobs.execution.get_generation_job_graph", lambda: MockGraph())
    monkeypatch.setattr("orchestrator.app.generation_jobs.execution.mark_generation_job_running", lambda *args, **kwargs: job)
    monkeypatch.setattr("orchestrator.app.generation_jobs.execution.append_generation_job_user_answer_message", lambda *args, **kwargs: None)
    monkeypatch.setattr("orchestrator.app.generation_jobs.service.mark_generation_job_waiting_user_input", mark_waiting)

    answer = GenerationJobAnswerRequest(field="business_type", value="cafe", display_text="카페")
    resumed = resume_generation_job_graph(
        "job_waiting",
        answer,
        allow_running=True,
        workspace_id="11111111-1111-1111-1111-111111111111",
        user_id="user_a",
    )

    assert resumed.status == "waiting_user_input"
    assert captured["workspace_id"] == "11111111-1111-1111-1111-111111111111"
    assert captured["user_id"] == "user_a"

def test_resume_generation_job_graph_marks_failed_when_graph_raises(monkeypatch):
    calls = []
    expected_job_id = None
    expected_thread_id = None

    class MockSharedGraph:
        def invoke(self, payload, config: dict | None = None) -> dict:
            nonlocal expected_job_id, expected_thread_id
            calls.append(payload)
            if len(calls) == 1:
                state = dict(payload)
                expected_job_id = state["job_id"]
                expected_thread_id = state["thread_id"]
                state["__interrupt__"] = [
                    FakeInterrupt(
                        {
                            "type": "option_question",
                            "job_id": state["job_id"],
                            "thread_id": state["thread_id"],
                            "option_question": {
                                "field": "item_or_service",
                                "question": "홍보할 상품이나 서비스는 무엇인가요?",
                                "options": [{"id": 1, "label": "대표 메뉴", "value": "대표 메뉴"}],
                            },
                        }
                    )
                ]
                state["status"] = "waiting_user_input"
                state["messages"] = [{"role": "assistant", "content": "홍보할 상품이나 서비스는 무엇인가요?"}]
                return state

            raise RuntimeError("resume graph crashed while planning image generation")

    shared_graph = MockSharedGraph()
    monkeypatch.setattr("orchestrator.app.generation_jobs.execution.get_generation_job_graph", lambda: shared_graph)

    request = GenerationJobCreateRequest(user_input="햄버거집 광고 만들어줘", run_mode="graph_job")
    job = create_generation_job(request)
    waiting = execute_generation_job_graph(job.job_id, request)
    assert waiting.status == "waiting_user_input"

    answer = GenerationJobAnswerRequest(field="item_or_service", value="햄버거 대표 메뉴", display_text="햄버거 대표 메뉴")
    resumed = resume_generation_job_graph(waiting.job_id, answer)

    assert resumed.status == "failed"
    assert resumed.progress.current_stage == "failed"
    assert resumed.error is not None
    assert resumed.error.error_code == "generation_job_execution_failed"
    assert resumed.metadata["execution_mode"] == "graph_resume_failed"
    assert "resume graph crashed" in resumed.error.detail


# ===== from test_generation_job_message_linkage.py =====
from orchestrator.app.api.schemas.chat_threads import ChatMessageResponse

def test_chat_message_schema_allows_job_and_event():
    msg = ChatMessageResponse(
        message_id="msg_1",
        thread_id="thread_1",
        role="user",
        content="hello",
        job_id="job_1",
        event_type="user_input",
        sequence_no=1,
        created_at="2026-06-05T00:00:00Z",
        updated_at="2026-06-05T00:00:00Z"
    )
    assert msg.job_id == "job_1"
    assert msg.event_type == "user_input"


# ===== from test_generation_job_modal_execution.py =====
from datetime import datetime, timezone

from orchestrator.app.api.schemas.common import ErrorResponse
from orchestrator.app.api.schemas.generation_jobs import GenerationJobCreateRequest, GenerationJobResponse, GenerationProgress
from orchestrator.app.generation_jobs import service
from orchestrator.app.modal.errors import ModalJobPollError
from orchestrator.app.modal.schemas import ModalPollResult
from orchestrator.app.modal.schemas import ModalSubmitResult


def _job(status="queued") -> GenerationJobResponse:
    now = datetime.now(timezone.utc).isoformat()
    return GenerationJobResponse(
        job_id="job_modal",
        thread_id="thread_modal",
        status=status,
        progress=GenerationProgress(progress_percent=0, current_stage=status),
        selected_reference_template_id=None,
        output_path=None,
        result_payload=None,
        error=None,
        created_at=now,
        updated_at=now,
        metadata={"requested_run_mode": "flux2_klein_4b", "effective_run_mode": "flux2_klein_4b"},
    )


def _row():
    return {
        "id": "job_uuid",
        "public_job_id": "job_modal",
        "workspace_id": "workspace_uuid",
        "thread_id": "thread_uuid",
        "run_mode": "flux2_klein_4b",
        "engine": "flux2_klein_4b",
        "prompt_preview": "Create an ad",
        "metadata": {"public_thread_id": "thread_modal"},
    }


def test_modal_router_policy_only_applies_to_modal_backend(monkeypatch):
    request = GenerationJobCreateRequest(user_input="Create an ad", run_mode="flux2_klein_4b")

    monkeypatch.setenv("EASYADS_T2I_EXECUTION_BACKEND", "local")
    assert service.should_route_generation_job_to_modal(request) is False

    monkeypatch.setenv("EASYADS_T2I_EXECUTION_BACKEND", "modal")
    assert service.should_route_generation_job_to_modal(request) is True

    gpt_request = GenerationJobCreateRequest(user_input="Create an ad", run_mode="gpt_image_2_actual")
    assert service.should_route_generation_job_to_modal(gpt_request) is False

    real_flux_request = GenerationJobCreateRequest(user_input="Create an ad", run_mode="flux2_klein_4b")
    assert service.should_route_generation_job_to_modal(real_flux_request) is True

    real_sd35_request = GenerationJobCreateRequest(user_input="Create an ad", run_mode="sd35_large_real")
    assert service.should_route_generation_job_to_modal(real_sd35_request) is True


def test_modal_disabled_marks_job_failed_without_local_model_execution(monkeypatch):
    monkeypatch.setenv("EASYADS_T2I_EXECUTION_BACKEND", "modal")
    monkeypatch.delenv("EASYADS_ENABLE_MODAL_EXECUTION", raising=False)
    monkeypatch.setattr(service, "_use_postgres_backend", lambda: True)
    captured = {}

    def fake_failed(job_id, error, metadata=None):
        captured["job_id"] = job_id
        captured["error"] = error
        return _job(status="failed").model_copy(update={"error": ErrorResponse(**error)})

    monkeypatch.setattr(service, "mark_generation_job_failed", fake_failed)

    result = service.maybe_submit_generation_job_to_modal(
        _job(),
        GenerationJobCreateRequest(user_input="Create an ad", run_mode="flux2_klein_4b"),
    )

    assert result.status == "failed"
    assert captured["error"]["error_code"] == "modal_execution_not_enabled"


def test_modal_enabled_submits_and_returns_latest_job(monkeypatch):
    monkeypatch.setenv("EASYADS_T2I_EXECUTION_BACKEND", "modal")
    monkeypatch.setenv("EASYADS_ENABLE_MODAL_EXECUTION", "true")
    monkeypatch.setattr(service, "_use_postgres_backend", lambda: True)
    monkeypatch.setattr(service.generation_job_repo, "get_generation_job_row", lambda job_id: _row())
    captured = {}

    def fake_submit(job_row, modal_request):
        captured["job_row"] = job_row
        captured["modal_request"] = modal_request
        return ModalSubmitResult(submitted=True, modal_call_id="modal_call_1", status="submitted")

    monkeypatch.setattr(service, "submit_generation_job_to_modal", fake_submit)
    monkeypatch.setattr(service, "get_generation_job", lambda job_id: _job(status="running"))

    result = service.maybe_submit_generation_job_to_modal(
        _job(),
        GenerationJobCreateRequest(user_input="Create an ad", run_mode="flux2_klein_4b"),
    )

    assert result.status == "running"
    assert captured["modal_request"].engine == "flux2_klein_4b"
    assert captured["modal_request"].job_id == "job_modal"


def test_modal_backend_records_model_provider_as_modal(monkeypatch):
    monkeypatch.setenv("EASYADS_T2I_EXECUTION_BACKEND", "modal")

    request = GenerationJobCreateRequest(user_input="Create an ad", run_mode="flux2_klein_4b")

    assert service._model_provider_for_request(request) == "modal"
    assert service._model_name_for_run_mode(request.run_mode) == "flux2_klein_4b"

    sd35_request = GenerationJobCreateRequest(user_input="Create an ad", run_mode="sd35_large_real")
    assert service._model_provider_for_request(sd35_request) == "modal"
    assert service._model_name_for_run_mode(sd35_request.run_mode) == "sd35_large"


def test_modal_poll_adapter_unavailable_does_not_fail_job(monkeypatch):
    monkeypatch.setenv("EASYADS_MODAL_POLL_ON_GET", "true")
    monkeypatch.setattr(service, "_use_postgres_backend", lambda: True)
    events = []
    row = {**_row(), "modal_call_id": "modal_call_1", "status": "running"}

    monkeypatch.setattr(service.generation_job_repo, "get_generation_job_row", lambda job_id: row)

    def raise_poll(job_id):
        raise ModalJobPollError("poll adapter unavailable")

    monkeypatch.setattr(service, "poll_and_process_modal_generation_job", raise_poll)
    monkeypatch.setattr(
        service.generation_job_event_repo,
        "record_generation_job_event",
        lambda **kwargs: events.append(kwargs) or {"id": "event_uuid"},
    )

    result = service.maybe_poll_generation_job_from_modal(_job(status="running"))

    assert result.status == "running"
    assert events[0]["event_type"] == "modal_poll_unavailable"
    assert events[0]["payload"]["error_code"] == "modal_poll_adapter_unavailable"


def test_graph_modal_pending_polls_through_graph_completion_path(monkeypatch):
    captured = {}

    def fake_graph_poll(job_id, **kwargs):
        captured["job_id"] = job_id
        return _job(status="done")

    monkeypatch.setattr(service, "_use_postgres_backend", lambda: False)
    monkeypatch.setattr(
        "orchestrator.app.generation_jobs.execution.poll_and_process_graph_modal_generation_job",
        fake_graph_poll,
    )

    job = _job(status="running").model_copy(
        update={
            "metadata": {
                "requested_run_mode": "graph_job",
                "effective_run_mode": "graph_job",
                "graph_modal_pending": True,
                "modal_call_id": "modal_call_graph",
            }
        }
    )

    result = service.maybe_poll_generation_job_from_modal(job)

    assert result.status == "done"
    assert captured["job_id"] == "job_modal"


def test_modal_success_uses_storage_backed_result_payload_contract(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    captured = {}
    poll_result = ModalPollResult(
        status="succeeded",
        modal_call_id="modal_call_1",
        image_b64="aW1hZ2U=",
        result_payload={"schema_version": "result_artifact_v1"},
    )

    from orchestrator.app.modal import service as modal_service

    monkeypatch.setattr(modal_service.job_repo, "get_generation_job_row", lambda job_id: _row() | {"modal_call_id": "modal_call_1"})
    monkeypatch.setattr(modal_service, "poll_modal_t2i_result", lambda modal_call_id, client=None: poll_result)
    monkeypatch.setattr(modal_service, "_record_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(modal_service, "_record_usage", lambda *args, **kwargs: None)

    def fake_mark_done(job_id, result_payload, output_path=None, metadata=None):
        captured["job_id"] = job_id
        captured["result_payload"] = result_payload
        captured["output_path"] = output_path
        return _job(status="done").model_copy(update={"result_payload": result_payload, "output_path": output_path})

    monkeypatch.setattr(service_module := __import__("orchestrator.app.generation_jobs.service", fromlist=["service"]), "mark_generation_job_done", fake_mark_done)
    monkeypatch.setattr(service_module, "get_generation_job", lambda job_id: _job(status="running"))
    monkeypatch.setattr(service_module, "mark_generation_job_running", lambda job_id, stage="running": _job(status="running"))
    monkeypatch.setattr(service_module, "mark_generation_job_failed", lambda job_id, error, metadata=None: _job(status="failed"))

    result = modal_service.poll_and_process_modal_generation_job(job_id="job_modal")

    assert result.status == "done"
    assert captured["job_id"] == "job_modal"
    assert captured["result_payload"]["schema_version"] == "result_artifact_v1"
    assert captured["result_payload"]["render_mode"] == "modal"
    assert captured["result_payload"]["final_image_path"] == "data/outputs/job_modal/final_0.png"
    assert "image_b64" not in str(captured["result_payload"])
    assert "image_bytes" not in str(captured["result_payload"])


# ===== from test_generation_job_persistence_db_backend.py =====
from contextlib import contextmanager
from datetime import datetime, timezone

from orchestrator.app.api.schemas.generation_jobs import GenerationJobCreateRequest
from orchestrator.app.generation_jobs import service


from unittest.mock import MagicMock

@contextmanager
def fake_db_transaction__test_generation_job_persistence_db_backend():
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    yield conn


def _row__test_generation_job_persistence_db_backend(status="queued", metadata=None, error=None):
    now = datetime.now(timezone.utc)
    return {
        "id": "job_uuid",
        "public_job_id": "job_db",
        "workspace_id": "11111111-1111-1111-1111-111111111111",
        "thread_id": "thread_uuid",
        "requested_by": "demo_user",
        "status": status,
        "current_stage": status,
        "progress_percent": 50 if status == "running" else 0,
        "selected_reference_template_id": "seed_1",
        "output_path": None,
        "result_payload": None,
        "error": error or {},
        "created_at": now,
        "updated_at": now,
        "metadata": metadata or {
            "public_thread_id": "thread_db",
            "requested_run_mode": "queued_only",
            "effective_run_mode": "queued_only",
            "execution_mode": "queued_only",
        },
    }


def test_postgres_create_records_queued_event_and_active_thread(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")
    monkeypatch.setattr(service, "db_transaction", fake_db_transaction__test_generation_job_persistence_db_backend)
    events = []
    thread_updates = []
    captured = {}

    monkeypatch.setattr(service.workspace_repo, "get_workspace_for_user", lambda *, workspace_id, user_id, connection=None: {"id": workspace_id, "owner_user_id": None})
    monkeypatch.setattr(service.chat_thread_repo, "create_chat_thread", lambda **kwargs: {"id": "thread_uuid", "public_thread_id": "thread_db"})
    monkeypatch.setattr(service.chat_message_repo, "append_chat_message", lambda **kwargs: {"id": "msg_uuid"})
    monkeypatch.setattr(service.state_service, "get_latest_thread_state_snapshot", lambda **kwargs: None)
    monkeypatch.setattr(service.state_service, "save_thread_state_snapshot", lambda **kwargs: {"snapshot_id": "snap_uuid"})
    monkeypatch.setattr(service.chat_thread_repo, "set_chat_thread_active_job", lambda *args, **kwargs: thread_updates.append((args, kwargs)) or {"id": "thread_uuid"})
    monkeypatch.setattr(service.chat_message_repo, "append_chat_message", lambda **kwargs: {"id": "msg_uuid"})
    monkeypatch.setattr(service.state_service, "get_latest_thread_state_snapshot", lambda **kwargs: None)
    monkeypatch.setattr(service.state_service, "save_thread_state_snapshot", lambda **kwargs: {"snapshot_id": "snap_uuid"})
    monkeypatch.setattr(service.generation_job_event_repo, "record_generation_job_event", lambda **kwargs: events.append(kwargs) or {"id": "event_uuid"})
    monkeypatch.setattr(service.chat_thread_repo, "get_chat_thread_by_public_id", lambda thread_id, **kwargs: {"id": "thread_uuid", "active_job_id": "job_uuid"})
    monkeypatch.setattr(service.chat_message_repo, "append_generation_job_chat_event", lambda **kwargs: {"id": "msg_uuid"})

    def create_row(**kwargs):
        captured.update(kwargs)
        metadata = dict(kwargs["metadata"])
        metadata["public_thread_id"] = "thread_db"
        return _row__test_generation_job_persistence_db_backend(metadata=metadata)

    monkeypatch.setattr(service.generation_job_repo, "create_generation_job_row", create_row)

    job = service.create_generation_job(
        GenerationJobCreateRequest(user_input="Create an ad", user_id="demo_user", workspace_id="11111111-1111-1111-1111-111111111111", run_mode="queued_only", selected_reference_template_id="seed_1")
    )

    assert job.job_id == "job_db"
    assert job.thread_id == "thread_db"
    assert job.status == "queued"
    assert captured["workspace_id"] == "11111111-1111-1111-1111-111111111111"
    assert captured["thread_id"] == "thread_uuid"
    assert events[0]["event_type"] == "queued"
    assert thread_updates[0][1]["status"] == "generating"

    assert captured["engine"] is None
    assert captured["model_provider"] is None
    assert captured["model_name"] is None


def test_postgres_get_converts_db_row_to_response(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")
    monkeypatch.setattr(service.generation_job_repo, "get_generation_job_internal_by_public_id", lambda job_id: _row__test_generation_job_persistence_db_backend())

    job = service.get_generation_job("job_db")

    assert job.job_id == "job_db"
    assert job.thread_id == "thread_db"
    assert job.selected_reference_template_id == "seed_1"
    assert job.metadata["requested_run_mode"] == "queued_only"


def test_postgres_mark_running_updates_row_and_records_event(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")
    monkeypatch.setattr(service, "db_transaction", fake_db_transaction__test_generation_job_persistence_db_backend)
    events = []
    thread_updates = []

    def mark_running(job_id, current_stage=None, connection=None):
        row = _row__test_generation_job_persistence_db_backend(status="running")
        row["current_stage"] = current_stage
        return row

    monkeypatch.setattr(service.generation_job_repo, "mark_generation_job_running_row", mark_running)
    monkeypatch.setattr(service.generation_job_event_repo, "record_generation_job_event", lambda **kwargs: events.append(kwargs) or {"id": "event_uuid"})
    monkeypatch.setattr(service.chat_thread_repo, "update_chat_thread_status", lambda *args, **kwargs: thread_updates.append((args, kwargs)) or {"id": "thread_uuid"})
    monkeypatch.setattr(service.chat_message_repo, "append_chat_message", lambda **kwargs: {"id": "msg_uuid"})
    monkeypatch.setattr(service.state_service, "get_latest_thread_state_snapshot", lambda **kwargs: None)
    monkeypatch.setattr(service.state_service, "save_thread_state_snapshot", lambda **kwargs: {"snapshot_id": "snap_uuid"})

    job = service.mark_generation_job_running("job_db", "t2i_running")

    assert job.status == "running"
    assert job.progress.current_stage == "t2i_running"
    assert job.progress.progress_percent == 50
    assert events[0]["event_type"] == "running"
    assert events[0]["payload"]["current_stage"] == "t2i_running"
    assert thread_updates[0][1]["status"] == "generating"


def test_postgres_mark_failed_updates_row_thread_and_event(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")
    monkeypatch.setattr(service, "db_transaction", fake_db_transaction__test_generation_job_persistence_db_backend)
    events = []
    thread_updates = []
    snapshots = []
    state = _row__test_generation_job_persistence_db_backend()

    def mark_failed(job_id, error, metadata=None, connection=None):
        state.update({"status": "failed", "current_stage": "failed", "error": error, "metadata": metadata or state["metadata"]})
        return state

    monkeypatch.setattr(service.generation_job_repo, "get_generation_job_row", lambda job_id, connection=None: state)
    monkeypatch.setattr(service.generation_job_repo, "mark_generation_job_failed_row", mark_failed)
    monkeypatch.setattr(service.generation_job_event_repo, "record_generation_job_event", lambda **kwargs: events.append(kwargs) or {"id": "event_uuid"})
    monkeypatch.setattr(service.chat_thread_repo, "fail_chat_thread_generation", lambda **kwargs: thread_updates.append(kwargs) or {"id": "thread_uuid"})
    monkeypatch.setattr(service.chat_message_repo, "append_chat_message", lambda **kwargs: {"id": "msg_uuid"})
    monkeypatch.setattr(service.chat_message_repo, "append_generation_job_chat_event", lambda **kwargs: {"id": "msg_uuid"})
    monkeypatch.setattr(service.state_service, "get_latest_thread_state_snapshot", lambda **kwargs: None)
    monkeypatch.setattr(service.state_service, "save_thread_state_snapshot", lambda **kwargs: snapshots.append(kwargs) or {"snapshot_id": "snap_uuid"})
    monkeypatch.setattr(service.chat_thread_repo, "get_chat_thread_by_public_id", lambda thread_id, **kwargs: {"id": "thread_uuid", "active_job_id": "job_uuid"})

    failed = service.mark_generation_job_failed("job_db", {"error_code": "x", "message": "failed", "detail": "missing package"})

    assert failed.status == "failed"
    assert failed.error.error_code == "x"
    assert events[0]["event_type"] == "failed"
    assert events[0]["payload"]["error_code"] == "x"
    assert thread_updates[0]["expected_active_job_id"] == "job_uuid"
    assert snapshots[0]["metadata"]["message"] == "failed"
    assert snapshots[0]["metadata"]["detail"] == "missing package"


def test_postgres_record_generation_job_lifecycle_event_records_scoped_event(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")
    monkeypatch.setattr(service, "db_transaction", fake_db_transaction__test_generation_job_persistence_db_backend)
    events = []
    row = _row__test_generation_job_persistence_db_backend()
    row["workspace_id"] = "workspace_uuid"

    monkeypatch.setattr(
        service,
        "_resolve_db_workspace_for_public_access",
        lambda requested_workspace_id=None, user_id=None, connection=None: "workspace_uuid",
    )
    monkeypatch.setattr(
        service.generation_job_repo,
        "get_generation_job_scoped_by_public_id",
        lambda job_id, workspace_id, connection=None, for_update=False: row,
    )
    monkeypatch.setattr(
        service.generation_job_event_repo,
        "record_generation_job_event",
        lambda **kwargs: events.append(kwargs) or {"id": "event_uuid"},
    )

    service.record_generation_job_lifecycle_event(
        "job_db",
        "background_enqueued",
        message="graph_resume",
        payload={"task": "graph_resume", "source": "answer_route"},
        workspace_id="workspace_uuid",
        user_id="user_uuid",
    )

    assert events == [
        {
            "workspace_id": "workspace_uuid",
            "thread_id": "thread_uuid",
            "job_id": "job_uuid",
            "event_type": "background_enqueued",
            "message": "graph_resume",
            "payload": {"task": "graph_resume", "source": "answer_route"},
            "connection": events[0]["connection"],
        }
    ]


# ===== from test_generation_job_r2_persistence.py =====
from contextlib import contextmanager

from orchestrator.app.generation_jobs import service
from orchestrator.app.storage.errors import R2UploadError, R2StorageUnavailableError


from unittest.mock import MagicMock

@contextmanager
def fake_db_transaction__test_generation_job_r2_persistence():
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    yield conn


def _base_row():
    return {
        "id": "job_uuid",
        "public_job_id": "job_db",
        "workspace_id": "workspace_uuid",
        "thread_id": "thread_uuid",
        "requested_by": "demo_user",
        "status": "queued",
        "current_stage": "queued",
        "progress_percent": 0,
        "selected_reference_template_id": None,
        "output_path": None,
        "result_payload": None,
        "error": {},
        "metadata": {"public_thread_id": "thread_db"},
        "created_at": "2026-06-02T00:00:00+00:00",
        "updated_at": "2026-06-02T00:00:00+00:00",
    }


def _patch_mark_done(monkeypatch, row):
    def mark_done(job_id, result_payload, output_path=None, metadata=None, connection=None):
        row.update(
            {
                "status": "done",
                "current_stage": "completed",
                "progress_percent": 100,
                "result_payload": result_payload,
                "output_path": output_path,
                "error": {},
                "metadata": metadata or row["metadata"],
            }
        )
        return row

    monkeypatch.setattr(service.generation_job_repo, "mark_generation_job_done_row", mark_done)


def test_mark_done_r2_disabled_keeps_local_dev_placeholder(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")
    monkeypatch.setenv("EASYADS_ASSET_STORAGE_BACKEND", "local_dev")
    monkeypatch.setenv("EASYADS_ENABLE_R2_UPLOAD", "false")
    monkeypatch.setenv("EASYADS_R2_UPLOAD_REQUIRED", "false")
    monkeypatch.setattr(service, "db_transaction", fake_db_transaction__test_generation_job_r2_persistence)
    events = []
    assets = []
    outputs = []
    row = _base_row()

    monkeypatch.setattr(service.generation_job_repo, "get_generation_job_row", lambda job_id, connection=None: row)
    monkeypatch.setattr(service.generation_job_repo, "update_generation_job_row", lambda job_id, connection=None, **fields: row.update(fields) or row)
    _patch_mark_done(monkeypatch, row)
    monkeypatch.setattr(service.asset_repo, "create_asset", lambda **kwargs: assets.append({"id": "asset_uuid", **kwargs}) or assets[-1])
    monkeypatch.setattr(service.generation_output_repo, "create_generation_output", lambda **kwargs: outputs.append({"id": "output_uuid", "asset_id": kwargs["asset_id"], **kwargs}) or outputs[-1])
    monkeypatch.setattr(service.generation_output_repo, "mark_output_final", lambda output_id, *args, **kwargs: {"id": output_id, "asset_id": "asset_uuid", "is_final": True})
    monkeypatch.setattr("orchestrator.app.archive.service.sync_archive_for_output", MagicMock())
    thread_updates = []
    monkeypatch.setattr(service.chat_thread_repo, "complete_chat_thread_generation", lambda **kwargs: thread_updates.append(kwargs) or {"id": "thread_uuid"})
    monkeypatch.setattr(service.chat_message_repo, "append_chat_message", lambda **kwargs: {"id": "msg_uuid"})
    monkeypatch.setattr(service.chat_message_repo, "append_generation_job_chat_event", lambda **kwargs: {"id": "msg_uuid"})
    monkeypatch.setattr(service.chat_thread_repo, "get_chat_thread_by_public_id", lambda thread_id, **kwargs: {"id": "thread_uuid", "active_job_id": "job_uuid"})
    monkeypatch.setattr(service.state_service, "get_latest_thread_state_snapshot", lambda **kwargs: None)
    monkeypatch.setattr(service.state_service, "save_thread_state_snapshot", lambda **kwargs: {"snapshot_id": "snap_uuid"})
    monkeypatch.setattr(service.generation_job_event_repo, "record_generation_job_event", lambda **kwargs: events.append(kwargs) or {"id": "event_uuid"})

    done = service.mark_generation_job_done(
        "job_db",
        result_payload={"schema_version": "result_artifact_v1", "final_image_path": "data/outputs/job_db/final_0.png"},
        output_path="data/outputs/job_db/final_0.png",
    )

    assert done.status == "done"
    assert assets[0]["storage_provider"] == "local_dev"
    assert done.result_payload["final_asset_id"] == "asset_uuid"
    assert done.result_payload["storage_provider"] == "local_dev"
    assert done.result_payload["bucket"] == "local-dev"
    assert done.result_payload["object_key"] == "data/outputs/job_db/final_0.png"
    assert done.result_payload.get("final_image_url") is None
    assert done.result_payload.get("download_url") is None
    assert "r2_upload_started" not in [event["event_type"] for event in events]
    assert thread_updates[0]["expected_active_job_id"] == "job_uuid"
    assert thread_updates[0]["final_output_id"] == "output_uuid"

def test_mark_done_r2_success_persists_r2_asset_and_urls(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")
    monkeypatch.setenv("EASYADS_ENABLE_R2_UPLOAD", "true")
    monkeypatch.setattr(service, "db_transaction", fake_db_transaction__test_generation_job_r2_persistence)
    events = []
    assets = []
    outputs = []
    state = {"row": _base_row()}

    def get_row(job_id, connection=None):
        return state["row"]

    def update_row(job_id, connection=None, **fields):
        state["row"] = {**state["row"], **fields}
        return state["row"]

    monkeypatch.setattr(service.generation_job_repo, "get_generation_job_row", get_row)
    monkeypatch.setattr(service.generation_job_repo, "update_generation_job_row", update_row)
    _patch_mark_done(monkeypatch, state["row"])
    monkeypatch.setattr(
        service,
        "upload_file_to_r2",
        lambda **kwargs: type(
            "Uploaded",
            (),
            {
                "bucket": "easyads-dev",
                "object_key": "workspaces/workspace_uuid/threads/thread_db/jobs/job_db/final_0.png",
                "storage_provider": "r2",
                "mime_type": "image/png",
                "size_bytes": 123,
                "public_url": None,
                "final_image_url": "https://signed.example/final_0.png",
                "download_url": "https://signed.example/final_0.png",
                "signed_url_expires_at": "2026-06-03T00:00:00+00:00",
                "metadata": {"public_serving": True, "url_mode": "signed", "source": "generation_job_r2_upload"},
                "width": 1200,
                "height": 1200,
            },
        )(),
    )
    monkeypatch.setattr(service.asset_repo, "create_asset", lambda **kwargs: assets.append({"id": "asset_r2_uuid", **kwargs}) or assets[-1])
    monkeypatch.setattr(service.generation_output_repo, "create_generation_output", lambda **kwargs: outputs.append({"id": "output_uuid", "asset_id": kwargs["asset_id"], **kwargs}) or outputs[-1])
    monkeypatch.setattr(service.generation_output_repo, "mark_output_final", lambda output_id, *args, **kwargs: {"id": output_id, "asset_id": "asset_r2_uuid", "is_final": True})
    monkeypatch.setattr("orchestrator.app.archive.service.sync_archive_for_output", MagicMock())
    thread_updates = []
    monkeypatch.setattr(service.chat_thread_repo, "complete_chat_thread_generation", lambda **kwargs: thread_updates.append(kwargs) or {"id": "thread_uuid"})
    monkeypatch.setattr(service.chat_message_repo, "append_chat_message", lambda **kwargs: {"id": "msg_uuid"})
    monkeypatch.setattr(service.chat_message_repo, "append_generation_job_chat_event", lambda **kwargs: {"id": "msg_uuid"})
    monkeypatch.setattr(service.chat_thread_repo, "get_chat_thread_by_public_id", lambda thread_id, **kwargs: {"id": "thread_uuid", "active_job_id": "job_uuid"})
    monkeypatch.setattr(service.state_service, "get_latest_thread_state_snapshot", lambda **kwargs: None)
    monkeypatch.setattr(service.state_service, "save_thread_state_snapshot", lambda **kwargs: {"snapshot_id": "snap_uuid"})
    monkeypatch.setattr(service.generation_job_event_repo, "record_generation_job_event", lambda **kwargs: events.append(kwargs) or {"id": "event_uuid"})

    done = service.mark_generation_job_done(
        "job_db",
        result_payload={"schema_version": "result_artifact_v1", "final_image_path": "data/outputs/job_db/final_0.png"},
        output_path="data/outputs/job_db/final_0.png",
    )

    assert done.status == "done"
    assert assets[0]["storage_provider"] == "r2"
    assert outputs[0]["asset_id"] == "asset_r2_uuid"
    assert done.result_payload["final_image_url"] == "https://signed.example/final_0.png"
    assert done.result_payload["download_url"] == "https://signed.example/final_0.png"
    assert done.result_payload["final_asset_id"] == "asset_r2_uuid"
    assert [event["event_type"] for event in events] == ["r2_upload_started", "r2_upload_completed", "archive_linked", "done", "output_created"]
    assert thread_updates[0]["expected_active_job_id"] == "job_uuid"
    assert thread_updates[0]["final_output_id"] == "output_uuid"


def test_mark_done_r2_failure_falls_back_to_local_dev_when_not_required(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")
    monkeypatch.setenv("EASYADS_ENABLE_R2_UPLOAD", "true")
    monkeypatch.setenv("EASYADS_R2_UPLOAD_REQUIRED", "false")
    monkeypatch.setattr(service, "db_transaction", fake_db_transaction__test_generation_job_r2_persistence)
    events = []
    assets = []
    state = {"row": _base_row()}

    monkeypatch.setattr(service.generation_job_repo, "get_generation_job_row", lambda job_id, connection=None: state["row"])
    monkeypatch.setattr(service.generation_job_repo, "update_generation_job_row", lambda job_id, connection=None, **fields: state["row"].update(fields) or state["row"])
    _patch_mark_done(monkeypatch, state["row"])
    monkeypatch.setattr(service, "upload_file_to_r2", lambda **kwargs: (_ for _ in ()).throw(R2UploadError("R2 upload failed.")))
    monkeypatch.setattr(service.asset_repo, "create_asset", lambda **kwargs: assets.append({"id": "asset_local_uuid", **kwargs}) or assets[-1])
    monkeypatch.setattr(service.generation_output_repo, "create_generation_output", lambda **kwargs: {"id": "output_uuid", "asset_id": kwargs["asset_id"], **kwargs})
    monkeypatch.setattr(service.generation_output_repo, "mark_output_final", lambda output_id, *args, **kwargs: {"id": output_id, "asset_id": "asset_local_uuid", "is_final": True})
    monkeypatch.setattr("orchestrator.app.archive.service.sync_archive_for_output", MagicMock())
    thread_updates = []
    monkeypatch.setattr(service.chat_thread_repo, "complete_chat_thread_generation", lambda **kwargs: thread_updates.append(kwargs) or {"id": "thread_uuid"})
    monkeypatch.setattr(service.chat_message_repo, "append_chat_message", lambda **kwargs: {"id": "msg_uuid"})
    monkeypatch.setattr(service.chat_message_repo, "append_generation_job_chat_event", lambda **kwargs: {"id": "msg_uuid"})
    monkeypatch.setattr(service.chat_thread_repo, "get_chat_thread_by_public_id", lambda thread_id, **kwargs: {"id": "thread_uuid", "active_job_id": "job_uuid"})
    monkeypatch.setattr(service.state_service, "get_latest_thread_state_snapshot", lambda **kwargs: None)
    monkeypatch.setattr(service.state_service, "save_thread_state_snapshot", lambda **kwargs: {"snapshot_id": "snap_uuid"})
    monkeypatch.setattr(service.generation_job_event_repo, "record_generation_job_event", lambda **kwargs: events.append(kwargs) or {"id": "event_uuid"})

    done = service.mark_generation_job_done(
        "job_db",
        result_payload={"schema_version": "result_artifact_v1", "final_image_path": "data/outputs/job_db/final_0.png"},
        output_path="data/outputs/job_db/final_0.png",
    )

    assert done.status == "done"
    assert assets[0]["storage_provider"] == "local_dev"
    assert done.result_payload.get("final_image_url") is None
    assert done.result_payload.get("download_url") is None
    assert done.metadata["storage_warning"] == "r2_upload_failed_local_dev_fallback"
    assert [event["event_type"] for event in events] == ["r2_upload_started", "r2_upload_failed", "archive_linked", "done", "output_created"]
    assert done.result_payload["final_asset_id"] == "asset_local_uuid"
    assert done.result_payload["storage_provider"] == "local_dev"
    assert done.result_payload["bucket"] == "local-dev"
    assert done.result_payload["object_key"] == "data/outputs/job_db/final_0.png"
    assert thread_updates[0]["expected_active_job_id"] == "job_uuid"
    assert thread_updates[0]["final_output_id"] == "output_uuid"

def test_mark_done_r2_failure_required_marks_job_failed(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")
    monkeypatch.setenv("EASYADS_ENABLE_R2_UPLOAD", "true")
    monkeypatch.setenv("EASYADS_R2_UPLOAD_REQUIRED", "true")
    monkeypatch.setattr(service, "db_transaction", fake_db_transaction__test_generation_job_r2_persistence)
    events = []
    state = {"row": _base_row()}

    def get_row(job_id, connection=None):
        return state["row"]

    def update_row(job_id, connection=None, **fields):
        state["row"] = {**state["row"], **fields}
        return state["row"]

    def mark_failed(job_id, error, metadata=None, connection=None):
        state["row"] = {
            **state["row"],
            "status": "failed",
            "current_stage": "failed",
            "error": error,
            "metadata": metadata or state["row"]["metadata"],
        }
        return state["row"]

    monkeypatch.setattr(service.generation_job_repo, "get_generation_job_row", get_row)
    monkeypatch.setattr(service.generation_job_repo, "update_generation_job_row", update_row)
    monkeypatch.setattr(service.generation_job_repo, "mark_generation_job_failed_row", mark_failed)
    _patch_mark_done(monkeypatch, state["row"])
    monkeypatch.setattr(service, "upload_file_to_r2", lambda **kwargs: (_ for _ in ()).throw(R2UploadError("R2 upload failed.")))
    monkeypatch.setattr(service.asset_repo, "create_asset", lambda **kwargs: (_ for _ in ()).throw(AssertionError("local asset fallback should not run")))
    monkeypatch.setattr(service.generation_output_repo, "create_generation_output", lambda **kwargs: (_ for _ in ()).throw(AssertionError("output should not be created")))
    monkeypatch.setattr(service.chat_thread_repo, "fail_chat_thread_generation", lambda **kwargs: {"id": "thread_uuid"})
    monkeypatch.setattr(service.chat_message_repo, "append_chat_message", lambda **kwargs: {"id": "msg_uuid"})
    monkeypatch.setattr(service.chat_message_repo, "append_generation_job_chat_event", lambda **kwargs: {"id": "msg_uuid"})
    monkeypatch.setattr(service.chat_thread_repo, "get_chat_thread_by_public_id", lambda thread_id, **kwargs: {"id": "thread_uuid", "active_job_id": "job_uuid"})
    monkeypatch.setattr(service.state_service, "get_latest_thread_state_snapshot", lambda **kwargs: None)
    monkeypatch.setattr(service.state_service, "save_thread_state_snapshot", lambda **kwargs: {"snapshot_id": "snap_uuid"})
    monkeypatch.setattr(service.generation_job_event_repo, "record_generation_job_event", lambda **kwargs: events.append(kwargs) or {"id": "event_uuid"})

    failed = service.mark_generation_job_done(
        "job_db",
        result_payload={"schema_version": "result_artifact_v1", "final_image_path": "data/outputs/job_db/final_0.png"},
        output_path="data/outputs/job_db/final_0.png",
    )

    assert failed.status == "failed"
    assert failed.error.error_code == "r2_upload_failed"
    assert [event["event_type"] for event in events] == ["r2_upload_started", "r2_upload_failed", "failed"]


def test_mark_done_r2_required_attempts_upload_even_without_enable_flag(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")
    monkeypatch.setenv("EASYADS_ENABLE_R2_UPLOAD", "false")
    monkeypatch.setenv("EASYADS_ASSET_STORAGE_BACKEND", "local_dev")
    monkeypatch.setenv("EASYADS_R2_UPLOAD_REQUIRED", "true")
    monkeypatch.setattr(service, "db_transaction", fake_db_transaction__test_generation_job_r2_persistence)
    events = []
    state = {"row": _base_row()}

    def mark_failed(job_id, error, metadata=None, connection=None):
        state["row"] = {
            **state["row"],
            "status": "failed",
            "current_stage": "failed",
            "error": error,
            "metadata": metadata or state["row"]["metadata"],
        }
        return state["row"]

    monkeypatch.setattr(service.generation_job_repo, "get_generation_job_row", lambda job_id, connection=None: state["row"])
    monkeypatch.setattr(service.generation_job_repo, "update_generation_job_row", lambda job_id, connection=None, **fields: state["row"].update(fields) or state["row"])
    monkeypatch.setattr(service.generation_job_repo, "mark_generation_job_failed_row", mark_failed)
    _patch_mark_done(monkeypatch, state["row"])
    monkeypatch.setattr(service, "upload_file_to_r2", lambda **kwargs: (_ for _ in ()).throw(R2StorageUnavailableError("R2 upload is unavailable.")))
    monkeypatch.setattr(service.asset_repo, "create_asset", lambda **kwargs: (_ for _ in ()).throw(AssertionError("local asset fallback should not run")))
    monkeypatch.setattr(service.generation_output_repo, "create_generation_output", lambda **kwargs: (_ for _ in ()).throw(AssertionError("output should not be created")))
    monkeypatch.setattr(service.chat_thread_repo, "fail_chat_thread_generation", lambda **kwargs: {"id": "thread_uuid"})
    monkeypatch.setattr(service.chat_message_repo, "append_generation_job_chat_event", lambda **kwargs: {"id": "msg_uuid"})
    monkeypatch.setattr(service.chat_thread_repo, "get_chat_thread_by_public_id", lambda thread_id, **kwargs: {"id": "thread_uuid", "active_job_id": "job_uuid"})
    monkeypatch.setattr(service.generation_job_event_repo, "record_generation_job_event", lambda **kwargs: events.append(kwargs) or {"id": "event_uuid"})

    failed = service.mark_generation_job_done(
        "job_db",
        result_payload={"schema_version": "result_artifact_v1", "final_image_path": "data/outputs/job_db/final_0.png"},
        output_path="data/outputs/job_db/final_0.png",
    )

    assert failed.status == "failed"
    assert failed.error.error_code == "r2_upload_failed"
    assert [event["event_type"] for event in events] == ["r2_upload_started", "r2_upload_failed", "failed"]


def test_mark_done_r2_required_fails_when_uploaded_asset_has_no_browser_url(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")
    monkeypatch.setenv("EASYADS_R2_UPLOAD_REQUIRED", "true")
    monkeypatch.setattr(service, "db_transaction", fake_db_transaction__test_generation_job_r2_persistence)
    events = []
    state = {"row": _base_row()}

    def update_row(job_id, connection=None, **fields):
        state["row"] = {**state["row"], **fields}
        return state["row"]

    def mark_failed(job_id, error, metadata=None, connection=None):
        state["row"] = {
            **state["row"],
            "status": "failed",
            "current_stage": "failed",
            "error": error,
            "metadata": metadata or state["row"]["metadata"],
        }
        return state["row"]

    monkeypatch.setattr(service.generation_job_repo, "get_generation_job_row", lambda job_id, connection=None: state["row"])
    monkeypatch.setattr(service.generation_job_repo, "update_generation_job_row", update_row)
    monkeypatch.setattr(service.generation_job_repo, "mark_generation_job_failed_row", mark_failed)
    _patch_mark_done(monkeypatch, state["row"])
    monkeypatch.setattr(
        service,
        "upload_file_to_r2",
        lambda **kwargs: type(
            "Uploaded",
            (),
            {
                "bucket": "easyads-dev",
                "object_key": "workspaces/workspace_uuid/threads/thread_db/jobs/job_db/final_0.png",
                "storage_provider": "r2",
                "mime_type": "image/png",
                "size_bytes": 123,
                "public_url": None,
                "final_image_url": None,
                "download_url": None,
                "signed_url_expires_at": None,
                "metadata": {"public_serving": False, "url_mode": "broken", "source": "generation_job_r2_upload"},
                "width": 1200,
                "height": 1200,
            },
        )(),
    )
    monkeypatch.setattr(service.asset_repo, "create_asset", lambda **kwargs: {"id": "asset_r2_uuid", **kwargs})
    monkeypatch.setattr(service.generation_output_repo, "create_generation_output", lambda **kwargs: (_ for _ in ()).throw(AssertionError("output should not be created")))
    monkeypatch.setattr(service.chat_thread_repo, "fail_chat_thread_generation", lambda **kwargs: {"id": "thread_uuid"})
    monkeypatch.setattr(service.chat_message_repo, "append_generation_job_chat_event", lambda **kwargs: {"id": "msg_uuid"})
    monkeypatch.setattr(service.chat_thread_repo, "get_chat_thread_by_public_id", lambda thread_id, **kwargs: {"id": "thread_uuid", "active_job_id": "job_uuid"})
    monkeypatch.setattr(service.generation_job_event_repo, "record_generation_job_event", lambda **kwargs: events.append(kwargs) or {"id": "event_uuid"})

    failed = service.mark_generation_job_done(
        "job_db",
        result_payload={"schema_version": "result_artifact_v1", "final_image_path": "data/outputs/job_db/final_0.png"},
        output_path="data/outputs/job_db/final_0.png",
    )

    assert failed.status == "failed"
    assert failed.error.error_code == "r2_upload_failed"
    assert [event["event_type"] for event in events] == ["r2_upload_started", "r2_upload_failed", "failed"]


# ===== from test_generation_job_run_mode_mapping.py =====
"""Characterization test for run_mode -> t2i engine routing."""

from orchestrator.app.api.routers.generation_jobs import T2I_RUN_MODE_TO_ENGINE


def test_run_mode_mapping_matches_legacy_elif_chain():
    # Exact behavior of the elif chain this mapping replaced.
    expected = {
        "gpt_image_1_actual": "gpt_image_1",
        "gpt_image_1_smoke": "gpt_image_1",
        "gpt_image_2_actual": "gpt_image_2",
        "gpt_image_2_smoke": "gpt_image_2",
        "sd35_local": "sd35_large",
        "sd35_local_smoke": "sd35_large",
        "sd35_large_real": "sd35_large",
        "flux2_klein_4b": "flux2_klein_4b",
        "flux_local": "flux2_klein_4b",
        "flux_local_smoke": "flux2_klein_4b",
        "flux_schnell_real": "flux2_klein_4b",
        "flux": "flux2_klein_4b",
        "flux_smoke": "flux2_klein_4b",
    }
    assert T2I_RUN_MODE_TO_ENGINE == expected


def test_non_t2i_modes_not_in_mapping():
    for mode in ("mock_immediate", "graph_job"):
        assert mode not in T2I_RUN_MODE_TO_ENGINE


# ===== from test_generation_job_service.py =====
from datetime import datetime, timedelta, timezone

import pytest

from orchestrator.app.api.schemas.generation_jobs import GenerationJobCreateRequest, GenerationJobResponse, GenerationProgress
from orchestrator.app.generation_jobs.service import (
    create_generation_job,
    get_generation_job,
    mark_generation_job_failed,
    mark_generation_job_running,
    maybe_mark_stale_generation_job_failed,
    reset_generation_job_store_for_tests,
)
from orchestrator.app.chat_threads.service import reset_chat_thread_store_for_tests
from orchestrator.app.chat_threads.state_service import (
    get_chat_state_snapshot_by_key,
    reset_chat_state_snapshot_store_for_tests,
)


@pytest.fixture(autouse=True)
def reset_store__test_generation_job_service():
    reset_generation_job_store_for_tests()
    reset_chat_thread_store_for_tests()
    reset_chat_state_snapshot_store_for_tests()
    yield
    reset_generation_job_store_for_tests()
    reset_chat_thread_store_for_tests()
    reset_chat_state_snapshot_store_for_tests()


def test_create_generation_job_defaults_and_lookup():
    job = create_generation_job(
        GenerationJobCreateRequest(
            user_input="Create a cafe ad",
            user_id="user_1",
            brand_kit_id="bk_1",
            selected_reference_template_id="seed_cafe_strawberry_feed_001",
            copy_generation_mode="auto_pilot",
            user_plan="free",
        )
    )

    assert job.job_id.startswith("job_")
    assert job.thread_id and job.thread_id.startswith("thread_")
    assert job.status == "queued"
    assert job.progress.progress_percent == 0
    assert job.progress.current_stage == "queued"
    assert "briefing" in job.progress.stage_order
    assert job.selected_reference_template_id == "seed_cafe_strawberry_feed_001"
    assert job.metadata["requested_run_mode"] == "queued_only"
    assert job.metadata["effective_run_mode"] == "queued_only"
    assert job.metadata["execution_mode"] == "queued_only"
    assert get_generation_job(job.job_id) == job


def test_create_generation_job_queued_only_metadata():
    job = create_generation_job(
        GenerationJobCreateRequest(
            user_input="Create an ad",
            run_mode="queued_only",
        )
    )

    assert job.status == "queued"
    assert job.metadata["requested_run_mode"] == "queued_only"
    assert job.metadata["effective_run_mode"] == "queued_only"
    assert job.metadata["execution_mode"] == "queued_only"


def test_create_generation_job_mock_immediate_pending_metadata():
    job = create_generation_job(
        GenerationJobCreateRequest(
            user_input="Create an ad",
            run_mode="mock_immediate",
        )
    )

    assert job.status == "queued"
    assert job.metadata["requested_run_mode"] == "mock_immediate"
    assert job.metadata["effective_run_mode"] == "mock_immediate"
    assert job.metadata["execution_mode"] == "pending_deterministic_mock"
    assert job.output_path is None
    assert job.result_payload is None


def test_create_generation_job_graph_job_degrades_metadata():
    job = create_generation_job(
        GenerationJobCreateRequest(
            user_input="Create an ad",
            run_mode="graph_job",
        )
    )

    assert job.status == "queued"
    assert job.metadata["requested_run_mode"] == "graph_job"
    assert job.metadata["effective_run_mode"] == "graph_job"
    assert job.metadata["execution_mode"] == "pending_graph_execution"
    assert job.output_path is None
    assert job.result_payload is None


def test_memory_mark_failed_snapshot_keeps_error_message_and_detail():
    job = create_generation_job(GenerationJobCreateRequest(user_input="Create an ad", run_mode="graph_job"))

    failed = mark_generation_job_failed(
        job.job_id,
        {
            "error_code": "generation_job_execution_failed",
            "message": "Generation job graph execution failed.",
            "detail": "No module named 'langgraph.checkpoint.postgres'",
        },
    )

    snapshot = get_chat_state_snapshot_by_key(
        snapshot_key=f"{job.job_id}:failed",
        public_thread_id=job.thread_id,
        workspace_id="mem_workspace",
        user_id=job.user_id,
    )

    assert failed is not None
    assert snapshot is not None
    assert snapshot.metadata["message"] == "Generation job graph execution failed."
    assert snapshot.metadata["detail"] == "No module named 'langgraph.checkpoint.postgres'"


def test_maybe_mark_stale_generation_job_failed_keeps_fresh_running_job():
    now = datetime(2026, 6, 8, 9, 0, tzinfo=timezone.utc)
    fresh_job = GenerationJobResponse(
        job_id="job_fresh",
        status="running",
        progress=GenerationProgress(progress_percent=50, current_stage="planning", stage_order=[]),
        created_at=(now - timedelta(minutes=1)).isoformat(),
        updated_at=(now - timedelta(minutes=1)).isoformat(),
        metadata={},
    )

    result = maybe_mark_stale_generation_job_failed(fresh_job, now=now, stale_after_seconds=900)

    assert result is fresh_job


def test_maybe_mark_stale_generation_job_failed_fails_old_running_job():
    now = datetime(2026, 6, 8, 9, 0, tzinfo=timezone.utc)
    job = create_generation_job(GenerationJobCreateRequest(user_input="햄버거 광고", run_mode="graph_job"))
    running = mark_generation_job_running(job.job_id, stage="planning")
    stale_running = running.model_copy(
        update={
            "updated_at": (now - timedelta(minutes=30)).isoformat(),
            "metadata": {**(running.metadata or {}), "execution_mode": "graph_execution"},
        }
    )

    result = maybe_mark_stale_generation_job_failed(stale_running, now=now, stale_after_seconds=900)

    assert result.status == "failed"
    assert result.progress.current_stage == "failed"
    assert result.error is not None
    assert result.error.error_code == "generation_job_stale_running"
    assert result.metadata["execution_mode"] == "stale_running_recovered"
    assert result.metadata["stale_running_stage"] == "planning"


def test_graph_job_snapshot_preserves_selected_engine():
    request = GenerationJobCreateRequest(
        user_input="카페 신메뉴 광고 만들어줘",
        run_mode="graph_job",
        metadata={
            "selected_engine": "flux2_klein_4b",
            "requested_engine": "flux2_klein_4b",
            "t2i_engine": "flux2_klein_4b",
        },
    )

    job = create_generation_job(request)
    snapshot = get_chat_state_snapshot_by_key(
        snapshot_key=f"{job.job_id}:input",
        public_thread_id=job.thread_id,
        workspace_id="mem_workspace",
        user_id=job.user_id,
    )

    assert snapshot is not None
    assert job.metadata["engine_preference"] == "flux2_klein_4b"
    assert job.metadata["t2i_engine"] == "flux2_klein_4b"
    assert snapshot.state_payload["engine"] == "flux2_klein_4b"
    assert snapshot.state_payload["current_brief"]["requested_engine"] == "flux2_klein_4b"


def test_get_missing_generation_job_returns_none_and_reset_clears_store():
    job = create_generation_job(GenerationJobCreateRequest(user_input="Create an ad"))
    assert get_generation_job("job_missing") is None

    reset_generation_job_store_for_tests()
    assert get_generation_job(job.job_id) is None


# ===== from test_generation_job_service_db_backend.py =====
from datetime import datetime, timezone
from contextlib import contextmanager

import pytest

from orchestrator.app.api.schemas.generation_jobs import GenerationJobCreateRequest
from orchestrator.app.chat_threads.errors import ChatThreadHasActiveJobError
from orchestrator.app.generation_jobs import service
from orchestrator.tests.factories.generation_jobs import (
    DEFAULT_WORKSPACE_ID,
    fake_db_transaction as shared_fake_db_transaction,
    make_generation_job_row,
)


@pytest.fixture(autouse=True)
def reset_store__test_generation_job_service_db_backend(monkeypatch):
    service.reset_generation_job_store_for_tests()
    monkeypatch.delenv("EASYADS_DB_BACKEND", raising=False)
    yield
    service.reset_generation_job_store_for_tests()


def _row__test_generation_job_service_db_backend(public_job_id="job_db", status="queued", metadata=None, result_payload=None, error=None):
    return make_generation_job_row(
        public_job_id=public_job_id,
        workspace_id=DEFAULT_WORKSPACE_ID,
        status=status,
        selected_reference_template_id="seed_1",
        output_path="data/outputs/job_db/final_0.png" if status == "done" else None,
        result_payload=result_payload,
        error=error,
        metadata=metadata
        or {
            "public_thread_id": "thread_db",
            "requested_run_mode": "queued_only",
            "effective_run_mode": "queued_only",
            "execution_mode": "queued_only",
        },
    )


from unittest.mock import MagicMock

@contextmanager
def fake_db_transaction__test_generation_job_service_db_backend():
    with shared_fake_db_transaction() as conn:
        yield conn


def _patch_noop_side_effects(monkeypatch):
    monkeypatch.setattr(service.chat_thread_repo, "set_chat_thread_active_job", lambda *args, **kwargs: {"id": "thread_uuid"})
    monkeypatch.setattr(service.chat_message_repo, "append_chat_message", lambda **kwargs: {"id": "msg_uuid"})
    monkeypatch.setattr(service.state_service, "get_latest_thread_state_snapshot", lambda **kwargs: None)
    monkeypatch.setattr(service.state_service, "save_thread_state_snapshot", lambda **kwargs: {"snapshot_id": "snap_uuid"})
    monkeypatch.setattr(service.chat_thread_repo, "complete_chat_thread_generation", lambda **kwargs: {"id": "thread_uuid", **kwargs})
    monkeypatch.setattr(service.chat_message_repo, "append_chat_message", lambda **kwargs: {"id": "msg_uuid"})
    monkeypatch.setattr(service.state_service, "get_latest_thread_state_snapshot", lambda **kwargs: None)
    monkeypatch.setattr(service.state_service, "save_thread_state_snapshot", lambda **kwargs: {"snapshot_id": "snap_uuid"})
    monkeypatch.setattr(service.chat_thread_repo, "fail_chat_thread_generation", lambda **kwargs: {"id": "thread_uuid", **kwargs})
    monkeypatch.setattr(service.chat_message_repo, "append_chat_message", lambda **kwargs: {"id": "msg_uuid"})
    monkeypatch.setattr(service.state_service, "get_latest_thread_state_snapshot", lambda **kwargs: None)
    monkeypatch.setattr(service.state_service, "save_thread_state_snapshot", lambda **kwargs: {"snapshot_id": "snap_uuid"})
    monkeypatch.setattr(service.generation_job_event_repo, "record_generation_job_event", lambda **kwargs: {"id": "event_uuid", **kwargs})
    monkeypatch.setattr(service.chat_thread_repo, "get_chat_thread_by_public_id", lambda thread_id, **kwargs: {"id": "thread_uuid", "active_job_id": "job_uuid"})
    monkeypatch.setattr(service.chat_message_repo, "append_generation_job_chat_event", lambda **kwargs: {"id": "msg_uuid"})


def test_memory_backend_uses_existing_store(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "memory")
    request = GenerationJobCreateRequest(user_input="Create an ad", run_mode="queued_only")

    job = service.create_generation_job(request)

    assert job.job_id.startswith("job_")
    assert service.get_generation_job(job.job_id) == job


def test_memory_backend_does_not_store_orphan_job_when_thread_claim_fails(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "memory")
    monkeypatch.setattr(
        service.chat_thread_service,
        "set_thread_active_job",
        lambda *args, **kwargs: (_ for _ in ()).throw(ChatThreadHasActiveJobError()),
    )

    with pytest.raises(ChatThreadHasActiveJobError):
        service.create_generation_job(GenerationJobCreateRequest(user_input="Create an ad", run_mode="queued_only"))

    assert service._GENERATION_JOBS == {}


def test_postgres_backend_create_uses_repository_path(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")
    monkeypatch.setattr(service, "db_transaction", fake_db_transaction__test_generation_job_service_db_backend)
    _patch_noop_side_effects(monkeypatch)
    monkeypatch.setattr(service.workspace_repo, "get_workspace_for_user", lambda *, workspace_id, user_id, connection=None: {"id": workspace_id, "owner_user_id": None})
    monkeypatch.setattr(
        service.chat_thread_repo,
        "create_chat_thread",
        lambda **kwargs: {"id": "thread_uuid", "public_thread_id": "thread_db"},
    )

    captured = {}

    def fake_create_generation_job_row(**kwargs):
        captured.update(kwargs)
        metadata = dict(kwargs["metadata"])
        metadata["public_thread_id"] = "thread_db"
        return _row__test_generation_job_service_db_backend(public_job_id=kwargs["public_job_id"], metadata=metadata)

    monkeypatch.setattr(service.generation_job_repo, "create_generation_job_row", fake_create_generation_job_row)

    captured_thread = {}
    monkeypatch.setattr(
        service.chat_thread_repo,
        "create_chat_thread",
        lambda **kwargs: captured_thread.update(kwargs) or {"id": "thread_uuid", "public_thread_id": "thread_db"},
    )

    request = GenerationJobCreateRequest(
        user_input="Create an ad",
        user_id="demo_user",
        workspace_id="11111111-1111-1111-1111-111111111111",
        run_mode="queued_only",
        selected_reference_template_id="seed_1",
        brand_kit_id="bk_public",
    )
    job = service.create_generation_job(request)

    assert job.job_id.startswith("job_")
    assert job.thread_id == "thread_db"
    assert job.status == "queued"
    assert job.selected_reference_template_id == "seed_1"
    assert captured["workspace_id"] == "11111111-1111-1111-1111-111111111111"
    assert captured["thread_id"] == "thread_uuid"
    assert captured_thread["brand_kit_id"] is None
    assert job.brand_kit_id == "bk_public"
    assert job.metadata["brand_kit_id"] == "bk_public"
    assert captured["run_mode"] == "queued_only"
    assert captured["request_payload"]["user_input_preview"] == "Create an ad"


def test_postgres_backend_create_uses_authenticated_user_workspace(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")
    monkeypatch.setenv("EASYADS_DEMO_WORKSPACE_ID", "workspace_demo")
    monkeypatch.setattr(service, "db_transaction", fake_db_transaction__test_generation_job_service_db_backend)
    _patch_noop_side_effects(monkeypatch)
    monkeypatch.setattr(
        service.workspace_repo,
        "ensure_user_workspace",
        lambda user_id, account_type="user", connection=None: {"id": f"workspace_{user_id}"},
    )
    monkeypatch.setattr(
        service.workspace_repo,
        "ensure_demo_workspace",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("authenticated users must not use demo workspace")),
    )
    monkeypatch.setattr(
        service.chat_thread_repo,
        "create_chat_thread",
        lambda **kwargs: {"id": "thread_uuid", "public_thread_id": "thread_db"},
    )

    captured = {}

    def fake_create_generation_job_row(**kwargs):
        captured.update(kwargs)
        metadata = dict(kwargs["metadata"])
        metadata["public_thread_id"] = "thread_db"
        return _row__test_generation_job_service_db_backend(public_job_id=kwargs["public_job_id"], metadata=metadata)

    monkeypatch.setattr(service.generation_job_repo, "create_generation_job_row", fake_create_generation_job_row)

    job = service.create_generation_job(
        GenerationJobCreateRequest(user_id="user_a", user_input="Create an ad", run_mode="queued_only")
    )

    assert job.user_id == "user_a"
    assert captured["workspace_id"] == "workspace_user_a"


def test_postgres_backend_create_marks_guest_workspace_and_job(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")
    monkeypatch.setattr(service, "db_transaction", fake_db_transaction__test_generation_job_service_db_backend)
    _patch_noop_side_effects(monkeypatch)
    captured_workspace = {}
    monkeypatch.setattr(
        service.workspace_repo,
        "ensure_user_workspace",
        lambda user_id, account_type="user", connection=None: captured_workspace.setdefault(
            "value",
            {"id": "workspace_guest", "user_id": user_id, "account_type": account_type},
        ),
    )
    monkeypatch.setattr(
        service.chat_thread_repo,
        "create_chat_thread",
        lambda **kwargs: {"id": "thread_uuid", "public_thread_id": "thread_guest"},
    )

    captured_job = {}

    def fake_create_generation_job_row(**kwargs):
        captured_job.update(kwargs)
        metadata = dict(kwargs["metadata"])
        metadata["public_thread_id"] = "thread_guest"
        return _row__test_generation_job_service_db_backend(public_job_id=kwargs["public_job_id"], metadata=metadata)

    monkeypatch.setattr(service.generation_job_repo, "create_generation_job_row", fake_create_generation_job_row)

    job = service.create_generation_job(
        GenerationJobCreateRequest(
            user_id="guest_uuid_1",
            accountType="guest",
            user_input="Create an ad",
            run_mode="queued_only",
        )
    )

    assert captured_workspace["value"]["user_id"] == "guest_uuid_1"
    assert captured_workspace["value"]["account_type"] == "guest"
    assert captured_job["requested_by"] == "guest_uuid_1"
    assert captured_job["metadata"]["account_type"] == "guest"
    assert job.thread_id == "thread_guest"


def test_postgres_backend_create_does_not_allow_metadata_account_type_override(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")
    monkeypatch.setattr(service, "db_transaction", fake_db_transaction__test_generation_job_service_db_backend)
    _patch_noop_side_effects(monkeypatch)
    monkeypatch.setattr(
        service.workspace_repo,
        "ensure_user_workspace",
        lambda user_id, account_type="user", connection=None: {"id": "workspace_guest"},
    )
    monkeypatch.setattr(
        service.chat_thread_repo,
        "create_chat_thread",
        lambda **kwargs: {"id": "thread_uuid", "public_thread_id": "thread_guest"},
    )

    captured_job = {}

    def fake_create_generation_job_row(**kwargs):
        captured_job.update(kwargs)
        metadata = dict(kwargs["metadata"])
        metadata["public_thread_id"] = "thread_guest"
        return _row__test_generation_job_service_db_backend(public_job_id=kwargs["public_job_id"], metadata=metadata)

    monkeypatch.setattr(service.generation_job_repo, "create_generation_job_row", fake_create_generation_job_row)

    service.create_generation_job(
        GenerationJobCreateRequest(
            user_id="guest_uuid_1",
            accountType="guest",
            user_input="Create an ad",
            run_mode="queued_only",
            metadata={"account_type": "user"},
        )
    )

    assert captured_job["metadata"]["account_type"] == "guest"


def test_postgres_backend_sanitizes_nested_metadata(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")
    monkeypatch.setattr(service, "db_transaction", fake_db_transaction__test_generation_job_service_db_backend)
    _patch_noop_side_effects(monkeypatch)
    monkeypatch.setattr(service.workspace_repo, "get_workspace_for_user", lambda *, workspace_id, user_id, connection=None: {"id": workspace_id, "owner_user_id": None})
    monkeypatch.setattr(service.chat_thread_repo, "create_chat_thread", lambda **kwargs: {"id": "thread_uuid", "public_thread_id": "thread_db"})
    monkeypatch.setattr(service.chat_message_repo, "append_chat_message", lambda **kwargs: {"id": "msg_uuid"})
    monkeypatch.setattr(service.state_service, "get_latest_thread_state_snapshot", lambda **kwargs: None)
    monkeypatch.setattr(service.state_service, "save_thread_state_snapshot", lambda **kwargs: {"snapshot_id": "snap_uuid"})

    captured = {}

    def fake_create_generation_job_row(**kwargs):
        captured.update(kwargs)
        metadata = dict(kwargs["metadata"])
        metadata["public_thread_id"] = "thread_db"
        return _row__test_generation_job_service_db_backend(public_job_id=kwargs["public_job_id"], metadata=metadata)

    monkeypatch.setattr(service.generation_job_repo, "create_generation_job_row", fake_create_generation_job_row)

    request = GenerationJobCreateRequest(
        user_input="Create an ad",
        user_id="demo_user",
        workspace_id="11111111-1111-1111-1111-111111111111",
        run_mode="queued_only",
        metadata={"debug": {"api_key": "sk-should-not-leak", "safe": "visible"}},
    )
    job = service.create_generation_job(request)

    assert "sk-should-not-leak" not in str(job.model_dump(mode="json"))
    assert captured["metadata"]["debug"]["safe"] == "visible"
    assert "api_key" not in captured["metadata"]["debug"]


def test_postgres_backend_mark_done_and_failed_preserve_shape(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")
    monkeypatch.setenv("EASYADS_ASSET_STORAGE_BACKEND", "local_dev")
    monkeypatch.setenv("EASYADS_ENABLE_R2_UPLOAD", "false")
    monkeypatch.setenv("EASYADS_R2_UPLOAD_REQUIRED", "false")
    monkeypatch.setattr(service, "db_transaction", fake_db_transaction__test_generation_job_service_db_backend)
    _patch_noop_side_effects(monkeypatch)
    state = {"row": _row__test_generation_job_service_db_backend(public_job_id="job_db")}
    monkeypatch.setattr(service.generation_job_repo, "get_generation_job_row", lambda job_id, connection=None: state["row"])

    def fake_mark_done(job_id, result_payload, output_path=None, metadata=None, connection=None):
        metadata = metadata or state["row"]["metadata"]
        state["row"] = {
            **state["row"],
            "status": "done",
            "current_stage": "completed",
            "progress_percent": 100,
            "output_path": output_path,
            "result_payload": result_payload,
            "error": {},
            "metadata": metadata,
        }
        return state["row"]

    def fake_mark_failed(job_id, error, metadata=None, connection=None):
        state["row"] = {
            **state["row"],
            "status": "failed",
            "current_stage": "failed",
            "error": error,
            "metadata": metadata or state["row"]["metadata"],
        }
        return state["row"]

    monkeypatch.setattr(service.generation_job_repo, "mark_generation_job_done_row", fake_mark_done)
    monkeypatch.setattr(service.generation_job_repo, "mark_generation_job_failed_row", fake_mark_failed)
    monkeypatch.setattr(
        service.generation_job_repo,
        "update_generation_job_row",
        lambda job_id, connection=None, **fields: state["row"].update(fields) or state["row"],
    )
    monkeypatch.setattr(service.asset_repo, "create_asset", lambda **kwargs: {"id": "asset_uuid", **kwargs})
    monkeypatch.setattr(service.generation_output_repo, "create_generation_output", lambda **kwargs: {"id": "output_uuid", "asset_id": kwargs["asset_id"], **kwargs})
    monkeypatch.setattr(service.generation_output_repo, "mark_output_final", lambda output_id, *args, **kwargs: {"id": output_id})
    monkeypatch.setattr("orchestrator.app.archive.service.sync_archive_for_output", MagicMock())

    done = service.mark_generation_job_done("job_db", result_payload={"schema_version": "result_artifact_v1"}, output_path="data/outputs/job_db/final_0.png")
    assert done.status == "done"
    assert done.result_payload["schema_version"] == "result_artifact_v1"
    assert done.output_path.endswith("final_0.png")

    failed = service.mark_generation_job_failed("job_db", {"error_code": "x", "message": "failed"})
    assert failed.status == "failed"
    assert failed.error.error_code == "x"
    assert failed.progress.current_stage == "failed"


# ===== from test_generation_job_tenant_isolation.py =====
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from orchestrator.app.api.schemas.generation_jobs import GenerationJobCreateRequest
from orchestrator.app.generation_jobs import service
from orchestrator.app.generation_jobs.errors import GenerationJobWorkspaceNotFound, GenerationJobWorkspaceRequired


WORKSPACE_A = DEFAULT_WORKSPACE_ID
WORKSPACE_B = "22222222-2222-2222-2222-222222222222"


@contextmanager
def fake_db_transaction__test_generation_job_tenant_isolation():
    with shared_fake_db_transaction() as conn:
        yield conn


def _row__test_generation_job_tenant_isolation(*, public_job_id="job_db", workspace_id=WORKSPACE_A, metadata=None):
    return make_generation_job_row(
        public_job_id=public_job_id,
        workspace_id=workspace_id,
        requested_by="user_a",
        metadata=metadata
        or {
            "public_thread_id": "thread_a",
            "requested_run_mode": "queued_only",
            "effective_run_mode": "queued_only",
            "execution_mode": "queued_only",
            "user_id": "user_a",
        },
    )


@pytest.fixture(autouse=True)
def reset(monkeypatch):
    service.reset_generation_job_store_for_tests()
    monkeypatch.delenv("EASYADS_DB_BACKEND", raising=False)
    monkeypatch.delenv("EASYADS_ALLOW_DEMO_WORKSPACE_FALLBACK", raising=False)
    yield
    service.reset_generation_job_store_for_tests()


def test_generation_job_create_request_accepts_workspace_id_alias():
    request = GenerationJobCreateRequest(userInput="Create an ad", workspaceId=WORKSPACE_A)

    assert request.workspace_id == WORKSPACE_A


def test_memory_generation_job_get_is_workspace_scoped(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "memory")
    job = service.create_generation_job(
        GenerationJobCreateRequest(userInput="Create an ad", workspaceId=WORKSPACE_A, userId="user_a")
    )

    assert service.get_generation_job(job.job_id, workspace_id=WORKSPACE_A, user_id="user_a") is not None
    assert service.get_generation_job(job.job_id, workspace_id=WORKSPACE_B, user_id="user_a") is None
    assert "workspace_id" not in job.metadata


def test_postgres_create_requires_workspace_without_demo_fallback(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")
    monkeypatch.setenv("EASYADS_ALLOW_DEMO_WORKSPACE_FALLBACK", "false")
    monkeypatch.setattr(service, "db_transaction", fake_db_transaction__test_generation_job_tenant_isolation)

    with pytest.raises(GenerationJobWorkspaceRequired):
        service.create_generation_job(GenerationJobCreateRequest(userInput="Create an ad"))


def test_postgres_public_access_resolves_workspace_from_user_id(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")
    monkeypatch.setenv("EASYADS_ALLOW_DEMO_WORKSPACE_FALLBACK", "false")
    monkeypatch.setattr(service, "db_transaction", fake_db_transaction__test_generation_job_tenant_isolation)

    calls = []
    running_kwargs = {}

    def ensure_user_workspace(*, user_id, connection=None):
        calls.append((user_id, connection is not None))
        return {"id": WORKSPACE_A, "owner_user_id": user_id}

    def mark_running(public_job_id, current_stage=None, connection=None, **kwargs):
        assert public_job_id == "job_db"
        running_kwargs.update(kwargs)
        row = _row__test_generation_job_tenant_isolation(public_job_id=public_job_id, workspace_id=kwargs["workspace_id"])
        row["status"] = "running"
        row["current_stage"] = current_stage
        row["progress_percent"] = 50
        return row

    monkeypatch.setattr(service.workspace_repo, "ensure_user_workspace", ensure_user_workspace)
    monkeypatch.setattr(service.generation_job_repo, "mark_generation_job_running_row", mark_running)
    monkeypatch.setattr(service.generation_job_repo, "update_generation_job_row", lambda *args, **kwargs: None)
    monkeypatch.setattr(service.generation_job_event_repo, "record_generation_job_event", lambda **kwargs: {"id": "event_uuid"})
    monkeypatch.setattr(service.chat_thread_repo, "update_chat_thread_status", lambda *args, **kwargs: {"id": "thread_uuid"})
    monkeypatch.setattr(service.chat_message_repo, "append_chat_message", lambda **kwargs: {"id": "msg_uuid"})
    monkeypatch.setattr(service.state_service, "get_latest_thread_state_snapshot", lambda **kwargs: None)
    monkeypatch.setattr(service.state_service, "save_thread_state_snapshot", lambda **kwargs: {"snapshot_id": "snap_uuid"})

    found = service.mark_generation_job_running("job_db", "planning", user_id="user_a")

    assert found is not None
    assert found.job_id == "job_db"
    assert found.progress.current_stage == "planning"
    assert calls == [("user_a", True)]
    assert running_kwargs == {"workspace_id": WORKSPACE_A}


def test_postgres_scoped_get_hides_cross_workspace_job(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")
    monkeypatch.setattr(service, "db_transaction", fake_db_transaction__test_generation_job_tenant_isolation)
    monkeypatch.setattr(service.workspace_repo, "get_workspace_for_user", lambda *, workspace_id, user_id, connection=None: {"id": workspace_id, "owner_user_id": "user_a"} if user_id == "user_a" and workspace_id == WORKSPACE_A else None)

    calls = []

    def fake_get_by_public_id(public_job_id, *, workspace_id, connection=None, for_update=False):
        calls.append((public_job_id, workspace_id))
        if workspace_id == WORKSPACE_A:
            return _row__test_generation_job_tenant_isolation(public_job_id=public_job_id, workspace_id=workspace_id)
        return None

    monkeypatch.setattr(service.generation_job_repo, "get_generation_job_scoped_by_public_id", fake_get_by_public_id)

    found = service.get_generation_job("job_db", workspace_id=WORKSPACE_A, user_id="user_a")
    with pytest.raises(GenerationJobWorkspaceNotFound):
        service.get_generation_job("job_db", workspace_id=WORKSPACE_B, user_id="user_a")

    assert found is not None
    assert calls == [("job_db", WORKSPACE_A)]
