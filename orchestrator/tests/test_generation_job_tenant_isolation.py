from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from orchestrator.app.api.schemas.generation_jobs import GenerationJobCreateRequest
from orchestrator.app.generation_jobs import service
from orchestrator.app.generation_jobs.errors import GenerationJobWorkspaceRequired


@contextmanager
def fake_db_transaction():
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    yield conn


def _row(*, public_job_id="job_db", workspace_id="workspace_a", metadata=None):
    now = datetime.now(timezone.utc)
    return {
        "id": "job_uuid",
        "public_job_id": public_job_id,
        "workspace_id": workspace_id,
        "thread_id": "thread_uuid",
        "requested_by": "user_a",
        "status": "queued",
        "current_stage": "queued",
        "progress_percent": 0,
        "selected_reference_template_id": None,
        "output_path": None,
        "result_payload": None,
        "error": {},
        "created_at": now,
        "updated_at": now,
        "metadata": metadata or {
            "public_thread_id": "thread_a",
            "requested_run_mode": "queued_only",
            "effective_run_mode": "queued_only",
            "execution_mode": "queued_only",
            "user_id": "user_a",
        },
    }


@pytest.fixture(autouse=True)
def reset(monkeypatch):
    service.reset_generation_job_store_for_tests()
    monkeypatch.delenv("EASYADS_DB_BACKEND", raising=False)
    monkeypatch.delenv("EASYADS_ALLOW_DEMO_WORKSPACE_FALLBACK", raising=False)
    yield
    service.reset_generation_job_store_for_tests()


def test_generation_job_create_request_accepts_workspace_id_alias():
    request = GenerationJobCreateRequest(userInput="Create an ad", workspaceId="workspace_a")

    assert request.workspace_id == "workspace_a"


def test_memory_generation_job_get_is_workspace_scoped(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "memory")
    job = service.create_generation_job(
        GenerationJobCreateRequest(userInput="Create an ad", workspaceId="workspace_a", userId="user_a")
    )

    assert service.get_generation_job(job.job_id, workspace_id="workspace_a", user_id="user_a") is not None
    assert service.get_generation_job(job.job_id, workspace_id="workspace_b", user_id="user_a") is None
    assert "workspace_id" not in job.metadata


def test_postgres_create_requires_workspace_without_demo_fallback(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")
    monkeypatch.setenv("EASYADS_ALLOW_DEMO_WORKSPACE_FALLBACK", "false")
    monkeypatch.setattr(service, "db_transaction", fake_db_transaction)

    with pytest.raises(GenerationJobWorkspaceRequired):
        service.create_generation_job(GenerationJobCreateRequest(userInput="Create an ad"))


def test_postgres_scoped_get_hides_cross_workspace_job(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")
    monkeypatch.setattr(service, "db_transaction", fake_db_transaction)
    monkeypatch.setattr(service.workspace_repo, "get_workspace", lambda workspace_id, connection=None: {"id": workspace_id, "owner_user_id": "user_a"})

    calls = []

    def fake_get_by_public_id(public_job_id, *, workspace_id, connection=None, for_update=False):
        calls.append((public_job_id, workspace_id))
        if workspace_id == "workspace_a":
            return _row(public_job_id=public_job_id, workspace_id=workspace_id)
        return None

    monkeypatch.setattr(service.generation_job_repo, "get_generation_job_by_public_id", fake_get_by_public_id)

    found = service.get_generation_job("job_db", workspace_id="workspace_a", user_id="user_a")
    hidden = service.get_generation_job("job_db", workspace_id="workspace_b", user_id="user_a")

    assert found is not None
    assert hidden is None
    assert calls == [("job_db", "workspace_a"), ("job_db", "workspace_b")]
