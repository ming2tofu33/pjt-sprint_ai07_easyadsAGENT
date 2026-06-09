from orchestrator.app.llm.copy_tone_policy import (
    get_copy_tone_policy,
    normalize_copy_for_business,
)


def test_cafe_policy_warns_tacky_discount_terms_without_rewriting():
    result = normalize_copy_for_business(
        {"headline": "\uc5ed\ub300\uae09 \ub300\ubc15 \ub525\uae30\ub77c\ub5bc \uc2e0\uba54\ub274!!", "subcopy": "\ubbf8\uce5c \ud560\uc778", "cta": "\uc9c0\uae08 \ub9cc\ub098\ubcf4\uae30"},
        "cafe",
    )

    normalized = result["normalized_copy"]
    assert "\uc5ed\ub300\uae09" in normalized["headline"]
    assert "\ub300\ubc15" in normalized["headline"]
    assert "\ubbf8\uce5c \ud560\uc778" in normalized["subcopy"]
    assert "avoid_term_detected" in result["warnings"]


def test_restaurant_bbq_policy_uses_reservation_cta():
    policy = get_copy_tone_policy("restaurant_bbq")

    assert any("\uc608\uc57d" in candidate for candidate in policy["cta_candidates"])
    assert policy["promotion_style"] == "reservation_visit"


def test_beauty_skincare_policy_warns_medical_claims_without_rewriting():
    result = normalize_copy_for_business(
        {"headline": "100% \uac1c\uc120 \uae30\uc801 \ucf00\uc5b4", "subcopy": "\uc989\uc2dc \ud6a8\uacfc", "cta": "\uc0c1\ub2f4 \uc608\uc57d\ud558\uae30"},
        "beauty_skincare",
    )

    normalized = result["normalized_copy"]
    assert "100% \uac1c\uc120" in normalized["headline"]
    assert "\uae30\uc801" in normalized["headline"]
    assert "\uc989\uc2dc \ud6a8\uacfc" in normalized["subcopy"]
    assert "avoid_term_detected" in result["warnings"]


def test_beauty_hair_policy_has_hair_or_style_cta():
    policy = get_copy_tone_policy("beauty_hair")

    assert any("\uc2a4\ud0c0\uc77c" in candidate or "\ud5e4\uc5b4" in candidate for candidate in policy["cta_candidates"])


def test_custom_input_mode_does_not_rewrite_copy():
    copy = {"headline": "\uc5ed\ub300\uae09 \ub300\ubc15!!", "subcopy": "\uc6d0\ubb38 \uc720\uc9c0", "cta": "\ubb34\uc870\uac74 \ud074\ub9ad", "mode": "custom_input"}

    result = normalize_copy_for_business(copy, "cafe")

    assert result["normalized_copy"]["headline"] == "\uc5ed\ub300\uae09 \ub300\ubc15!!"
    assert result["normalized_copy"]["cta"] == "\ubb34\uc870\uac74 \ud074\ub9ad"
    assert "custom_input_not_rewritten" in result["warnings"]


def test_generated_mode_normalizes_excessive_punctuation():
    result = normalize_copy_for_business({"headline": "\uc2e0\uba54\ub274!!!", "subcopy": "\uc624\ub298\ub9cc!!!", "cta": "\ubcf4\uae30!!!"}, "generic")

    joined = " ".join(result["normalized_copy"].values())
    assert "!!" not in joined
    assert "normalized_spacing_or_punctuation" in result["applied_rules"]
