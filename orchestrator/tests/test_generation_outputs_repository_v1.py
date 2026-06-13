import pytest
from unittest.mock import MagicMock
from orchestrator.app.db.repositories.generation_outputs import (
    create_generation_output,
    get_generation_output_by_public_id,
    list_generation_outputs,
    count_generation_outputs,
    mark_output_final,
)


def _mock_connection():
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    return mock_conn, mock_cur

def test_generation_output_create_get_list_count(monkeypatch):
    # This is a focused mock test to ensure repository queries compile and pass parameters correctly
    mock_conn, mock_cur = _mock_connection()
    
    # 1. create
    mock_cur.fetchone.return_value = {"id": "uuid1", "public_output_id": "out_public_1"}
    out = create_generation_output(
        workspace_id="ws1", thread_id="t1", job_id="j1",
        asset_id="a1", variant_index=0, is_final=False, connection=mock_conn
    )
    assert out["public_output_id"] == "out_public_1"
    
    # 2. get
    get_generation_output_by_public_id(public_output_id="out_public_1", workspace_id="ws1", connection=mock_conn)
    # 3. list
    mock_cur.fetchall.return_value = [{"id": "uuid1"}]
    lst = list_generation_outputs(workspace_id="ws1", public_job_id="j_pub", is_final=True, connection=mock_conn)
    assert len(lst) == 1
    
    # 4. count
    mock_cur.fetchone.return_value = {"total": 1}
    cnt = count_generation_outputs(workspace_id="ws1", public_job_id="j_pub", connection=mock_conn)
    assert cnt == 1

def test_generation_output_mark_final_transaction(monkeypatch):
    mock_conn, mock_cur = _mock_connection()
    
    mock_cur.fetchone.side_effect = [{"thread_id": "thread1"}, {"id": "thread1"}, {"id": "uuid1"}]
    
    mark_output_final(output_id="uuid1", workspace_id="ws1", connection=mock_conn)
    
    # Check that update queries were executed
    assert mock_cur.execute.call_count >= 2
