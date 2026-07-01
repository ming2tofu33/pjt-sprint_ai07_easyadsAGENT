import pytest
from pydantic import ValidationError

from orchestrator.app.api.schemas.generation_jobs import GenerationJobCreateRequest
from orchestrator.app.t2i.contracts import (
    GenerationRunMode,
    PUBLIC_T2I_ENGINES,
    RUN_MODE_TO_T2I_ENGINE,
    T2IEngine,
    engine_for_run_mode,
    normalize_generation_run_mode,
    normalize_t2i_engine,
    public_engine_values,
    run_mode_values,
)


def test_public_t2i_engine_set_is_canonical():
    assert set(public_engine_values()) == {"gpt_image_2", "flux2_klein_4b", "sd35_large"}
    assert "gpt_image_1" not in public_engine_values()
    assert set(PUBLIC_T2I_ENGINES) == {
        T2IEngine.GPT_IMAGE_2,
        T2IEngine.FLUX2_KLEIN_4B,
        T2IEngine.SD35_LARGE,
    }


def test_legacy_engine_aliases_normalize_only_through_compatibility_helper():
    assert normalize_t2i_engine("gpt_image_1") is T2IEngine.GPT_IMAGE_2
    assert normalize_t2i_engine("flux") is T2IEngine.FLUX2_KLEIN_4B
    assert normalize_t2i_engine("flux_schnell") is T2IEngine.FLUX2_KLEIN_4B
    assert normalize_t2i_engine("flux2_klein") is T2IEngine.FLUX2_KLEIN_4B
    assert normalize_t2i_engine("gpt_image_1", allow_legacy_alias=False) is None
    assert normalize_t2i_engine("unknown") is None


def test_run_mode_values_and_engine_mapping_are_complete():
    assert set(run_mode_values()) == {mode.value for mode in GenerationRunMode}
    t2i_modes = set(GenerationRunMode) - {
        GenerationRunMode.QUEUED_ONLY,
        GenerationRunMode.GRAPH_JOB,
    }
    assert t2i_modes <= set(RUN_MODE_TO_T2I_ENGINE)
    assert engine_for_run_mode("gpt_image_1_actual") is T2IEngine.GPT_IMAGE_2
    assert engine_for_run_mode("flux_schnell_real") is T2IEngine.FLUX2_KLEIN_4B
    assert engine_for_run_mode("sd35_large_real") is T2IEngine.SD35_LARGE


def test_unknown_run_mode_never_falls_back_to_mock():
    assert normalize_generation_run_mode("unknown") is None
    assert engine_for_run_mode("unknown") is None


def test_generation_job_public_engine_fields_accept_only_canonical_values():
    request = GenerationJobCreateRequest(
        userInput="Create an ad",
        runMode="graph_job",
        imageGenerationEngine="gpt_image_2",
        requestedEngine="flux2_klein_4b",
        t2iEngine="sd35_large",
    )
    assert request.image_generation_engine == "gpt_image_2"
    assert request.requested_engine == "flux2_klein_4b"
    assert request.t2i_engine == "sd35_large"

    with pytest.raises(ValidationError):
        GenerationJobCreateRequest(userInput="Create an ad", imageGenerationEngine="gpt_image_1")
    with pytest.raises(ValidationError):
        GenerationJobCreateRequest(userInput="Create an ad", requestedEngine="unknown")
    with pytest.raises(ValidationError):
        GenerationJobCreateRequest(userInput="Create an ad", runMode="unknown")
