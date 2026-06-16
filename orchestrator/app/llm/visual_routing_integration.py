"""A-8 shadow-only visual routing integration for image prompt planning."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from orchestrator.app.schemas.visual_routing_shadow import RoutingMode, RoutingSource


VISUAL_ROUTING_METADATA_VERSION = "image-prompt-visual-routing-shadow-v1"
_TRACE_ERROR_STAGE_UNKNOWN = "unknown"
_ALLOWED_TRACE_ERROR_STAGES = frozenset({"trace_build"})


def resolve_visual_routing_mode(state: Mapping[str, Any] | None) -> RoutingMode:
    """Resolve the A-8 routing mode.

    The first A-8 PR is shadow-only. A requested canonical mode is coerced to
    SHADOW so production output cannot switch to canonical route selection.
    """

    state = state or {}
    render_options = state.get("render_options") if isinstance(state, Mapping) else {}
    raw_mode = None
    if isinstance(render_options, Mapping):
        raw_mode = render_options.get("visual_routing_mode")
    raw_mode = raw_mode or state.get("visual_routing_mode")
    normalized = str(raw_mode or RoutingMode.SHADOW.value).strip().lower()
    if normalized == RoutingMode.LEGACY.value:
        return RoutingMode.LEGACY
    return RoutingMode.SHADOW


def build_fail_open_visual_routing_metadata(
    *,
    mode: RoutingMode,
    exception: Exception,
    stage: str,
) -> dict[str, Any]:
    return {
        "routing_mode": mode.value,
        "active_source": RoutingSource.LEGACY.value,
        "trace_available": False,
        "trace_error": {
            "stage": _sanitize_trace_error_stage(stage),
            "exception_type": exception.__class__.__name__,
        },
    }


def _sanitize_trace_error_stage(stage: str) -> str:
    if stage in _ALLOWED_TRACE_ERROR_STAGES:
        return stage
    return _TRACE_ERROR_STAGE_UNKNOWN
