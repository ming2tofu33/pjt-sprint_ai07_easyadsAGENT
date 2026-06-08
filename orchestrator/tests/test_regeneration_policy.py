from orchestrator.app.validation_feedback.regeneration_policy import build_regeneration_patch


def test_regeneration_policy_builds_structured_patch_without_raw_state():
    patch = build_regeneration_patch(["increase_copy_safe_area", "remove_fake_text"], user_instruction="short note")

    assert patch["scope"] == "full"
    assert patch["actions"] == ["remove_fake_text", "increase_copy_safe_area"]
    assert patch["patches"]["remove_fake_text"]["changeSeed"] is True
    assert "local_path" not in str(patch)

