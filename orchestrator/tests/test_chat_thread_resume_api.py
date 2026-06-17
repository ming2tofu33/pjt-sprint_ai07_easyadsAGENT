from types import SimpleNamespace

from fastapi.testclient import TestClient

from orchestrator.app.api.app import create_app
from orchestrator.app.api.schemas.chat_threads import ChatThreadCreateRequest
from orchestrator.app.chat_threads import service as chat_service
from orchestrator.app.chat_threads import state_service


def _thread_row(**overrides):
    row = {
        "public_thread_id": "thread_1",
        "workspace_id": "workspace_1",
        "title": "프리미엄 뷰티살롱",
        "status": "draft",
        "brand_kit_id": None,
        "project_id": None,
        "final_brief": {},
        "active_job_id": None,
        "active_public_job_id": None,
        "final_output_id": None,
        "final_public_output_id": None,
        "final_public_job_id": None,
        "last_message_at": "2026-06-17T03:37:45+00:00",
        "archived_at": None,
        "created_at": "2026-06-17T03:30:00+00:00",
        "updated_at": "2026-06-17T03:37:45+00:00",
    }
    row.update(overrides)
    return row


def test_thread_response_contains_resume_state_for_final_output(monkeypatch):
    monkeypatch.setattr(chat_service.db_settings, "get_db_backend", lambda: "postgres")
    monkeypatch.setattr(
        chat_service,
        "_ensure_workspace_for_user",
        lambda user_id, connection=None, account_type=None: {"id": "workspace_1"},
    )
    monkeypatch.setattr(
        chat_service.chat_thread_repo,
        "get_chat_thread_by_public_id",
        lambda *args, **kwargs: {
            "public_thread_id": "thread_done",
            "title": "프리미엄 뷰티살롱",
            "status": "draft",
            "brand_kit_id": None,
            "project_id": None,
            "final_brief": {},
            "active_public_job_id": None,
            "final_public_job_id": "job_done",
            "final_public_output_id": "output_done",
            "final_output_id": "internal-output-uuid",
            "last_message_at": "2026-06-17T03:37:45+00:00",
            "archived_at": None,
            "created_at": "2026-06-17T03:30:00+00:00",
            "updated_at": "2026-06-17T03:37:45+00:00",
        },
    )
    monkeypatch.setattr(
        state_service,
        "get_latest_thread_state_snapshot",
        lambda *args, **kwargs: SimpleNamespace(
            snapshot_id="snapshot_waiting",
            snapshot_kind="waiting_user_input",
            state_payload={},
        ),
    )
    monkeypatch.setattr(
        chat_service.generation_job_repo,
        "get_latest_waiting_generation_job_for_thread",
        lambda *args, **kwargs: {
            "public_job_id": "job_waiting",
            "metadata": {"assistant_message": "어떤 업종의 광고인가요?"},
        },
    )

    thread = chat_service.get_chat_thread("thread_done", user_id="user_1")

    assert thread is not None
    assert thread.final_output_id == "output_done"
    assert thread.resume_state is not None
    assert thread.resume_state.action == "view_result"
    assert thread.resume_state.resume_job_id == "job_done"
    assert thread.resume_state.final_output_id == "output_done"


def test_resume_state_route_returns_pending_job(monkeypatch):
    app = create_app()
    client = TestClient(app)

    monkeypatch.setattr(
        chat_service,
        "get_chat_thread_resume_state",
        lambda thread_id, user_id=None, account_type=None: SimpleNamespace(
            action="answer_pending_job",
            thread_id=thread_id,
            resume_job_id="job_waiting",
            final_output_id=None,
            latest_snapshot_id="snapshot_waiting",
            snapshot_kind="waiting_user_input",
            reason="thread_has_waiting_job",
            current_question={"field": "business_type"},
        ),
    )

    response = client.get("/api/v1/chat-threads/thread_pending/resume-state")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["resume_state"]["action"] == "answer_pending_job"
    assert payload["resume_state"]["resume_job_id"] == "job_waiting"
    assert payload["resume_state"]["current_question"] == {"field": "business_type"}


def test_memory_resume_state_route_returns_continue_draft(monkeypatch):
    monkeypatch.setattr(chat_service.db_settings, "get_db_backend", lambda: "memory")
    chat_service.reset_chat_thread_store_for_tests()
    app = create_app()
    client = TestClient(app)

    thread = chat_service.create_chat_thread(
        ChatThreadCreateRequest(user_id="user_memory", title="Memory draft")
    )

    response = client.get(f"/api/v1/chat-threads/{thread.thread_id}/resume-state?userId=user_memory")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["resume_state"]["action"] == "continue_draft"
    assert payload["resume_state"]["thread_id"] == thread.thread_id


def test_list_chat_threads_db_does_not_fetch_resume_inputs_per_row(monkeypatch):
    monkeypatch.setattr(chat_service.db_settings, "get_db_backend", lambda: "postgres")
    monkeypatch.setattr(chat_service, "_get_workspace_id_for_user", lambda *args, **kwargs: "workspace_1")
    monkeypatch.setattr(
        chat_service.chat_thread_repo,
        "list_chat_threads",
        lambda **kwargs: [
            _thread_row(
                public_thread_id="thread_done",
                final_public_job_id="job_done",
                final_public_output_id="output_done",
            )
        ],
    )
    monkeypatch.setattr(chat_service.chat_thread_repo, "count_chat_threads", lambda **kwargs: 1)
    monkeypatch.setattr(
        chat_service,
        "_thread_resume_inputs",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("list should not fetch resume inputs")),
    )

    threads, total = chat_service.list_chat_threads(user_id="user_1")

    assert total == 1
    assert len(threads) == 1
    assert threads[0].final_output_id == "output_done"
    assert threads[0].resume_state is not None
    assert threads[0].resume_state.action == "view_result"


def test_archive_chat_thread_refetches_joined_final_output(monkeypatch):
    monkeypatch.setattr(chat_service.db_settings, "get_db_backend", lambda: "postgres")
    monkeypatch.setattr(chat_service, "_get_workspace_id_for_user", lambda *args, **kwargs: "workspace_1")
    get_calls = []

    def fake_get_chat_thread_by_public_id(public_thread_id, workspace_id=None, connection=None, for_update=False):
        get_calls.append(public_thread_id)
        if len(get_calls) == 1:
            return _thread_row(public_thread_id=public_thread_id)
        return _thread_row(
            public_thread_id=public_thread_id,
            status="archived",
            archived_at="2026-06-17T03:40:00+00:00",
            final_public_job_id="job_done",
            final_public_output_id="output_done",
        )

    monkeypatch.setattr(chat_service.chat_thread_repo, "get_chat_thread_by_public_id", fake_get_chat_thread_by_public_id)
    monkeypatch.setattr(
        chat_service.chat_thread_repo,
        "archive_chat_thread",
        lambda *args, **kwargs: _thread_row(
            public_thread_id="thread_done",
            status="archived",
            archived_at="2026-06-17T03:40:00+00:00",
        ),
    )

    thread = chat_service.archive_chat_thread("thread_done", user_id="user_1")

    assert len(get_calls) == 2
    assert thread is not None
    assert thread.final_output_id == "output_done"
    assert thread.resume_state is not None
    assert thread.resume_state.action == "view_result"


def test_restore_chat_thread_refetches_joined_final_output(monkeypatch):
    monkeypatch.setattr(chat_service.db_settings, "get_db_backend", lambda: "postgres")
    monkeypatch.setattr(chat_service, "_get_workspace_id_for_user", lambda *args, **kwargs: "workspace_1")
    monkeypatch.setattr(chat_service.db_settings, "get_max_threads_per_workspace", lambda: 3)
    monkeypatch.setattr(chat_service.chat_thread_repo, "count_chat_threads", lambda **kwargs: 0)
    get_calls = []

    def fake_get_chat_thread_by_public_id(public_thread_id, workspace_id=None, connection=None, for_update=False):
        get_calls.append(public_thread_id)
        if len(get_calls) == 1:
            return _thread_row(
                public_thread_id=public_thread_id,
                status="archived",
                archived_at="2026-06-17T03:40:00+00:00",
            )
        return _thread_row(
            public_thread_id=public_thread_id,
            status="draft",
            archived_at=None,
            final_public_job_id="job_done",
            final_public_output_id="output_done",
        )

    monkeypatch.setattr(chat_service.chat_thread_repo, "get_chat_thread_by_public_id", fake_get_chat_thread_by_public_id)
    monkeypatch.setattr(
        chat_service.chat_thread_repo,
        "restore_chat_thread",
        lambda *args, **kwargs: _thread_row(public_thread_id="thread_done", status="draft", archived_at=None),
    )

    thread = chat_service.restore_chat_thread("thread_done", user_id="user_1")

    assert len(get_calls) == 2
    assert thread is not None
    assert thread.final_output_id == "output_done"
    assert thread.resume_state is not None
    assert thread.resume_state.action == "view_result"
