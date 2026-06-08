"""Final selection transaction 테스트.

검증 범위:
- mark_output_final SQL 실행 순서 (output → thread lock → is_final 변경 → thread.final_output_id)
- workspace 격리 (다른 workspace output → None)
- Archive sync 실패 시 예외 전파 (transaction rollback 보장)
- mark → archive 순서 보장
"""

import pytest
from contextlib import contextmanager
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# mark_output_final: SQL 실행 순서 검증
# ---------------------------------------------------------------------------

def test_mark_output_final_sql_order(monkeypatch):
    """mark_output_final이 올바른 순서로 SQL을 실행하는지 검증."""
    from orchestrator.app.db.repositories import generation_outputs as repo

    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    cur.fetchone.side_effect = [
        {"thread_id": "thread_uuid_1"},
        {"id": "thread_uuid_1"},
        {"id": "output_uuid_1", "public_output_id": "out_pub_1"},
    ]

    @contextmanager
    def fake_tx(connection=None):
        yield connection

    monkeypatch.setattr(repo, "db_transaction", fake_tx)

    repo.mark_output_final("output_uuid_1", workspace_id="ws1", connection=conn)

    sql_calls = [call_args[0][0].strip() for call_args in cur.execute.call_args_list]

    # 1번째: output 조회 (thread_id 획득)
    assert "select thread_id from generation_outputs" in sql_calls[0].lower()
    # 2번째: thread FOR UPDATE
    assert "for update" in sql_calls[1].lower()
    # 3번째: 기존 final 해제
    assert "is_final = false" in sql_calls[2].lower()
    # 4번째: 새 final 설정
    assert "is_final = true" in sql_calls[3].lower()
    # 5번째: thread.final_output_id 갱신
    assert "final_output_id" in sql_calls[4].lower()


def test_mark_output_final_returns_none_when_output_not_found(monkeypatch):
    """다른 workspace의 output이면 None 반환 (workspace 격리)."""
    from orchestrator.app.db.repositories import generation_outputs as repo

    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    cur.fetchone.return_value = None

    @contextmanager
    def fake_tx(connection=None):
        yield connection

    monkeypatch.setattr(repo, "db_transaction", fake_tx)

    result = repo.mark_output_final("other_ws_output", workspace_id="ws1", connection=conn)
    assert result is None


def test_mark_output_final_returns_none_when_thread_not_found(monkeypatch):
    """thread row가 없으면 None 반환."""
    from orchestrator.app.db.repositories import generation_outputs as repo

    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    cur.fetchone.side_effect = [
        {"thread_id": "thread_uuid_1"},
        None,
    ]

    @contextmanager
    def fake_tx(connection=None):
        yield connection

    monkeypatch.setattr(repo, "db_transaction", fake_tx)

    result = repo.mark_output_final("output_uuid_1", workspace_id="ws1", connection=conn)
    assert result is None


# ---------------------------------------------------------------------------
# select_final_generation_output: transaction 실패 시 rollback
# ---------------------------------------------------------------------------

def test_select_final_propagates_archive_failure_and_does_not_commit(monkeypatch):
    """Archive sync 실패 시 예외가 전파되고 transaction이 commit되지 않음."""
    from orchestrator.app.generation_outputs.service import select_final_generation_output

    state = {"committed": False, "rolled_back": False}

    @contextmanager
    def fake_tx(*args, **kwargs):
        conn = MagicMock()
        try:
            yield conn
        except Exception:
            state["rolled_back"] = True
            raise
        else:
            state["committed"] = True

    monkeypatch.setattr("orchestrator.app.generation_outputs.service.db_transaction", fake_tx)

    mock_row = {"id": "uuid1", "public_output_id": "out1"}
    repo_mock = MagicMock()
    repo_mock.get_generation_output_by_public_id.return_value = mock_row
    repo_mock.mark_output_final.return_value = mock_row
    monkeypatch.setattr("orchestrator.app.generation_outputs.service.output_repo", repo_mock)

    def fail_sync(*args, **kwargs):
        raise RuntimeError("Archive sync failed")

    monkeypatch.setattr(
        "orchestrator.app.generation_outputs.service.sync_archive_for_output", fail_sync
    )

    with pytest.raises(RuntimeError, match="Archive sync failed"):
        select_final_generation_output("out1", workspace_id="ws1")

    assert state["rolled_back"] is True
    assert state["committed"] is False


def test_select_final_propagates_output_not_found(monkeypatch):
    """output이 없을 때 GenerationOutputNotFound 발생."""
    from orchestrator.app.generation_outputs.service import (
        select_final_generation_output,
        GenerationOutputNotFound,
    )

    repo_mock = MagicMock()
    repo_mock.get_generation_output_by_public_id.return_value = None
    monkeypatch.setattr("orchestrator.app.generation_outputs.service.output_repo", repo_mock)

    @contextmanager
    def fake_tx(*args, **kwargs):
        yield MagicMock()

    monkeypatch.setattr("orchestrator.app.generation_outputs.service.db_transaction", fake_tx)

    with pytest.raises(GenerationOutputNotFound):
        select_final_generation_output("nonexistent", workspace_id="ws1")


def test_select_final_calls_mark_then_archive(monkeypatch):
    """mark_output_final → sync_archive_for_output 순서 검증."""
    from orchestrator.app.generation_outputs.service import select_final_generation_output

    call_order = []

    mock_row = {"id": "uuid1", "public_output_id": "out1"}
    repo_mock = MagicMock()
    repo_mock.get_generation_output_by_public_id.return_value = mock_row
    repo_mock.mark_output_final.side_effect = lambda *a, **kw: (call_order.append("mark"), mock_row)[1]
    monkeypatch.setattr("orchestrator.app.generation_outputs.service.output_repo", repo_mock)

    def fake_sync(*args, **kwargs):
        call_order.append("archive_sync")

    monkeypatch.setattr(
        "orchestrator.app.generation_outputs.service.sync_archive_for_output", fake_sync
    )

    @contextmanager
    def fake_tx(*args, **kwargs):
        yield MagicMock()

    monkeypatch.setattr("orchestrator.app.generation_outputs.service.db_transaction", fake_tx)

    select_final_generation_output("out1", workspace_id="ws1")

    assert call_order == ["mark", "archive_sync"], f"예상 순서 위반: {call_order}"


# ---------------------------------------------------------------------------
# workspace isolation: 다른 workspace output 접근 거부
# ---------------------------------------------------------------------------

def test_get_generation_output_workspace_isolation(monkeypatch):
    """다른 workspace의 public_output_id 조회 시 NotFound."""
    from orchestrator.app.generation_outputs.service import (
        get_generation_output,
        GenerationOutputNotFound,
    )

    repo_mock = MagicMock()
    repo_mock.get_generation_output_by_public_id.return_value = None
    monkeypatch.setattr("orchestrator.app.generation_outputs.service.output_repo", repo_mock)

    with pytest.raises(GenerationOutputNotFound):
        get_generation_output("out_other_ws", workspace_id="ws1")

    repo_mock.get_generation_output_by_public_id.assert_called_once_with(
        public_output_id="out_other_ws", workspace_id="ws1"
    )
