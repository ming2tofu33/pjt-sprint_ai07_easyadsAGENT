"""OCR gate smoke runner.

Default path uses generated PIL fixtures and fake OCR spans. Actual OCR endpoint
is opt-in with --actual and EASYADS_OCR_ACTUAL=1.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw

from orchestrator.app.ocr_gate.adapters.local_http import LocalHTTPOCRAdapter
from orchestrator.app.ocr_gate.adapters.stub import FakeOCRAdapter
from orchestrator.app.ocr_gate.schemas import NormalizedBox, OCRSpan, OCRValidationRequest
from orchestrator.app.ocr_gate.service import run_ocr_gate
from orchestrator.app.ocr_gate.text_normalization import normalize_ocr_text

OUTPUT_DIR = Path("data/outputs/ocr_gate_smoke")


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    background_path, final_path = _write_fixtures()
    background_request = OCRValidationRequest(stage="background", image_path=background_path.as_posix())
    final_request = OCRValidationRequest(
        stage="final_ad",
        image_path=final_path.as_posix(),
        expected_text=["여름 시즌 아이스라떼", "지금 주문하기"],
    )
    actual = {"executed": False, "reason": "disabled"}
    if args.actual:
        if os.getenv("EASYADS_OCR_ACTUAL") != "1":
            actual = {"executed": False, "reason": "EASYADS_OCR_ACTUAL not enabled"}
            background = run_ocr_gate(request=background_request, adapter=_background_fake_adapter())
            final_ad = run_ocr_gate(request=final_request, adapter=_final_fake_adapter())
        else:
            adapter = LocalHTTPOCRAdapter()
            actual = {"executed": True, "reason": None}
            background = run_ocr_gate(request=background_request, adapter=adapter)
            final_ad = run_ocr_gate(request=final_request, adapter=adapter)
    else:
        background = run_ocr_gate(request=background_request, adapter=_background_fake_adapter())
        final_ad = run_ocr_gate(request=final_request, adapter=_final_fake_adapter())

    report = {
        "schema_version": "ocr_gate_smoke_v1",
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "background": _summary(background.model_dump(mode="json")),
        "final_ad": _summary(final_ad.model_dump(mode="json")),
        "actual_ocr": actual,
    }
    target = OUTPUT_DIR / "ocr_gate_result.json"
    target.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"status": "ok", "report": target.as_posix()}, ensure_ascii=False))
    return 0


def _write_fixtures() -> tuple[Path, Path]:
    bg = OUTPUT_DIR / "background_with_fake_text.png"
    final = OUTPUT_DIR / "final_ad_with_korean_copy.png"
    for path, texts in (
        (bg, ["SALE 50%", "SAMPLE"]),
        (final, ["여름 시즌 아이스라떼", "지금 주문하기"]),
    ):
        image = Image.new("RGB", (512, 512), "#f4efe7")
        draw = ImageDraw.Draw(image)
        y = 180
        for text in texts:
            draw.text((80, y), text, fill="#111827")
            y += 56
        image.save(path)
    return bg, final


def _span(text: str, confidence: float = 0.95) -> OCRSpan:
    return OCRSpan(
        text=text,
        normalized_text=normalize_ocr_text(text),
        confidence=confidence,
        box=NormalizedBox(x1=100, y1=100, x2=700, y2=180),
        source="ocr",
    )


def _background_fake_adapter() -> FakeOCRAdapter:
    return FakeOCRAdapter([_span("SALE 50%"), _span("SAMPLE")])


def _final_fake_adapter() -> FakeOCRAdapter:
    return FakeOCRAdapter([_span("여름 시즌 아이스라떼"), _span("지금 주문하기")])


def _summary(result: dict) -> dict:
    return {
        "decision": result.get("decision"),
        "status": result.get("status"),
        "fake_text": result.get("fake_text"),
        "watermark_or_logo_text": result.get("watermark_or_logo_text"),
        "unexpected_text": [span.get("text") for span in result.get("unexpected_text", [])],
        "expected_matches": result.get("expected_matches", []),
        "retry_feedback": result.get("retry_feedback", []),
        "revision_action": result.get("revision_action"),
    }


def _parse_args(argv: list[str] | None = None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--actual", action="store_true")
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
