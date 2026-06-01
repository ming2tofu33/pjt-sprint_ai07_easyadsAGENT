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
    openai_api_key_present: bool = False
    hf_token_present: bool = False
    sd35_model_id: str | None = "stabilityai/stable-diffusion-3.5-large"
    sd35_local_path: str | None = None
    max_images_per_job: int = Field(default=1, ge=1, le=4)
    default_width: int = 1024
    default_height: int = 1024
    gpt_image_model: str = "gpt-image-2"

def load_t2i_settings() -> T2ISettings:
    return T2ISettings(
        enable_external_t2i=_env_bool("EASYADS_ENABLE_EXTERNAL_T2I"),
        enable_gpt_image_2=_env_bool("EASYADS_ENABLE_GPT_IMAGE_2"),
        enable_sd35_local=_env_bool("EASYADS_ENABLE_SD35_LOCAL"),
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
        max_images_per_job=_env_int("EASYADS_T2I_MAX_IMAGES_PER_JOB", 1),
    )


def is_gpt_image_2_enabled(settings: T2ISettings) -> bool:
    return settings.enable_external_t2i and settings.enable_gpt_image_2 and settings.openai_api_key_present


def is_sd35_local_enabled(settings: T2ISettings) -> bool:
    return settings.enable_sd35_local


def require_t2i_enabled(engine: str, settings: T2ISettings) -> None:
    if engine == "gpt_image_2" and not is_gpt_image_2_enabled(settings):
        raise T2IEngineNotEnabledError("GPT-image-2 generation is disabled.")
    if engine == "sd35_large" and not is_sd35_local_enabled(settings):
        raise T2IEngineNotEnabledError("SD3.5 local generation is disabled.")


def _env_bool(name: str) -> bool:
    return str(_get_env(name, "")).strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        value = int(_get_env(name, str(default)))
    except ValueError:
        return default
    return max(1, min(value, 4))


def get_openai_api_key() -> str:
    return _get_env("OPENAI_API_KEY", "")


def get_hf_token() -> str:
    return _get_env("HF_TOKEN", "") or _get_env("HUGGINGFACE_TOKEN", "")

