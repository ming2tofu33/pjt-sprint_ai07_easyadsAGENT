"""Guarded T2I lane settings."""

from __future__ import annotations

from pydantic import BaseModel, Field
from orchestrator.app.core.config import _get_env

class T2IEngineNotEnabledError(RuntimeError):
    """Raised when an actual T2I lane is requested without explicit enable flags."""


class T2IEngineUnavailableError(RuntimeError):
    """Raised when an enabled T2I lane cannot run in this environment."""


class T2ISettings(BaseModel):
    enable_external_t2i: bool = False
    enable_gpt_image_2: bool = False
    enable_sd35_local: bool = False
    enable_flux_local: bool = False
    enable_flux2_klein_local: bool = False
    openai_api_key_present: bool = False
    hf_token_present: bool = False
    sd35_model_id: str | None = "stabilityai/stable-diffusion-3.5-large"
    sd35_local_path: str | None = None
    flux_model_id: str | None = "black-forest-labs/FLUX.1-schnell"
    flux_local_path: str | None = None
    flux_device: str = "auto"
    flux_num_inference_steps: int = Field(default=4, ge=1, le=50)
    flux_guidance_scale: float = Field(default=0.0, ge=0.0, le=20.0)
    flux_max_sequence_length: int = Field(default=256, ge=64, le=512)
    flux2_klein_model_id: str | None = "black-forest-labs/FLUX.2-klein-4B"
    flux2_klein_backend: str = "local_diffusers"
    flux2_klein_device: str = "cuda"
    flux2_klein_dtype: str = "bfloat16"
    flux2_klein_enable_cpu_offload: bool = False
    flux2_klein_cache_dir: str | None = ".hf-cache"
    flux2_klein_num_inference_steps: int = Field(default=4, ge=1, le=80)
    flux2_klein_guidance_scale: float = Field(default=1.0, ge=0.0, le=20.0)
    max_images_per_job: int = Field(default=1, ge=1, le=4)
    default_width: int = 1024
    default_height: int = 1024
    gpt_image_model: str = "gpt-image-2"

def load_t2i_settings() -> T2ISettings:
    return T2ISettings(
        enable_external_t2i=_env_bool("EASYADS_ENABLE_EXTERNAL_T2I"),
        enable_gpt_image_2=_env_bool("EASYADS_ENABLE_GPT_IMAGE_2"),
        enable_sd35_local=_env_bool("EASYADS_ENABLE_SD35_LOCAL"),
        enable_flux_local=_env_bool("EASYADS_ENABLE_FLUX_LOCAL"),
        enable_flux2_klein_local=_env_bool("EASYADS_ENABLE_FLUX2_KLEIN_LOCAL"),
        openai_api_key_present=bool(get_openai_api_key()),
        hf_token_present=bool(get_hf_token()),
        gpt_image_model=(
            _get_env("EASYADS_GPT_IMAGE_MODEL", "")
            or _get_env("T2I_GPT_IMAGE_MODEL", "")
            or "gpt-image-2"
        ),
        sd35_model_id=(
            _get_env("EASYADS_SD35_MODEL_ID", "")
            or _get_env("T2I_SD35_MODEL_ID", "")
            or "stabilityai/stable-diffusion-3.5-large"
        ),
        sd35_local_path=_get_env("EASYADS_SD35_LOCAL_PATH", "") or None,
        flux_model_id=(
            _get_env("EASYADS_FLUX_MODEL_ID", "")
            or _get_env("T2I_FLUX_MODEL_ID", "")
            or "black-forest-labs/FLUX.1-schnell"
        ),
        flux_local_path=_get_env("EASYADS_FLUX_LOCAL_PATH", "") or None,
        flux_device=_get_env("EASYADS_FLUX_DEVICE", "") or "auto",
        flux_num_inference_steps=_env_int("EASYADS_FLUX_NUM_INFERENCE_STEPS", 4, minimum=1, maximum=50),
        flux_guidance_scale=_env_float("EASYADS_FLUX_GUIDANCE_SCALE", 0.0, minimum=0.0, maximum=20.0),
        flux_max_sequence_length=_env_int("EASYADS_FLUX_MAX_SEQUENCE_LENGTH", 256, minimum=64, maximum=512),
        flux2_klein_model_id=_get_env("EASYADS_T2I_FLUX2_KLEIN_MODEL_ID", "") or "black-forest-labs/FLUX.2-klein-4B",
        flux2_klein_backend=_get_env("EASYADS_T2I_FLUX2_KLEIN_BACKEND", "") or "local_diffusers",
        flux2_klein_device=_get_env("EASYADS_T2I_FLUX2_KLEIN_DEVICE", "") or "cuda",
        flux2_klein_dtype=_get_env("EASYADS_T2I_FLUX2_KLEIN_DTYPE", "") or "bfloat16",
        flux2_klein_enable_cpu_offload=_env_bool("EASYADS_T2I_FLUX2_KLEIN_ENABLE_CPU_OFFLOAD", default=False),
        flux2_klein_cache_dir=_get_env("EASYADS_T2I_FLUX2_KLEIN_CACHE_DIR", "") or ".hf-cache",
        flux2_klein_num_inference_steps=_env_int("EASYADS_T2I_FLUX2_KLEIN_STEPS", 4, minimum=1, maximum=80),
        flux2_klein_guidance_scale=_env_float("EASYADS_T2I_FLUX2_KLEIN_GUIDANCE_SCALE", 1.0, minimum=0.0, maximum=20.0),
        max_images_per_job=_env_int("EASYADS_T2I_MAX_IMAGES_PER_JOB", 1),
    )


def is_gpt_image_2_enabled(settings: T2ISettings) -> bool:
    return settings.enable_external_t2i and settings.enable_gpt_image_2 and settings.openai_api_key_present


def is_sd35_local_enabled(settings: T2ISettings) -> bool:
    return settings.enable_sd35_local


def is_flux_local_enabled(settings: T2ISettings) -> bool:
    return settings.enable_flux_local


def is_flux2_klein_enabled(settings: T2ISettings) -> bool:
    if settings.flux2_klein_backend == "local_diffusers":
        return settings.enable_flux2_klein_local
    if settings.flux2_klein_backend == "modal":
        try:
            from orchestrator.app.modal import settings as modal_settings

            return modal_settings.is_modal_execution_enabled()
        except Exception:
            return False
    return False


def require_t2i_enabled(engine: str, settings: T2ISettings) -> None:
    if engine == "gpt_image_2" and not is_gpt_image_2_enabled(settings):
        raise T2IEngineNotEnabledError("GPT-image-2 generation is disabled.")
    if engine == "sd35_large" and not is_sd35_local_enabled(settings):
        raise T2IEngineNotEnabledError("SD3.5 local generation is disabled.")
    if engine in {"flux", "flux_local", "flux_schnell"} and not is_flux_local_enabled(settings):
        raise T2IEngineNotEnabledError("FLUX local lane is disabled.")
    if engine == "flux2_klein_4b" and not is_flux2_klein_enabled(settings):
        raise T2IEngineNotEnabledError("FLUX.2 Klein generation is disabled.")


def _env_bool(name: str, default: bool = False) -> bool:
    raw = _get_env(name, "")
    if raw == "":
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int, minimum: int = 1, maximum: int = 4) -> int:
    try:
        value = int(_get_env(name, str(default)))
    except ValueError:
        return default
    return max(minimum, min(value, maximum))


def _env_float(name: str, default: float, minimum: float, maximum: float) -> float:
    try:
        value = float(_get_env(name, str(default)))
    except ValueError:
        return default
    return max(minimum, min(value, maximum))


def get_openai_api_key() -> str:
    return _get_env("OPENAI_API_KEY", "")


def get_hf_token() -> str:
    return _get_env("HF_TOKEN", "") or _get_env("HUGGINGFACE_TOKEN", "")

