"""OpenAI-compatible local VLM adapter.

This module never loads local model weights. It only talks to a configured
OpenAI-compatible multimodal endpoint when explicitly called.
"""

from __future__ import annotations

import base64
import json
import mimetypes
from pathlib import Path
from time import perf_counter
from urllib import request as urlrequest

from orchestrator.app.quality_gate import settings
from orchestrator.app.quality_gate.errors import QualityGateUnavailable
from orchestrator.app.quality_gate.ocr_validation import validate_ocr_text
from orchestrator.app.quality_gate.policy import aggregate_quality_decision
from orchestrator.app.quality_gate.schemas import QualityCheckResult, VLMQualityGateResult, VLMQualityRequest


class OpenAICompatibleVisionAdapter:
    provider = "local_openai_compat"

    def __init__(self, *, base_url: str | None = None, model_name: str | None = None, timeout_seconds: int = 20, headers: dict[str, str] | None = None) -> None:
        self.base_url = (base_url or settings.get_local_vlm_base_url()).rstrip("/")
        self.model_name = model_name or settings.get_local_vlm_model()
        self.timeout_seconds = timeout_seconds
        self.headers = dict(headers or {})

    def inspect(self, *, image_path: str, request: VLMQualityRequest) -> VLMQualityGateResult:
        started = perf_counter()
        if not self.base_url:
            raise QualityGateUnavailable("Local VLM endpoint is unavailable.")
        payload = _build_payload(model=self.model_name, request=request, image_path=image_path)
        req = urlrequest.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", **self.headers},
            method="POST",
        )
        try:
            with urlrequest.urlopen(req, timeout=self.timeout_seconds) as response:  # nosec B310 - explicit local/user-configured endpoint
                body = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise QualityGateUnavailable("Local VLM endpoint is unavailable.") from exc
        content = (((body.get("choices") or [{}])[0].get("message") or {}).get("content") or "{}")
        parsed = _parse_result_json(content)
        result = _result_from_adapter_payload(
            stage=request.stage,
            provider=self.provider,
            model_name=self.model_name,
            payload=parsed,
            expected_text=request.expected_text,
            latency_ms=int((perf_counter() - started) * 1000),
        )
        return aggregate_quality_decision(result)


def _build_payload(*, model: str, request: VLMQualityRequest, image_path: str | None = None) -> dict:
    content = [{"type": "text", "text": _prompt_text(request)}]
    if image_path:
        content.append({"type": "image_url", "image_url": {"url": _image_data_url(image_path)}})
    return {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": content,
            }
        ],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }


def _prompt_text(request: VLMQualityRequest) -> str:
    return (
        "Inspect this advertising image. Return compact JSON only with keys: "
        "decision, overall_score, confidence, fake_text, unauthorized_logo, watermark, "
        "copy_safe_area, business_fit, readability, commercial_viability, detected_text. "
        f"stage={request.stage}; business_type={request.business_type}; expected_text={request.expected_text}; "
        "Do not include chain-of-thought."
    )


def _image_data_url(image_path: str) -> str:
    target = Path(image_path)
    if not target.is_file():
        raise QualityGateUnavailable("Quality Gate input image was not found.")
    size_bytes = target.stat().st_size
    max_bytes = settings.get_vlm_image_max_bytes()
    if size_bytes > max_bytes:
        raise QualityGateUnavailable("Quality Gate input image is too large.")
    mime_type = mimetypes.guess_type(target.name)[0] or "image/png"
    encoded = base64.b64encode(target.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _parse_result_json(content: str) -> dict:
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _result_from_adapter_payload(*, stage: str, provider: str, model_name: str, payload: dict, expected_text: list[str], latency_ms: int) -> VLMQualityGateResult:
    detected_text = payload.get("detected_text") if isinstance(payload.get("detected_text"), list) else []
    return VLMQualityGateResult(
        stage=stage,  # type: ignore[arg-type]
        provider=provider,
        model_name=model_name,
        fake_text=_check(payload.get("fake_text")),
        unauthorized_logo=_check(payload.get("unauthorized_logo")),
        watermark=_check(payload.get("watermark")),
        copy_safe_area=_check(payload.get("copy_safe_area")),
        business_fit=_check(payload.get("business_fit")),
        readability=_check(payload.get("readability")),
        commercial_viability=_check(payload.get("commercial_viability")),
        ocr=validate_ocr_text(expected_text=expected_text, detected_text=[str(text) for text in detected_text]),
        decision=payload.get("decision") if payload.get("decision") in {"pass", "retry", "reject", "manual_review", "unavailable"} else "manual_review",
        overall_score=float(payload.get("overall_score") or 0),
        confidence=float(payload.get("confidence") or 0),
        latency_ms=latency_ms,
    )


def _check(value) -> QualityCheckResult:
    if not isinstance(value, dict):
        return QualityCheckResult(status="unknown", score=0, confidence=0)
    status = value.get("status") if value.get("status") in {"pass", "fail", "unknown"} else "unknown"
    return QualityCheckResult(
        status=status,
        score=float(value.get("score") or 0),
        confidence=float(value.get("confidence") or 0),
        evidence=[str(item)[:160] for item in (value.get("evidence") or [])[:5]] if isinstance(value.get("evidence"), list) else [],
    )
