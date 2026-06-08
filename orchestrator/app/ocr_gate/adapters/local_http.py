"""Local HTTP OCR adapter."""

from __future__ import annotations

import base64
import json
import mimetypes
from pathlib import Path
from time import perf_counter
from urllib import request as urlrequest

from orchestrator.app.ocr_gate import settings
from orchestrator.app.ocr_gate.schemas import NormalizedBox, OCRExtractionResult, OCRSpan
from orchestrator.app.ocr_gate.text_normalization import normalize_ocr_text


class LocalHTTPOCRAdapter:
    provider = "local_http_ocr"

    def __init__(self, *, endpoint: str | None = None, timeout_seconds: int | None = None) -> None:
        self.endpoint = endpoint or settings.get_local_ocr_endpoint()
        self.timeout_seconds = timeout_seconds or settings.get_ocr_timeout_seconds()

    def extract_text(self, *, image_path: str, stage: str) -> OCRExtractionResult:
        started = perf_counter()
        try:
            payload = {"image": _image_data_url(image_path), "stage": stage}
            req = urlrequest.Request(
                self.endpoint,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlrequest.urlopen(req, timeout=self.timeout_seconds) as response:  # nosec B310 - user-configured local endpoint
                body = json.loads(response.read().decode("utf-8"))
            spans = [_span_from_payload(item) for item in body.get("spans", []) if isinstance(item, dict)]
            return OCRExtractionResult(provider=self.provider, status="ok", spans=spans, latency_ms=int((perf_counter() - started) * 1000))
        except Exception:
            return OCRExtractionResult(provider=self.provider, status="unavailable", spans=[], error_code="local_http_ocr_unavailable", latency_ms=int((perf_counter() - started) * 1000))


def _image_data_url(image_path: str) -> str:
    target = Path(image_path)
    if not target.is_file():
        raise FileNotFoundError("OCR input image was not found.")
    if target.stat().st_size > settings.get_image_max_bytes():
        raise ValueError("OCR input image is too large.")
    mime_type = mimetypes.guess_type(target.name)[0] or "image/png"
    return f"data:{mime_type};base64,{base64.b64encode(target.read_bytes()).decode('ascii')}"


def _span_from_payload(item: dict) -> OCRSpan:
    box = item.get("box") if isinstance(item.get("box"), dict) else None
    return OCRSpan(
        text=str(item.get("text") or ""),
        normalized_text=normalize_ocr_text(str(item.get("text") or "")),
        confidence=float(item.get("confidence") or 0),
        box=NormalizedBox(**box) if box else None,
        source="ocr",
    )
