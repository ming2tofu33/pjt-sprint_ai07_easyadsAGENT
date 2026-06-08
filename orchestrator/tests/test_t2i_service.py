from pathlib import Path

import pytest

from orchestrator.app.modal.schemas import ModalSubmitResult
from orchestrator.app.t2i import graph_engines
from orchestrator.app.t2i.prompts import resolve_negative_prompt
from orchestrator.app.t2i.service import generate_image_v1


def _phrases(prompt: str) -> list[str]:
    return [item.strip().lower() for item in prompt.split(",")]


def test_common_negative_prompt_applies_when_user_prompt_empty():
    effective = resolve_negative_prompt(None, None)

    assert "text" in effective
    assert "watermark" in effective
    assert "broken typography" in effective
    assert "people where not requested" in effective


def test_restaurant_negative_prompt_merges_from_business_type():
    effective = resolve_negative_prompt(None, {"business_type": "restaurant"})

    assert "text" in effective
    assert "dirty table" in effective
    assert "unappetizing food" in effective


def test_food_alias_maps_to_restaurant_negative_prompt():
    effective = resolve_negative_prompt(None, {"business_type": "food"})

    assert "burnt food" in effective
    assert "rotten ingredients" in effective


def test_user_negative_prompt_appends_after_common_and_industry():
    effective = resolve_negative_prompt("bad lighting, text", {"business_type": "cafe"})

    assert "text" in effective
    assert "spilled drink" in effective
    assert "bad lighting" in effective


def test_duplicate_phrases_are_removed_case_insensitively():
    effective = resolve_negative_prompt("TEXT, text, watermark", {"business_type": "restaurant"})
    phrases = _phrases(effective)

    assert phrases.count("text") == 1
    assert phrases.count("watermark") == 1


def test_generate_image_v1_returns_mock_image_path(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("T2I_OUTPUT_DIR", str(tmp_path))
    monkeypatch.setenv("T2I_DEFAULT_ENGINE", "mock")
    result = generate_image_v1(
        prompt="Korean BBQ campaign poster background",
        width=512,
        height=512,
        metadata={"job_id": "job-1", "business_type": "restaurant"},
    )

    assert result.engine == "mock"
    assert result.error is None
    assert result.image_paths == [str(tmp_path / "job-1" / "mock_0.png")]
    assert Path(result.image_paths[0]).exists()


def test_generate_image_v1_metadata_contains_job_and_effective_negative_prompt(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("T2I_OUTPUT_DIR", str(tmp_path))
    monkeypatch.setenv("T2I_DEFAULT_ENGINE", "mock")
    result = generate_image_v1(
        prompt="Cafe signature drink ad background",
        negative_prompt="bad crop",
        metadata={"job_id": "job-meta", "business_type": "beverage"},
    )

    assert result.metadata["job_id"] == "job-meta"
    assert result.metadata["requested_engine"] == "mock"
    assert result.metadata["effective_engine"] == "mock"
    assert "bad crop" in result.metadata["effective_negative_prompt"]
    assert "industry:cafe" in result.metadata["negative_prompt_sources"]
    assert result.metadata["business_type"] == "beverage"
    assert result.metadata["num_images"] == 1


def test_generate_image_v1_uses_job_scoped_output_path(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("T2I_OUTPUT_DIR", str(tmp_path))
    monkeypatch.setenv("T2I_DEFAULT_ENGINE", "mock")
    result = generate_image_v1(
        prompt="Retail product promo background",
        metadata={"job_id": "job-path", "business_type": "product"},
    )

    assert str(tmp_path / "job-path" / "mock_0.png") == result.image_paths[0]


@pytest.mark.parametrize(
    ("engine", "enable_env", "expected_message"),
    [
        ("flux", "EASYADS_ENABLE_FLUX_LOCAL", "FLUX local lane is disabled."),
        ("sd35_large", "EASYADS_ENABLE_SD35_LOCAL", "SD3.5 local generation is disabled."),
    ],
)
def test_generate_image_v1_returns_engine_error_when_graph_actual_lane_is_not_enabled(
    tmp_path: Path,
    monkeypatch,
    engine: str,
    enable_env: str,
    expected_message: str,
):
    monkeypatch.setenv("EASYADS_T2I_EXECUTION_BACKEND", "local")
    monkeypatch.setenv("EASYADS_ENABLE_MODAL_EXECUTION", "false")
    monkeypatch.setenv(enable_env, "false")

    result = generate_image_v1(
        prompt="Premium cafe summer campaign background",
        engine_preference=engine,
        output_dir=str(tmp_path),
        metadata={"job_id": f"job-{engine}"},
    )

    assert result.engine == engine
    assert result.image_paths == []
    assert result.error == expected_message
    assert result.metadata["execution_backend"] == "local"
    assert result.metadata["error_code"] == "t2i_engine_not_enabled"


def test_generate_image_v1_routes_flux_through_modal_and_returns_pending_call_id(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("EASYADS_T2I_EXECUTION_BACKEND", "modal")
    monkeypatch.setenv("EASYADS_ENABLE_MODAL_EXECUTION", "true")
    monkeypatch.setenv("MODAL_TOKEN_ID", "token-id")
    monkeypatch.setenv("MODAL_TOKEN_SECRET", "token-secret")
    captured = {}

    def fake_submit(request):
        captured["request"] = request
        return ModalSubmitResult(
            submitted=True,
            modal_call_id="modal_call_flux",
            status="submitted",
        )

    monkeypatch.setattr(graph_engines, "submit_modal_t2i_job", fake_submit)

    result = generate_image_v1(
        prompt="Premium cafe summer campaign background",
        engine_preference="flux",
        output_dir=str(tmp_path),
        metadata={
            "job_id": "job-modal-flux",
            "thread_id": "thread-public",
            "t2i_params": {"max_sequence_length": 256, "ignored": "nope"},
        },
    )

    assert result.engine == "flux"
    assert result.error is None
    assert result.image_paths == []
    assert result.metadata["execution_backend"] == "modal"
    assert result.metadata["modal_provider"] == "modal"
    assert result.metadata["modal_status"] == "submitted"
    assert result.metadata["modal_call_id"] == "modal_call_flux"
    assert result.metadata["modal_call_id_present"] is True
    assert captured["request"].run_mode == "flux_schnell_real"
    assert captured["request"].engine == "flux"
    assert captured["request"].thread_id == "thread-public"
    assert captured["request"].params["render_mode"] == "flux_schnell"
    assert captured["request"].params["max_sequence_length"] == 256
    assert "ignored" not in captured["request"].params
