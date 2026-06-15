"""Adapt native single-shot output to the existing web result contract."""

from __future__ import annotations

from typing import Any


def native_result_adapter_node(state: dict[str, Any]) -> dict[str, Any]:
    result = dict(state.get("native_generation_result") or {})
    image_path = result.get("image_path")
    review = dict(state.get("native_generation_review") or {})
    accepted = state.get("native_generation_status") == "accept" and bool(image_path)
    failure_reasons = review.get("failure_reasons") or [state.get("native_generation_status") or "native_generation_failed"]
    # error는 ErrorResponse.detail(str)까지 흘러감 → list 넣으면 pydantic string_type 검증 크래시.
    # 심사 reason 리스트를 단일 문자열로 합쳐 계약 유지.
    error_text = None if accepted else "; ".join(str(reason) for reason in failure_reasons)
    return {
        "final_image_path": image_path if accepted else None,
        "t2i_result": {
            "engine": "gpt_image_2",
            "image_paths": [image_path] if image_path else [],
            "error": error_text,
            "metadata": {
                "source_node": "gpt_image_2_native_single_shot",
                "native_typography": True,
                "text_overlay_pending": False,
                "image_call_count": int(result.get("image_call_count") or 0),
                "edit_call_count": int(result.get("edit_call_count") or 0),
                "retry_call_count": int(result.get("retry_call_count") or 0),
                "external_renderer_calls": 0,
            },
        },
        "text_overlay_pending": False,
        "render_result": {"metadata": {"source": "native_typography", "has_text_overlay": False, "external_renderer_unused": True}},
        "status": "done" if accepted else "failed",
    }
