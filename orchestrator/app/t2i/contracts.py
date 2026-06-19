"""Canonical generation run-mode and T2I engine contracts."""

from __future__ import annotations

from enum import Enum


class T2IEngine(str, Enum):
    MOCK = "mock"
    GPT_IMAGE_2 = "gpt_image_2"
    FLUX2_KLEIN_4B = "flux2_klein_4b"
    SD35_LARGE = "sd35_large"


class GenerationRunMode(str, Enum):
    QUEUED_ONLY = "queued_only"
    MOCK_IMMEDIATE = "mock_immediate"
    GRAPH_JOB = "graph_job"
    GPT_IMAGE_1_ACTUAL = "gpt_image_1_actual"
    GPT_IMAGE_1_SMOKE = "gpt_image_1_smoke"
    GPT_IMAGE_2_ACTUAL = "gpt_image_2_actual"
    GPT_IMAGE_2_SMOKE = "gpt_image_2_smoke"
    SD35_LOCAL = "sd35_local"
    SD35_LOCAL_SMOKE = "sd35_local_smoke"
    SD35_LARGE_REAL = "sd35_large_real"
    FLUX_LOCAL = "flux_local"
    FLUX_LOCAL_SMOKE = "flux_local_smoke"
    FLUX_SCHNELL_REAL = "flux_schnell_real"
    FLUX = "flux"
    FLUX_SMOKE = "flux_smoke"
    FLUX2_KLEIN_4B = "flux2_klein_4b"


PUBLIC_T2I_ENGINES: tuple[T2IEngine, ...] = (
    T2IEngine.GPT_IMAGE_2,
    T2IEngine.FLUX2_KLEIN_4B,
    T2IEngine.SD35_LARGE,
)

LEGACY_T2I_ENGINE_ALIASES: dict[str, T2IEngine] = {
    "gpt_image_1": T2IEngine.GPT_IMAGE_2,
    "gpt_image1": T2IEngine.GPT_IMAGE_2,
    "gptimage1": T2IEngine.GPT_IMAGE_2,
    "flux": T2IEngine.FLUX2_KLEIN_4B,
    "flux_schnell": T2IEngine.FLUX2_KLEIN_4B,
    "flux_1_schnell": T2IEngine.FLUX2_KLEIN_4B,
    "flux2_klein": T2IEngine.FLUX2_KLEIN_4B,
    "flux_2_klein_4b": T2IEngine.FLUX2_KLEIN_4B,
    "sd35": T2IEngine.SD35_LARGE,
    "sd3_5_large": T2IEngine.SD35_LARGE,
}

RUN_MODE_TO_T2I_ENGINE: dict[GenerationRunMode, T2IEngine] = {
    GenerationRunMode.MOCK_IMMEDIATE: T2IEngine.MOCK,
    GenerationRunMode.GPT_IMAGE_1_ACTUAL: T2IEngine.GPT_IMAGE_2,
    GenerationRunMode.GPT_IMAGE_1_SMOKE: T2IEngine.GPT_IMAGE_2,
    GenerationRunMode.GPT_IMAGE_2_ACTUAL: T2IEngine.GPT_IMAGE_2,
    GenerationRunMode.GPT_IMAGE_2_SMOKE: T2IEngine.GPT_IMAGE_2,
    GenerationRunMode.SD35_LOCAL: T2IEngine.SD35_LARGE,
    GenerationRunMode.SD35_LOCAL_SMOKE: T2IEngine.SD35_LARGE,
    GenerationRunMode.SD35_LARGE_REAL: T2IEngine.SD35_LARGE,
    GenerationRunMode.FLUX_LOCAL: T2IEngine.FLUX2_KLEIN_4B,
    GenerationRunMode.FLUX_LOCAL_SMOKE: T2IEngine.FLUX2_KLEIN_4B,
    GenerationRunMode.FLUX_SCHNELL_REAL: T2IEngine.FLUX2_KLEIN_4B,
    GenerationRunMode.FLUX: T2IEngine.FLUX2_KLEIN_4B,
    GenerationRunMode.FLUX_SMOKE: T2IEngine.FLUX2_KLEIN_4B,
    GenerationRunMode.FLUX2_KLEIN_4B: T2IEngine.FLUX2_KLEIN_4B,
}

LEGACY_GENERATION_RUN_MODE_ALIASES: dict[str, GenerationRunMode] = {
    "flux2_klein": GenerationRunMode.FLUX2_KLEIN_4B,
    "flux2_klein_4b": GenerationRunMode.FLUX2_KLEIN_4B,
    "flux_2_klein_4b": GenerationRunMode.FLUX2_KLEIN_4B,
    "flux_real": GenerationRunMode.FLUX2_KLEIN_4B,
    "flux_modal_real": GenerationRunMode.FLUX2_KLEIN_4B,
    "sd35_real": GenerationRunMode.SD35_LARGE_REAL,
    "sd35_modal_real": GenerationRunMode.SD35_LARGE_REAL,
}


def normalize_t2i_engine(value: object, *, allow_legacy_alias: bool = True) -> T2IEngine | None:
    if value is None:
        return None
    if isinstance(value, T2IEngine):
        return value
    normalized = str(value).strip().lower().replace("-", "_")
    if normalized in {"gpt_image_1", "gpt_image1", "gptimage1"}:
        return T2IEngine.GPT_IMAGE_2 if allow_legacy_alias else None
    try:
        return T2IEngine(normalized)
    except ValueError:
        return LEGACY_T2I_ENGINE_ALIASES.get(normalized) if allow_legacy_alias else None


def normalize_generation_run_mode(value: object) -> GenerationRunMode | None:
    if value is None:
        return None
    if isinstance(value, GenerationRunMode):
        return value
    try:
        return GenerationRunMode(str(value).strip().lower())
    except ValueError:
        normalized = str(value).strip().lower().replace("-", "_")
        return LEGACY_GENERATION_RUN_MODE_ALIASES.get(normalized)


def engine_value_set() -> set[str]:
    return {engine.value for engine in T2IEngine}


def public_engine_values() -> tuple[str, ...]:
    return tuple(engine.value for engine in PUBLIC_T2I_ENGINES)


def run_mode_values() -> tuple[str, ...]:
    return tuple(mode.value for mode in GenerationRunMode)


def engine_for_run_mode(value: object) -> T2IEngine | None:
    run_mode = normalize_generation_run_mode(value)
    return RUN_MODE_TO_T2I_ENGINE.get(run_mode) if run_mode else None
