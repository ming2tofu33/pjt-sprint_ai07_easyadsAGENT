from orchestrator.app.validation_feedback.action_mapper import build_suggested_actions, derive_scope
from orchestrator.app.validation_feedback.schemas import ValidationFailureType


def test_action_mapper_dedupes_and_sorts_by_priority():
    actions = build_suggested_actions(
        [
            ValidationFailureType.UNEXPECTED_TEXT,
            ValidationFailureType.FAKE_TEXT,
            ValidationFailureType.COPY_SAFE_AREA,
        ]
    )

    assert [item.code.value for item in actions] == ["remove_fake_text", "increase_copy_safe_area"]
    assert actions[0].priority == 90


def test_derive_scope_uses_full_for_mixed_actions():
    assert derive_scope(["remove_fake_text"]) == "image"
    assert derive_scope(["adjust_copy_layout"]) == "layout"
    assert derive_scope(["remove_fake_text", "adjust_copy_layout"]) == "full"

