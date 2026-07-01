from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from orchestrator.app.graph.state import (
    append_state_items,
    overlay_current_request_asset_ids,
    read_model,
    write_model,
)
from orchestrator.app.chat_threads.state_service import restore_thread_state_for_generation


class ExampleModel(BaseModel):
    name: str = "default"
    created_at: datetime | None = None


def test_read_model_missing_and_defaults():
    assert read_model({}, "item", ExampleModel) == ExampleModel()
    assert read_model({}, "item", ExampleModel, default=None) is None
    assert read_model({}, "item", ExampleModel, default={"name": "fallback"}) == ExampleModel(name="fallback")


def test_read_model_accepts_instance_and_mapping():
    instance = ExampleModel(name="instance")
    assert read_model({"item": instance}, "item", ExampleModel) is instance
    assert read_model({"item": {"name": "mapping"}}, "item", ExampleModel) == ExampleModel(name="mapping")


def test_read_model_rejects_scalar():
    with pytest.raises(TypeError, match="item must be ExampleModel or mapping"):
        read_model({"item": "invalid"}, "item", ExampleModel)


def test_write_model_returns_json_safe_plain_values():
    created_at = datetime(2026, 1, 2, 3, 4, tzinfo=timezone.utc)
    assert write_model(ExampleModel(name="value", created_at=created_at)) == {
        "name": "value",
        "created_at": "2026-01-02T03:04:00Z",
    }
    assert write_model(None) is None
    assert write_model({"name": "mapping"}) == {"name": "mapping"}


def test_append_state_items_handles_incremental_and_full_list_updates():
    assert append_state_items(None, [{"id": "a"}]) == [{"id": "a"}]
    assert append_state_items([{"id": "a"}], [{"id": "b"}]) == [{"id": "a"}, {"id": "b"}]
    assert append_state_items([{"id": "a"}], []) == [{"id": "a"}]
    assert append_state_items([{"id": "a"}], [{"id": "a"}, {"id": "b"}]) == [
        {"id": "a"},
        {"id": "b"},
    ]


def test_current_asset_ids_override_snapshot_and_legacy_paths():
    restored = overlay_current_request_asset_ids(
        {
            "source_asset_id": "asset_old_source",
            "reference_asset_id": "asset_old_reference",
            "source_image_path": "data/uploads/old-source.png",
            "reference_image_path": "data/uploads/old-reference.png",
            "current_brief": {
                "source_asset_id": "asset_old_source",
                "reference_asset_id": "asset_old_reference",
                "source_image_path": "data/uploads/old-source.png",
                "reference_image_path": "data/uploads/old-reference.png",
            },
        },
        source_asset_id="asset_new_source",
        reference_asset_id="asset_new_reference",
    )

    assert restored["source_asset_id"] == "asset_new_source"
    assert restored["reference_asset_id"] == "asset_new_reference"
    assert restored["source_image_path"] is None
    assert restored["reference_image_path"] is None
    assert restored["current_brief"]["source_asset_id"] == "asset_new_source"
    assert restored["current_brief"]["reference_asset_id"] == "asset_new_reference"


def test_missing_current_asset_ids_preserve_snapshot_ids():
    restored = overlay_current_request_asset_ids(
        {"source_asset_id": "asset_source", "reference_asset_id": "asset_reference"},
        source_asset_id=None,
        reference_asset_id=None,
    )
    assert restored["source_asset_id"] == "asset_source"
    assert restored["reference_asset_id"] == "asset_reference"


def test_legacy_paths_do_not_create_asset_ids():
    restored = overlay_current_request_asset_ids(
        {"source_image_path": "data/uploads/source.png", "reference_image_path": "data/uploads/reference.png"},
        source_asset_id=None,
        reference_asset_id=None,
    )
    assert "source_asset_id" not in restored
    assert "reference_asset_id" not in restored


def test_generation_restore_applies_current_asset_ids_to_brief():
    snapshot = SimpleNamespace(
        state_payload={
            "source_asset_id": "asset_old_source",
            "reference_asset_id": "asset_old_reference",
            "source_image_path": "data/uploads/old-source.png",
            "reference_image_path": "data/uploads/old-reference.png",
            "current_brief": {"source_asset_id": "asset_old_source"},
        }
    )
    restored = restore_thread_state_for_generation(
        snapshot,
        {
            "source_asset_id": "asset_new_source",
            "reference_asset_id": "asset_new_reference",
            "source_image_path": "data/uploads/current-source.png",
            "reference_image_path": "data/uploads/current-reference.png",
        },
        "Create another ad",
        "continue",
    )
    assert restored["source_asset_id"] == "asset_new_source"
    assert restored["reference_asset_id"] == "asset_new_reference"
    assert restored["source_image_path"] is None
    assert restored["reference_image_path"] is None
    assert restored["current_brief"]["source_asset_id"] == "asset_new_source"
    assert restored["current_brief"]["reference_asset_id"] == "asset_new_reference"
