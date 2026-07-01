"""Runtime configuration loader for EasyAds T2I-first services."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import cache
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]


@cache
def _load_dotenv(path: Path) -> dict[str, str]:
    """Parse a dotenv file once per process.

    Cached for the process lifetime: dotenv files are deployment-time inputs,
    not runtime-mutable state. os.environ is NOT cached — _get_env always
    checks it live, so monkeypatched env vars in tests keep working.
    Callers must treat the returned dict as read-only.
    """
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _get_env(name: str, default: str = "") -> str:
    """Read OS env first, then local .env, then default."""
    if name in os.environ:
        return os.environ[name]
    local_env = _load_dotenv(PROJECT_ROOT / ".env")
    if name in local_env:
        return local_env[name]
    return default


def _get_bool(name: str, default: bool) -> bool:
    value = _get_env(name, str(default)).lower()
    return value in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class T2ISettings:
    """Settings needed by local/API T2I engines."""

    openai_api_key: str
    hf_token: str
    default_engine: str
    allow_api_calls: bool
    output_dir: Path
    enable_api_cost_guard: bool
    gpt_image_model: str
    gpt_image_1_model: str
    gpt_image_2_model: str
    sd35_model_id: str
    flux_model_id: str
    flux2_klein_model_id: str

    @classmethod
    def from_env(cls) -> T2ISettings:
        output_dir = Path(_get_env("T2I_OUTPUT_DIR", "data/outputs"))
        if not output_dir.is_absolute():
            output_dir = PROJECT_ROOT / output_dir
        return cls(
            openai_api_key=_get_env("OPENAI_API_KEY", ""),
            hf_token=_get_env("HF_TOKEN", ""),
            default_engine=_get_env("T2I_DEFAULT_ENGINE", "mock"),
            allow_api_calls=_get_bool("T2I_ALLOW_API_CALLS", False),
            output_dir=output_dir,
            enable_api_cost_guard=_get_bool("T2I_ENABLE_API_COST_GUARD", True),
            gpt_image_model=_get_env("T2I_GPT_IMAGE_MODEL", "gpt-image-1"),
            gpt_image_1_model=_get_env("EASYADS_GPT_IMAGE_1_MODEL", "gpt-image-1"),
            gpt_image_2_model=_get_env("EASYADS_GPT_IMAGE_2_MODEL", "gpt-image-2"),
            sd35_model_id=_get_env("T2I_SD35_MODEL_ID", "stabilityai/stable-diffusion-3.5-large"),
            flux_model_id=_get_env("T2I_FLUX_MODEL_ID", "black-forest-labs/FLUX.1-schnell"),
            flux2_klein_model_id=_get_env("EASYADS_T2I_FLUX2_KLEIN_MODEL_ID", "black-forest-labs/FLUX.2-klein-4B"),
        )


def get_t2i_settings() -> T2ISettings:
    """Return current T2I settings."""
    return T2ISettings.from_env()
