"""Structured regeneration patch policy."""

from __future__ import annotations

from typing import Any

from orchestrator.app.validation_feedback.action_mapper import derive_scope
from orchestrator.app.validation_feedback.schemas import SuggestedActionCode


PATCHES: dict[str, dict[str, Any]] = {
    "remove_fake_text": {"target": "image_prompt", "addNegativeConstraints": ["no text", "no letters", "no numbers", "no logo", "no watermark"], "changeSeed": True},
    "remove_watermark": {"target": "image_prompt", "addNegativeConstraints": ["no watermark", "no logo"], "changeSeed": True},
    "increase_copy_safe_area": {"target": "layout", "safeAreaScale": 1.15, "moveSubjectAwayFromCopyZone": True},
    "reduce_visual_clutter": {"target": "image_prompt", "simplifyBackground": True},
    "improve_business_fit": {"target": "image_prompt", "strengthenBusinessCues": True},
    "adjust_copy_contrast": {"target": "textStyle", "increaseContrast": True, "enableShadowOrOverlay": True},
    "adjust_copy_layout": {"target": "layout", "reduceFontScale": True, "increasePadding": True, "rewrapText": True},
    "restore_missing_copy": {"target": "copy", "restoreExpectedCopy": True},
    "rerun_with_prompt_v3_1": {"target": "promptPolicy", "promptVersion": "v3.1"},
    "manual_review": {"target": "manual", "requiresManualReview": True},
}


ORDER = ["manual_review", "rerun_with_prompt_v3_1", "remove_fake_text", "remove_watermark", "reduce_visual_clutter", "improve_business_fit", "restore_missing_copy", "increase_copy_safe_area", "adjust_copy_layout", "adjust_copy_contrast"]


def build_regeneration_patch(actions: list[SuggestedActionCode | str], *, scope: str | None = None, user_instruction: str | None = None) -> dict[str, Any]:
    action_values = []
    for action in actions:
        value = action.value if hasattr(action, "value") else str(action)
        if value in PATCHES and value not in action_values:
            action_values.append(value)
    action_values.sort(key=lambda value: ORDER.index(value) if value in ORDER else 999)
    patches = {value: PATCHES[value] for value in action_values}
    return {
        "scope": scope or derive_scope(action_values),
        "actions": action_values,
        "patches": patches,
        "userInstruction": user_instruction,
    }
