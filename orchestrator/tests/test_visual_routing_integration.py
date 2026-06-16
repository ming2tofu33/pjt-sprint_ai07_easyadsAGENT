from __future__ import annotations

from orchestrator.app.llm.visual_routing_integration import (
    build_fail_open_visual_routing_metadata,
    resolve_visual_routing_mode,
)
from orchestrator.app.schemas.visual_routing_shadow import RoutingMode, RoutingSource


def test_a8_visual_routing_mode_defaults_to_shadow():
    assert resolve_visual_routing_mode({}) == RoutingMode.SHADOW


def test_a8_visual_routing_mode_reads_render_options():
    state = {"render_options": {"visual_routing_mode": "legacy"}}

    assert resolve_visual_routing_mode(state) == RoutingMode.LEGACY


def test_a8_visual_routing_mode_rejects_canonical_for_first_shadow_pr():
    state = {"render_options": {"visual_routing_mode": "canonical"}}

    assert resolve_visual_routing_mode(state) == RoutingMode.SHADOW


def test_a8_fail_open_metadata_is_sanitized():
    metadata = build_fail_open_visual_routing_metadata(
        mode=RoutingMode.SHADOW,
        exception=RuntimeError("contains user prompt or secret"),
        stage="trace_build",
    )

    assert metadata == {
        "routing_mode": "shadow",
        "active_source": RoutingSource.LEGACY.value,
        "trace_available": False,
        "trace_error": {
            "stage": "trace_build",
            "exception_type": "RuntimeError",
        },
    }
    assert "secret" not in str(metadata)


def test_a8_fail_open_metadata_sanitizes_unknown_trace_stage():
    metadata = build_fail_open_visual_routing_metadata(
        mode=RoutingMode.SHADOW,
        exception=RuntimeError("contains user prompt or secret"),
        stage="contains user prompt or secret",
    )

    assert metadata["trace_error"] == {
        "stage": "unknown",
        "exception_type": "RuntimeError",
    }
    metadata_text = str(metadata)
    assert "contains user prompt or secret" not in metadata_text
    assert "secret" not in metadata_text
