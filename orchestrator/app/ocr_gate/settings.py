"""Runtime OCR gate settings."""

from __future__ import annotations

from orchestrator.app.core.config import _get_env


def env_bool(name: str, default: bool = False) -> bool:
    raw = _get_env(name, "")
    if raw == "":
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    try:
        return int(_get_env(name, str(default)))
    except ValueError:
        return default


def env_float(name: str, default: float) -> float:
    try:
        return float(_get_env(name, str(default)))
    except ValueError:
        return default


def is_ocr_gate_enabled() -> bool:
    return env_bool("EASYADS_OCR_GATE_ENABLED", default=False)


def is_ocr_actual_enabled() -> bool:
    return env_bool("EASYADS_OCR_ACTUAL", default=False)


def is_revision_loop_enabled() -> bool:
    return env_bool("EASYADS_OCR_REVISION_LOOP_ENABLED", default=False)


def get_max_revisions() -> int:
    return max(0, env_int("EASYADS_OCR_MAX_REVISIONS", 1))


def get_ocr_provider() -> str:
    return _get_env("EASYADS_OCR_PROVIDER", "stub") or "stub"


def get_local_ocr_endpoint() -> str:
    return _get_env("EASYADS_OCR_LOCAL_ENDPOINT", "http://localhost:8001/ocr")


def get_ocr_timeout_seconds() -> int:
    return max(1, env_int("EASYADS_OCR_TIMEOUT_SECONDS", 8))


def get_expected_text_match_threshold() -> float:
    return env_float("EASYADS_OCR_EXPECTED_TEXT_MATCH_THRESHOLD", 0.72)


def get_malformed_text_threshold() -> float:
    return env_float("EASYADS_OCR_MALFORMED_TEXT_THRESHOLD", 0.45)


def get_min_span_confidence() -> float:
    return env_float("EASYADS_OCR_MIN_SPAN_CONFIDENCE", 0.35)


def get_image_max_bytes() -> int:
    return max(1, env_int("EASYADS_OCR_IMAGE_MAX_BYTES", 8 * 1024 * 1024))


def get_watermark_terms() -> set[str]:
    raw = _get_env("EASYADS_OCR_WATERMARK_TERMS", "")
    terms = raw.split(",") if raw else ["watermark", "logo", "sample", "shutterstock", "adobe", "getty", "stock", "preview", "dreamstime", "alamy", "123rf", "canva"]
    return {term.strip().lower() for term in terms if term.strip()}

