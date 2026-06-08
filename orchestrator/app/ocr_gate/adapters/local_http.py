"""Local HTTP OCR adapter."""

from __future__ import annotations

import base64
import json
import mimetypes
import socket
from pathlib import Path
from time import perf_counter
from urllib import request as urlrequest
from urllib.error import URLError

from PIL import Image, UnidentifiedImageError

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
            try:
                with urlrequest.urlopen(req, timeout=self.timeout_seconds) as response:  # nosec B310 - user-configured local endpoint
                    body = json.loads(response.read().decode("utf-8"))
            except socket.timeout:
                return _unavailable("ocr_timeout", started)
            except URLError:
                return _unavailable("ocr_connection_failed", started)
            except json.JSONDecodeError:
                return _unavailable("ocr_invalid_json", started)
            if not isinstance(body.get("spans"), list):
                return _unavailable("ocr_invalid_response", started)
            spans = []
            for item in body.get("spans", []):
                if not isinstance(item, dict):
                    continue
                span = _span_from_payload(item)
                if span is not None:
                    spans.append(span)
            return OCRExtractionResult(provider=self.provider, status="ok", spans=spans, latency_ms=int((perf_counter() - started) * 1000))
        except FileNotFoundError:
            return _unavailable("ocr_input_not_found", started)
        except ValueError as exc:
            return _unavailable(str(exc) or "ocr_invalid_input", started)
        except Exception:
            return _unavailable("local_http_ocr_unavailable", started)


def _image_data_url(image_path: str) -> str:
    target = Path(image_path)
    if not target.is_file():
        raise FileNotFoundError("OCR input image was not found.")
    if target.stat().st_size > settings.get_image_max_bytes():
        raise ValueError("ocr_input_too_large")
    try:
        with Image.open(target) as image:
            image.verify()
        with Image.open(target) as image:
            image.load()
    except UnidentifiedImageError as exc:
        raise ValueError("ocr_invalid_image") from exc
    mime_type = mimetypes.guess_type(target.name)[0] or "image/png"
    return f"data:{mime_type};base64,{base64.b64encode(target.read_bytes()).decode('ascii')}"


def _span_from_payload(item: dict) -> OCRSpan | None:
    box = item.get("box") if isinstance(item.get("box"), dict) else None
    try:
        return OCRSpan(
            text=str(item.get("text") or ""),
            normalized_text=normalize_ocr_text(str(item.get("text") or "")),
            confidence=float(item.get("confidence") or 0),
            box=NormalizedBox(**box) if box else None,
            source="ocr",
        )
    except Exception:
        return None


def _unavailable(error_code: str, started: float) -> OCRExtractionResult:
    return OCRExtractionResult(provider="local_http_ocr", status="unavailable", spans=[], error_code=error_code, latency_ms=int((perf_counter() - started) * 1000))
