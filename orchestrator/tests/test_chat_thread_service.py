from __future__ import annotations

import ast
from pathlib import Path

import pytest

from orchestrator.app.api.schemas.chat_threads import ChatMessageCreateRequest, ChatThreadCreateRequest, ChatThreadUpdateRequest
from orchestrator.app.chat_threads.errors import ChatThreadHasActiveJobError
from orchestrator.app.chat_threads.service import (
    append_chat_message,
    archive_chat_thread,
    create_chat_thread,
    get_chat_thread,
    list_chat_messages,
    list_chat_threads,
    clear_thread_active_job,
    reset_chat_thread_store_for_tests,
    set_thread_active_job,
    set_thread_final_output,
    update_chat_thread,
)


@pytest.fixture(autouse=True)
def memory_backend(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "memory")
    reset_chat_thread_store_for_tests()
    yield
    reset_chat_thread_store_for_tests()


def test_memory_thread_owner_scope_and_pagination_total():
    for index in range(5):
        create_chat_thread(ChatThreadCreateRequest(user_id="user_a", title=f"A {index}"))
    create_chat_thread(ChatThreadCreateRequest(user_id="user_b", title="B"))

    threads, total = list_chat_threads(user_id="user_a", limit=2, offset=0)

    assert total == 5
    assert len(threads) == 2
    assert all(get_chat_thread(thread.thread_id, user_id="user_b") is None for thread in threads)


def test_final_brief_and_message_payload_are_sanitized():
    thread = create_chat_thread(
        ChatThreadCreateRequest(
            user_id="user_a",
            final_brief={"safe": "visible", "apiKey": "sk-secret", "nested": {"rawLlmResponse": "blocked"}},
        )
    )
    assert thread.final_brief == {"safe": "visible", "nested": {}}

    msg = append_chat_message(
        thread.thread_id,
        ChatMessageCreateRequest(role="user", content="hello", payload={"safe": "visible", "hfToken": "hf-secret"}),
        user_id="user_a",
    )

    assert msg.payload == {"safe": "visible"}
    assert msg.created_by == "user_a"


def test_active_thread_cannot_be_archived():
    thread = create_chat_thread(ChatThreadCreateRequest(user_id="user_a", title="Active"))
    set_thread_active_job(thread.thread_id, "job_uuid", "job_public")

    with pytest.raises(ChatThreadHasActiveJobError):
        archive_chat_thread(thread.thread_id, user_id="user_a")


def test_user_message_reopens_completed_thread_but_keeps_final_output():
    thread = create_chat_thread(ChatThreadCreateRequest(user_id="user_a", title="Done"))
    set_thread_active_job(thread.thread_id, "job_uuid", "job_public")
    set_thread_final_output(thread.thread_id, "output_uuid", final_brief={"safe": "brief"})
    clear_thread_active_job(thread.thread_id, status="completed")

    append_chat_message(thread.thread_id, ChatMessageCreateRequest(role="user", content="again"), user_id="user_a")
    updated = get_chat_thread(thread.thread_id, user_id="user_a")

    assert updated.status == "draft"
    assert updated.has_final_output is True
    assert updated.final_brief == {"safe": "brief"}


def test_stale_memory_job_cannot_clear_newer_active_job():
    thread = create_chat_thread(ChatThreadCreateRequest(user_id="user_a", title="Stale"))
    set_thread_active_job(thread.thread_id, "job_uuid_b", "job_b")

    set_thread_final_output(
        thread.thread_id,
        "output_uuid_a",
        final_brief={"stale": True},
        expected_public_job_id="job_a",
    )
    clear_thread_active_job(thread.thread_id, status="completed", expected_public_job_id="job_a")

    current = get_chat_thread(thread.thread_id, user_id="user_a")
    assert current.active_job_id == "job_b"
    assert current.status == "generating"
    assert current.has_final_output is False


def test_message_pagination_total():
    thread = create_chat_thread(ChatThreadCreateRequest(user_id="user_a", title="Messages"))
    for index in range(5):
        append_chat_message(thread.thread_id, ChatMessageCreateRequest(role="user", content=f"m {index}"), user_id="user_a")

    messages, total = list_chat_messages(thread.thread_id, user_id="user_a", limit=2, offset=2)

    assert total == 5
    assert [message.sequence_no for message in messages] == [3, 4]


def test_chat_thread_backend_files_do_not_have_duplicate_function_definitions():
    paths = [
        Path("orchestrator/app/db/repositories/chat_messages.py"),
        Path("orchestrator/app/db/repositories/chat_threads.py"),
        Path("orchestrator/app/chat_threads/service.py"),
    ]
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        seen: dict[str, int] = {}
        duplicates: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if node.name in seen:
                    duplicates.add(node.name)
                seen[node.name] = node.lineno
        assert duplicates == set(), f"{path} has duplicate defs: {sorted(duplicates)}"


def test_get_chat_thread_with_workspace_falls_back_to_owning_workspace(monkeypatch):
    from orchestrator.app.chat_threads import service as chat_service

    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")
    monkeypatch.setattr(chat_service, "_get_demo_workspace_id", lambda user_id=None: "workspace_demo")

    calls = []

    def fake_get_chat_thread_by_public_id(public_thread_id, workspace_id=None, connection=None, for_update=False):
        calls.append(workspace_id)
        if workspace_id == "workspace_demo":
            return None
        return {
            "id": "internal_thread_uuid",
            "public_thread_id": public_thread_id,
            "workspace_id": "workspace_actual",
            "title": "카페 신메뉴 광고",
            "status": "generating",
            "brand_kit_id": None,
            "project_id": None,
            "final_brief": {},
            "active_job_id": None,
            "active_public_job_id": None,
            "final_output_id": None,
            "last_message_at": "2026-06-06T00:00:00+00:00",
            "archived_at": None,
            "created_at": "2026-06-06T00:00:00+00:00",
            "updated_at": "2026-06-06T00:00:00+00:00",
        }

    monkeypatch.setattr(chat_service.chat_thread_repo, "get_chat_thread_by_public_id", fake_get_chat_thread_by_public_id)

    result = chat_service.get_chat_thread_with_workspace("thread_generated")

    assert result is not None
    thread, workspace_id = result
    assert thread.thread_id == "thread_generated"
    assert workspace_id == "workspace_actual"
    assert calls == ["workspace_demo", None]
