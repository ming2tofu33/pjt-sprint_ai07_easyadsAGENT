from pathlib import Path

from PIL import Image

from orchestrator.app.graph.state import create_initial_marketing_state
from orchestrator.app.schemas.llm_marketing import InitialMarketingRequest
from orchestrator.app.vision.nodes import product_preprocess_node, reference_preprocess_node


def _image(path: Path) -> Path:
    Image.new("RGB", (80, 80), (200, 140, 120)).save(path)
    return path


def _state(tmp_path: Path):
    return create_initial_marketing_state(
        InitialMarketingRequest(
            user_input="ready",
            job_id="vision-node-test",
            thread_id="vision-node-test",
            source_image_path=str(_image(tmp_path / "source.png")),
            reference_image_path=str(_image(tmp_path / "reference.png")),
        )
    )


def test_reference_preprocess_node_updates_state_fields(tmp_path):
    update = reference_preprocess_node(_state(tmp_path))

    assert update["status"] == "preprocessing_reference_image"
    assert update["reference_style_profile"]["metadata"]["vlm_used"] is False
    assert update["current_brief"]["reference_style_ready"] is True
    assert update["artifact_refs"]


def test_product_preprocess_node_updates_state_fields(tmp_path):
    update = product_preprocess_node(_state(tmp_path))

    assert update["status"] == "preprocessing_product_image"
    assert update["product_preserve_spec"]["preserve_strategy"] == "center_bbox_stub"
    assert update["current_brief"]["product_preserve_ready"] is True
    assert update["artifact_refs"]


def test_preprocess_node_invalid_path_returns_clear_error():
    state = create_initial_marketing_state(
        InitialMarketingRequest(user_input="ready", job_id="vision-node-invalid", thread_id="vision-node-invalid", source_image_path="missing.png")
    )

    update = product_preprocess_node(state)

    assert update["status"] == "failed"
    assert "vision_preprocess_failed" in update["error_message"]
