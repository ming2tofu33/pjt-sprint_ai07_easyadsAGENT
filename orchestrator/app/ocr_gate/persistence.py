"""Public-safe OCR gate persistence helpers."""

from __future__ import annotations

from typing import Any


OCR_EVENT_BY_DECISION = {
    "pass": "ocr_gate_completed",
    "manual_review": "ocr_gate_manual_review",
    "retry_image": "ocr_gate_retry_requested",
    "retry_layout": "ocr_gate_retry_requested",
    "reject": "ocr_gate_rejected",
    "unavailable": "ocr_gate_unavailable",
}


def build_ocr_gate_payload(*, background: dict | None = None, final: dict | None = None) -> dict:
    decision = (final or background or {}).get("decision")
    return {
        "background": _safe_result(background),
        "final": _safe_result(final),
        "decision": decision,
        "retry_required": decision in {"retry_image", "retry_layout"},
        "revision_action": (final or background or {}).get("revision_action") or "none",
    }


def event_type_for_ocr_decision(decision: str | None) -> str:
    return OCR_EVENT_BY_DECISION.get(str(decision or ""), "ocr_gate_completed")


def build_ocr_event_payload(result: dict) -> dict:
    return {
        "stage": result.get("stage"),
        "provider": result.get("provider"),
        "status": result.get("status"),
        "decision": result.get("decision"),
        "revision_action": result.get("revision_action"),
        "fake_text": bool(result.get("fake_text")),
        "watermark_or_logo_text": bool(result.get("watermark_or_logo_text")),
        "unexpected_text_count": len(result.get("unexpected_text") or []),
        "expected_match_count": len(result.get("expected_matches") or []),
    }


def _safe_result(result: dict[str, Any] | None) -> dict | None:
    if not result:
        return None
    return {
        "stage": result.get("stage"),
        "provider": result.get("provider"),
        "status": result.get("status"),
        "decision": result.get("decision"),
        "fake_text": result.get("fake_text"),
        "watermark_or_logo_text": result.get("watermark_or_logo_text"),
        "confidence": result.get("confidence"),
        "retry_feedback": result.get("retry_feedback") or [],
        "revision_action": result.get("revision_action"),
        "unexpected_text_count": len(result.get("unexpected_text") or []),
        "expected_match_count": len(result.get("expected_matches") or []),
    }
