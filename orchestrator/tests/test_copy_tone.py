from orchestrator.app.llm.copy_tone import COPY_TONE_MAPPING, get_copy_tone_profile


def test_copy_tone_mapping_supports_required_business_types():
    assert set(COPY_TONE_MAPPING) == {
        "restaurant",
        "cafe",
        "beauty_salon",
        "bar",
        "fitness",
        "academy",
        "flower_shop",
        "store",
    }


def test_copy_tone_profile_returns_fallback_for_unknown_business_type():
    profile = get_copy_tone_profile("unknown_type", "unknown_persona")

    assert profile["voice"] == "friendly_clear"
    assert profile["business_type"] == "unknown_type"
    assert profile["target_persona"] == "unknown_persona"
    assert isinstance(profile["keywords"], list)


def test_copy_tone_profile_adds_persona_hint_when_known():
    profile = get_copy_tone_profile("restaurant", "office_worker")

    assert profile["voice"] == "warm_appetizing"
    assert profile["persona_hint"]["energy"] == "efficient"
