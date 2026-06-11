from pydantic import ValidationError

from orchestrator.app.schemas.ad_format import AdFormatContract, PlatformSafeZoneSpec


def test_platform_safe_zone_spec_bounds():
    spec = PlatformSafeZoneSpec(top_ratio=0.10, bottom_ratio=0.12, reserved_for_platform_ui=["story_header", "platform_cta"])

    assert spec.top_ratio == 0.10
    assert spec.reserved_for_platform_ui == ["story_header", "platform_cta"]


def test_ad_format_contract_rejects_platform_only_without_platform_cta():
    try:
        AdFormatContract(
            placement="instagram_feed_static",
            aspect_ratio="1:1",
            interaction_mode="non_interactive_image",
            platform_cta_available=False,
            embedded_cta_policy="platform_only",
            platform_safe_zones=PlatformSafeZoneSpec(),
            creative_lane="visual_first",
            text_density_range="minimal",
        )
    except ValidationError as exc:
        assert "platform_only CTA requires" in str(exc)
    else:
        raise AssertionError("expected validation error")


def test_qr_enabled_requires_qr_destination():
    try:
        AdFormatContract(
            placement="print_poster",
            aspect_ratio="1:1",
            interaction_mode="qr_enabled",
            platform_cta_available=False,
            embedded_cta_policy="required",
            platform_safe_zones=PlatformSafeZoneSpec(),
            creative_lane="information_design",
            text_density_range="high",
        )
    except ValidationError as exc:
        assert "qr_destination" in str(exc)
    else:
        raise AssertionError("expected validation error")
