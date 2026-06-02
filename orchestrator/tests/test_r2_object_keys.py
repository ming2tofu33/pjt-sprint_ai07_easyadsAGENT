import pytest

from orchestrator.app.storage.object_keys import build_generation_object_key, safe_object_key_part


def test_build_generation_object_key_uses_expected_convention():
    key = build_generation_object_key(
        workspace_id="workspace_1",
        thread_id="thread_1",
        job_id="job_1",
        filename="final_0.png",
    )

    assert key == "workspaces/workspace_1/threads/thread_1/jobs/job_1/final_0.png"


def test_safe_object_key_part_sanitizes_traversal_and_backslashes():
    assert safe_object_key_part(r"..\unsafe/name.png") == "name.png"
    assert safe_object_key_part(" spaced value ") == "spaced_value"


def test_build_generation_object_key_uses_filename_basename():
    key = build_generation_object_key(
        workspace_id="workspace_1",
        thread_id="thread_1",
        job_id="job_1",
        filename="nested/path/final_0.png",
    )

    assert key.endswith("/final_0.png")


def test_safe_object_key_part_rejects_empty_values():
    with pytest.raises(ValueError):
        safe_object_key_part("..")
