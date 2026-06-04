"""Modal execution settings and readiness guards."""

from __future__ import annotations

from orchestrator.app.core.config import _get_env
from orchestrator.app.modal.errors import ModalExecutionUnavailableError

_ALLOWED_EXECUTION_BACKENDS = {"local", "modal"}
_ALLOWED_RESULT_TRANSPORTS = {"inline_base64"}


def _env_bool(name: str) -> bool:
    return str(_get_env(name, "")).strip().lower() in {"1", "true", "yes", "on"}


def get_t2i_execution_backend_raw() -> str:
    return str(_get_env("EASYADS_T2I_EXECUTION_BACKEND", "local") or "local").strip().lower()


def get_t2i_execution_backend() -> str:
    raw = get_t2i_execution_backend_raw()
    return raw if raw in _ALLOWED_EXECUTION_BACKENDS else "local"


def is_modal_execution_enabled() -> bool:
    return get_t2i_execution_backend() == "modal" and _env_bool("EASYADS_ENABLE_MODAL_EXECUTION")


def is_modal_submit_required() -> bool:
    return _env_bool("EASYADS_MODAL_SUBMIT_REQUIRED")


def is_modal_poll_on_get_enabled() -> bool:
    return _env_bool("EASYADS_MODAL_POLL_ON_GET")


def get_modal_app_name() -> str | None:
    return _get_env("EASYADS_MODAL_APP_NAME", "easyads-t2i").strip() or None


def get_modal_function_name(*, run_mode: str | None = None, engine: str | None = None) -> str | None:
    normalized_run_mode = (run_mode or "").strip().lower()
    if normalized_run_mode in {"flux_schnell_real", "flux_real", "flux_modal_real"}:
        return _get_env("EASYADS_MODAL_FLUX_FUNCTION_NAME", "generate_flux_schnell_image").strip() or None
    if normalized_run_mode in {"sd35_large_real", "sd35_real", "sd35_modal_real"}:
        return _get_env("EASYADS_MODAL_SD35_FUNCTION_NAME", "generate_sd35_large_image").strip() or None
    return _get_env("EASYADS_MODAL_FUNCTION_NAME", "generate_image").strip() or None


def get_modal_environment() -> str | None:
    return _get_env("EASYADS_MODAL_ENVIRONMENT", "").strip() or None


def get_modal_default_gpu() -> str:
    return _get_env("EASYADS_MODAL_DEFAULT_GPU", "L40S").strip() or "L40S"


def get_modal_result_transport() -> str:
    value = _get_env("EASYADS_MODAL_RESULT_TRANSPORT", "inline_base64").strip().lower()
    return value if value in _ALLOWED_RESULT_TRANSPORTS else "inline_base64"


def get_modal_poll_timeout_seconds() -> int:
    return _int_env("EASYADS_MODAL_POLL_TIMEOUT_SECONDS", 0, minimum=0)


def get_modal_poll_interval_seconds() -> float:
    raw = _get_env("EASYADS_MODAL_POLL_INTERVAL_SECONDS", "1").strip()
    try:
        value = float(raw)
    except ValueError:
        return 1.0
    return max(0.1, value)


def get_modal_max_poll_attempts() -> int:
    return _int_env("EASYADS_MODAL_MAX_POLL_ATTEMPTS", 1, minimum=1)


def get_modal_readiness() -> dict:
    raw_backend = get_t2i_execution_backend_raw()
    app_name = get_modal_app_name()
    function_name = get_modal_function_name()
    token_id_present = bool(_get_env("MODAL_TOKEN_ID", "").strip())
    token_secret_present = bool(_get_env("MODAL_TOKEN_SECRET", "").strip())
    missing = []
    if get_t2i_execution_backend() == "modal" or _env_bool("EASYADS_ENABLE_MODAL_EXECUTION"):
        if not app_name:
            missing.append("EASYADS_MODAL_APP_NAME")
        if not function_name:
            missing.append("EASYADS_MODAL_FUNCTION_NAME")
        if not token_id_present:
            missing.append("MODAL_TOKEN_ID")
        if not token_secret_present:
            missing.append("MODAL_TOKEN_SECRET")
    return {
        "enabled": is_modal_execution_enabled(),
        "execution_backend": get_t2i_execution_backend(),
        "backend_valid": raw_backend in _ALLOWED_EXECUTION_BACKENDS,
        "app_name_present": bool(app_name),
        "function_name_present": bool(function_name),
        "token_id_present": token_id_present,
        "token_secret_present": token_secret_present,
        "result_transport": get_modal_result_transport(),
        "missing_requirements": missing,
    }


def require_modal_ready() -> None:
    readiness = get_modal_readiness()
    if not readiness["enabled"]:
        raise ModalExecutionUnavailableError("Modal execution is disabled.")
    if readiness["missing_requirements"]:
        raise ModalExecutionUnavailableError(
            "Modal execution is unavailable. Missing requirements: "
            + ", ".join(readiness["missing_requirements"])
        )


def _int_env(name: str, default: int, minimum: int) -> int:
    raw = _get_env(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(minimum, value)
