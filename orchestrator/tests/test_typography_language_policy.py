from orchestrator.app.schemas.text_layout import TypographyLanguagePolicy


def test_typography_language_policy_defaults_keep_body_korean():
    policy = TypographyLanguagePolicy()
    assert policy.primary_locale == "ko-KR"
    assert policy.body_language_mode == "korean"
    assert "body" in policy.korean_required_roles
    assert "headline" in policy.english_allowed_roles


def test_typography_language_policy_allows_english_display_headline():
    policy = TypographyLanguagePolicy(primary_locale="mixed", headline_language_mode="english")
    assert policy.allow_english_display_headline is True
    assert policy.body_language_mode == "korean"
