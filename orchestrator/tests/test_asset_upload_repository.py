import pytest
from unittest.mock import MagicMock
from orchestrator.app.db.repositories import assets as asset_repo

def test_create_asset_conflict(monkeypatch):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_cursor.fetchone.return_value = {"id": "123"}
    
    res1 = asset_repo.create_asset(
        workspace_id="ws1",
        bucket="b",
        object_key="k",
        kind="source",
        connection=mock_conn
    )
    assert res1 is not None
    assert "insert into assets" in mock_cursor.execute.call_args[0][0].lower()
    assert "returning *" in mock_cursor.execute.call_args[0][0].lower()

def test_update_asset_with_workspace(monkeypatch):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_cursor.fetchone.return_value = {"id": "123", "public_url": "http://new"}
    
    updated = asset_repo.update_asset(
        "123",
        workspace_id="ws1",
        public_url="http://new",
        connection=mock_conn
    )
    assert updated is not None
    assert "workspace_id = %s" in mock_cursor.execute.call_args[0][0]
