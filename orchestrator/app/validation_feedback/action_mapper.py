"""Map validation failures to deterministic suggested actions."""

from __future__ import annotations

from orchestrator.app.validation_feedback.schemas import SuggestedAction, SuggestedActionCode, ValidationFailureType


ACTION_BY_FAILURE = {
    ValidationFailureType.WATERMARK: SuggestedAction(code=SuggestedActionCode.REMOVE_WATERMARK, scope="image", priority=100, reason="Watermark or logo-like text was detected."),
    ValidationFailureType.UNAUTHORIZED_LOGO: SuggestedAction(code=SuggestedActionCode.REMOVE_WATERMARK, scope="image", priority=100, reason="Unauthorized logo-like text was detected."),
    ValidationFailureType.FAKE_TEXT: SuggestedAction(code=SuggestedActionCode.REMOVE_FAKE_TEXT, scope="image", priority=90, reason="Unexpected readable or fake text was detected in the image."),
    ValidationFailureType.UNEXPECTED_TEXT: SuggestedAction(code=SuggestedActionCode.REMOVE_FAKE_TEXT, scope="image", priority=85, reason="Unexpected text should be removed before copy overlay."),
    ValidationFailureType.COPY_MISSING: SuggestedAction(code=SuggestedActionCode.RESTORE_MISSING_COPY, scope="copy", priority=80, reason="Expected copy is missing from the final ad."),
    ValidationFailureType.COPY_MALFORMED: SuggestedAction(code=SuggestedActionCode.ADJUST_COPY_LAYOUT, scope="layout", priority=80, reason="Rendered copy appears malformed."),
    ValidationFailureType.COPY_CLIPPING: SuggestedAction(code=SuggestedActionCode.ADJUST_COPY_LAYOUT, scope="layout", priority=80, reason="Rendered copy may be clipped."),
    ValidationFailureType.COPY_SAFE_AREA: SuggestedAction(code=SuggestedActionCode.INCREASE_COPY_SAFE_AREA, scope="layout", priority=75, reason="Copy safe area needs more room."),
    ValidationFailureType.COPY_UNREADABLE: SuggestedAction(code=SuggestedActionCode.ADJUST_COPY_CONTRAST, scope="layout", priority=70, reason="Copy readability is below the target."),
    ValidationFailureType.COPY_CONTRAST: SuggestedAction(code=SuggestedActionCode.ADJUST_COPY_CONTRAST, scope="layout", priority=70, reason="Copy contrast needs adjustment."),
    ValidationFailureType.BUSINESS_FIT: SuggestedAction(code=SuggestedActionCode.IMPROVE_BUSINESS_FIT, scope="image", priority=60, reason="Visual business fit should be improved."),
    ValidationFailureType.VISUAL_CLUTTER: SuggestedAction(code=SuggestedActionCode.REDUCE_VISUAL_CLUTTER, scope="image", priority=55, reason="Background should be simplified."),
    ValidationFailureType.PROVIDER_UNAVAILABLE: SuggestedAction(code=SuggestedActionCode.MANUAL_REVIEW, scope="manual", priority=30, reason="Validation provider was unavailable."),
    ValidationFailureType.MANUAL_REVIEW_REQUIRED: SuggestedAction(code=SuggestedActionCode.MANUAL_REVIEW, scope="manual", priority=30, reason="Manual review is required."),
}


def build_suggested_actions(failure_types: list[ValidationFailureType], *, prompt_upgrade: bool = False) -> list[SuggestedAction]:
    by_code: dict[SuggestedActionCode, SuggestedAction] = {}
    for failure in failure_types:
        action = ACTION_BY_FAILURE.get(failure)
        if not action:
            continue
        existing = by_code.get(action.code)
        if not existing or action.priority > existing.priority:
            by_code[action.code] = action
    if prompt_upgrade:
        by_code[SuggestedActionCode.RERUN_WITH_PROMPT_V3_1] = SuggestedAction(
            code=SuggestedActionCode.RERUN_WITH_PROMPT_V3_1,
            scope="full",
            priority=40,
            reason="Prompt policy upgrade is recommended.",
        )
    return sorted(by_code.values(), key=lambda item: (-item.priority, item.code.value))


def derive_scope(actions: list[SuggestedActionCode | str]) -> str:
    scopes = set()
    for action in actions:
        code = action.value if hasattr(action, "value") else str(action)
        if code in {"remove_fake_text", "remove_watermark", "reduce_visual_clutter", "improve_business_fit"}:
            scopes.add("image")
        elif code in {"adjust_copy_layout", "increase_copy_safe_area", "adjust_copy_contrast"}:
            scopes.add("layout")
        elif code == "restore_missing_copy":
            scopes.add("copy")
        elif code in {"manual_review", "rerun_with_prompt_v3_1"}:
            scopes.add("full")
    if not scopes:
        return "full"
    return next(iter(scopes)) if len(scopes) == 1 else "full"
