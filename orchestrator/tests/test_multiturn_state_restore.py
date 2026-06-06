from orchestrator.app.chat_threads.state_snapshot import restore_persistent_state, calculate_changed_fields

def test_restore_persistent_state_empty():
    assert restore_persistent_state(None) == {}
    assert restore_persistent_state({}) == {}

def test_restore_persistent_state_filters_allowlist():
    payload = {
        "user_input": "ignored",
        "business_type": "done",
        "brand_kit_id": "bk_1",
        "ad_format": "story",
        "some_random_key": "filtered"
    }
    restored = restore_persistent_state(payload)
    assert restored["business_type"] == "done"
    assert restored["brand_kit_id"] == "bk_1"
    assert restored["ad_format"] == "story"
    assert "user_input" in restored  # user_input IS persistent!
    assert "some_random_key" not in restored

def test_calculate_changed_fields():
    old = {"business_type": "old", "ad_format": "story"}
    new = {"business_type": "old", "ad_format": "post", "user_input": "new"}
    changed = calculate_changed_fields(old, new)
    assert sorted(changed) == ["ad_format", "user_input"]
