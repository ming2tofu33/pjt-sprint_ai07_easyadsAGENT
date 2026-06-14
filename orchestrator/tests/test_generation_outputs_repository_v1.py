from unittest.mock import MagicMock

from orchestrator.app.db.repositories.generation_outputs import (
    count_generation_outputs,
    create_generation_output,
    get_generation_output_by_public_id,
    list_generation_outputs,
    mark_output_final,
)


def _mock_connection():
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    return mock_conn, mock_cur


def test_generation_output_create_returns_public_id_and_insert_params():
    mock_conn, mock_cur = _mock_connection()
    mock_cur.fetchone.return_value = {"id": "uuid1", "public_output_id": "out_public_1"}

    out = create_generation_output(
        workspace_id="ws1",
        thread_id="t1",
        job_id="j1",
        asset_id="a1",
        variant_index=0,
        is_final=False,
        public_output_id="out_public_1",
        connection=mock_conn,
    )

    assert out["public_output_id"] == "out_public_1"
    sql, params = mock_cur.execute.call_args[0]
    assert "insert into generation_outputs" in sql.lower()
    assert params[0:5] == ("ws1", "t1", "j1", "a1", None)
    assert params[5] == 0
    assert params[8] is False
    assert params[10] == "out_public_1"


def test_generation_output_get_scopes_by_workspace_and_public_id():
    mock_conn, mock_cur = _mock_connection()
    mock_cur.fetchone.return_value = {"id": "uuid1", "public_output_id": "out_public_1"}

    row = get_generation_output_by_public_id(
        public_output_id="out_public_1",
        workspace_id="ws1",
        connection=mock_conn,
    )

    assert row["public_output_id"] == "out_public_1"
    sql, params = mock_cur.execute.call_args[0]
    normalized = " ".join(sql.lower().split())
    assert "where o.public_output_id = %s and o.workspace_id = %s" in normalized
    assert params == ("out_public_1", "ws1")


def test_generation_output_list_applies_job_workspace_and_final_filters():
    mock_conn, mock_cur = _mock_connection()
    mock_cur.fetchall.return_value = [{"id": "uuid1", "public_job_id": "j_pub", "is_final": True}]

    rows = list_generation_outputs(
        workspace_id="ws1",
        public_job_id="j_pub",
        is_final=True,
        connection=mock_conn,
    )

    assert [row["id"] for row in rows] == ["uuid1"]
    sql, params = mock_cur.execute.call_args[0]
    normalized = " ".join(sql.lower().split())
    assert "o.workspace_id = %s" in normalized
    assert "j.public_job_id = %s" in normalized
    assert "o.is_final = %s" in normalized
    assert "order by o.created_at desc" in normalized
    assert params == ("ws1", "j_pub", True, 50, 0)


def test_generation_output_count_applies_job_and_workspace_filters():
    mock_conn, mock_cur = _mock_connection()
    mock_cur.fetchone.return_value = {"total": 1}

    total = count_generation_outputs(
        workspace_id="ws1",
        public_job_id="j_pub",
        connection=mock_conn,
    )

    assert total == 1
    sql, params = mock_cur.execute.call_args[0]
    normalized = " ".join(sql.lower().split())
    assert "select count(*) as total" in normalized
    assert "o.workspace_id = %s" in normalized
    assert "j.public_job_id = %s" in normalized
    assert params == ("ws1", "j_pub")


def test_generation_output_mark_final_transaction_updates_thread_scope_and_final_row():
    mock_conn, mock_cur = _mock_connection()
    mock_cur.fetchone.side_effect = [{"thread_id": "thread1"}, {"id": "thread1"}, {"id": "uuid1"}]

    result = mark_output_final(output_id="uuid1", workspace_id="ws1", connection=mock_conn)

    assert result["id"] == "uuid1"
    calls = mock_cur.execute.call_args_list
    select_sql, select_params = calls[0][0]
    clear_sql, clear_params = calls[2][0]
    update_sql, update_params = calls[3][0]
    link_sql, link_params = calls[4][0]
    assert "select thread_id from generation_outputs where id = %s and workspace_id = %s" in " ".join(select_sql.lower().split())
    assert select_params == ("uuid1", "ws1")
    assert "update generation_outputs set is_final = false where thread_id = %s and is_final = true" in " ".join(clear_sql.lower().split())
    assert clear_params == ("thread1",)
    assert "set is_final = true" in " ".join(update_sql.lower().split())
    assert update_params == ("uuid1",)
    assert "set final_output_id = %s" in " ".join(link_sql.lower().split())
    assert link_params == ("uuid1", "thread1")
