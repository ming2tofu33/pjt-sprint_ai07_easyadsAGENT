"""State snapshot serialization and comparison."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping
from datetime import datetime

from orchestrator.app.graph.state import MarketingState
from orchestrator.app.chat_threads.sanitization import sanitize_chat_payload

class ChatStateSerializationError(ValueError):
    pass

_UNSUPPORTED = object()

MAX_PAYLOAD_SIZE = 512 * 1024  # 512 KB

PERSISTENT_FIELDS = {
    "job_id",
    "thread_id",
    "user_id",
    "user_input",
    "business_type",
    "business_subtype",
    "item_or_service",
    "promotion_goal",
    "target_persona",
    "tone",
    "missing_fields",
    "final_brief",
    "ad_format",
    "engine",
    "copy_generation_mode",
    "selected_copy",
    "selected_copy_id",
    "selected_channel_id",
    "selected_reference_template_id",
    "source_image_path",
    "reference_image_path",
    "brand_kit_id",
    "brand_kit_snapshot",
    "plan_policy",
    "user_plan",
    "status",
    # these belong to context in MarketingState, but keeping flat semantics is fine
    "context", 
    "current_brief",
    "marketing_copy",
    "image_prompt_spec",
    "copy_spec",
    "copy_required",
    "text_layout_spec",
    "text_style_spec",
    "text_overlay_pending",
    "t2i_request",
    "t2i_result",
    "candidates",
    "artifact_refs",
    "background_validation_report",
    "safe_area_report",
    "readability_report",
    "render_result",
    "final_validation_report",
    "result_payload",
    "final_image_path",
    "error_message",
    "error_info",
    "selected_tone",
    "custom_direction",
    "user_custom_headline",
    "user_custom_subcopy",
}

def serialize_marketing_state_snapshot(state: Mapping[str, Any]) -> dict[str, Any]:
    """Serialize MarketingState to a persistent dictionary."""
    result: dict[str, Any] = {}
    for key, value in state.items():
        if key not in PERSISTENT_FIELDS:
            continue
        sanitized = _sanitize_value(value)
        if sanitized is not _UNSUPPORTED:
            result[key] = sanitized

    # Apply nested sanitizer
    result = sanitize_chat_payload(result)

    # Size check
    try:
        dumped = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise ChatStateSerializationError("chat_state_snapshot_not_serializable") from exc

    if len(dumped.encode("utf-8")) > MAX_PAYLOAD_SIZE:
        # Try removing some heavy but non-critical persistent fields if too large
        for heavy_key in ["marketing_copy", "image_prompt_spec"]:
            if heavy_key in result:
                del result[heavy_key]
        
        try:
            dumped = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
        except (TypeError, ValueError) as exc:
            raise ChatStateSerializationError("chat_state_snapshot_not_serializable") from exc

        if len(dumped.encode("utf-8")) > MAX_PAYLOAD_SIZE:
            raise ChatStateSerializationError("chat_state_snapshot_too_large")
        
    return result

def _sanitize_value(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return _sanitize_value(value.model_dump(mode="json"))
    if isinstance(value, dict):
        d = {}
        for k, v in value.items():
            sv = _sanitize_value(v)
            if sv is not _UNSUPPORTED:
                d[k] = sv
        return d
    if isinstance(value, (list, tuple, set)):
        lst = []
        for v in list(value)[:100]:
            sv = _sanitize_value(v)
            if sv is not _UNSUPPORTED:
                lst.append(sv)
        return lst
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value.name) # only keep name, no absolute path
    if isinstance(value, (str, int, float, bool)):
        if isinstance(value, str):
            # truncate long strings (e.g. max 10k chars per string to avoid huge json)
            if len(value) > 20000:
                return value[:20000] + "...(truncated)"
        return value
    # fallback
    return _UNSUPPORTED

def calculate_changed_fields(previous_state: dict[str, Any] | None, current_state: dict[str, Any]) -> list[str]:
    """Calculate changed top-level persistent fields."""
    current_persistent = {k: v for k, v in current_state.items() if k in PERSISTENT_FIELDS}
    if not previous_state:
        return sorted(list(current_persistent.keys()))

    previous_persistent = {k: v for k, v in previous_state.items() if k in PERSISTENT_FIELDS}
    keys = set(previous_persistent.keys()) | set(current_persistent.keys())

    missing = object()
    changed = [
        k for k in keys
        if previous_persistent.get(k, missing) != current_persistent.get(k, missing)
    ]
    return sorted(changed)

def restore_persistent_state(latest_snapshot: dict[str, Any] | None) -> dict[str, Any]:
    """Restore state from snapshot, dropping transient properties."""
    if not latest_snapshot:
        return {}
    return {k: v for k, v in latest_snapshot.items() if k in PERSISTENT_FIELDS}
