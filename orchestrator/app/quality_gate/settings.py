"""Runtime quality gate settings."""

from __future__ import annotations

from orchestrator.app.core.config import _get_env


def env_bool(name: str, default: bool = False) -> bool:
    raw = _get_env(name, "")
    if raw == "":
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def env_float(name: str, default: float) -> float:
    try:
        return float(_get_env(name, str(default)))
    except ValueError:
        return default


def get_local_vlm_model() -> str:
    return _get_env("EASYADS_VLM_LOCAL_FAST_MODEL", "") or "Qwen/Qwen2-VL-2B-Instruct"


def get_local_vlm_provider() -> str:
    return _get_env("EASYADS_VLM_LOCAL_PROVIDER", "") or "local_openai_compat"


def get_local_vlm_base_url() -> str:
    return _get_env("EASYADS_VLM_LOCAL_BASE_URL", "") or "http://localhost:8000/v1"


def get_api_vlm_model(deep: bool = False) -> str:
    key = "EASYADS_VLM_API_DEEP_MODEL" if deep else "EASYADS_VLM_API_FAST_MODEL"
    return _get_env(key, "") or ("gpt-4o" if deep else "gpt-4o-mini")


def is_quality_gate_enabled() -> bool:
    return env_bool("EASYADS_VLM_GATE_ENABLED", default=False)

