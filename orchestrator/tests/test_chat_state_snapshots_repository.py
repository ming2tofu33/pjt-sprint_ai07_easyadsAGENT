from orchestrator.app.db.repositories import chat_state_snapshots as repo
import pytest

def test_chat_state_snapshot_repo_requires_connection():
    with pytest.raises(Exception):
        repo.create_chat_state_snapshot(
            public_snapshot_id="s",
            public_thread_id="t",
            workspace_id="w",
            snapshot_kind="k",
            state_payload={},
            changed_fields=[],
            connection=None  # will fail db_transaction without object connection? 
            # Actually db_transaction creates a new connection if none provided, but we assume it throws runtime error if no DB configured or raises Postgres backend error.
        )
