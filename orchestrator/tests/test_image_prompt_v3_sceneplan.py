import os
import pytest
from orchestrator.app.llm.scene_planner import build_scene_plan, build_prompt_quality_policy, resolve_business_type
from orchestrator.app.llm.visual_presets import select_visual_preset


@pytest.fixture(autouse=True)
def disable_external_apis():
    vars_to_clear = [
        "EASYADS_ENABLE_EXTERNAL_T2I",
        "EASYADS_ENABLE_GPT_IMAGE_2",
        "EASYADS_ENABLE_SD35_LOCAL",
        "EASYADS_ENABLE_FLUX_LOCAL",
        "EASYADS_QUALITY_BATCH_CONFIRM",
        "OPENAI_API_KEY",
    ]
    old_values = {}
    for var in vars_to_clear:
        if var in os.environ:
            old_values[var] = os.environ[var]
            del os.environ[var]
    yield
    for var, val in old_values.items():
        os.environ[var] = val


def test_cafe_dessert_scene_plan():
    # cafe user_input -> cafe preset / subject_right_copy_left
    scene_plan = build_scene_plan(
        user_input="달콤한 초코 딸기 케이크 신메뉴 광고",
        business_type="cafe",
        ad_format="instagram_feed"
    )
    assert scene_plan.business_type == "cafe"
    assert scene_plan.composition_archetype == "subject_right_copy_left"
    assert scene_plan.reserved_copy_area == "left"
    assert "pastel pink" in scene_plan.desired_mood
    
    # Check forbidden elements contain text/signage terms
    assert any("text" in item or "sign" in item for item in scene_plan.forbidden_visual_elements)


def test_restaurant_bbq_scene_plan():
    # restaurant BBQ user_input -> restaurant_bbq preset / dark warm left copy area
    scene_plan = build_scene_plan(
        user_input="참숯에 구운 프리미엄 한우 삼겹살 갈비",
        business_type="restaurant",
        ad_format="instagram_feed"
    )
    assert scene_plan.business_type == "restaurant_bbq"
    assert scene_plan.composition_archetype == "subject_right_copy_left"
    assert scene_plan.reserved_copy_area == "left"
    assert "premium restaurant mood" in scene_plan.desired_mood
    assert any("menu" in item or "table" in item for item in scene_plan.forbidden_visual_elements)


def test_beauty_subtypes_heuristics():
    # hair
    bt_hair = resolve_business_type(
        user_input="홍대 미용실 헤어 컷트 셋팅펌 스타일링",
        business_type="beauty"
    )
    assert bt_hair == "beauty_hair"
    
    # skincare
    bt_skin = resolve_business_type(
        user_input="피부과 에스테틱 스킨케어 앰플 수분 크림",
        business_type="beauty"
    )
    assert bt_skin == "beauty_skincare"
    
    # nail
    bt_nail = resolve_business_type(
        user_input="여름 젤네일 아트 추천",
        business_type="beauty"
    )
    assert bt_nail == "beauty_nail"
    
    # spa
    bt_spa = resolve_business_type(
        user_input="태국 아로마 스파 마사지 힐링 웰니스",
        business_type="beauty"
    )
    assert bt_spa == "beauty_spa"


def test_ambiguous_beauty_fallback():
    # ambiguous beauty_salon -> beauty_skincare fallback (deterministic)
    bt_ambiguous = resolve_business_type(
        user_input="강남 뷰티샵 미용 서비스",
        business_type="beauty_salon"
    )
    assert bt_ambiguous == "beauty_skincare"
    
    # Explicit mapping override if user input contains hair terms
    bt_ambiguous_hair = resolve_business_type(
        user_input="강남 뷰티샵 헤어 스타일링",
        business_type="beauty_salon"
    )
    assert bt_ambiguous_hair == "beauty_hair"


def test_prompt_quality_policy():
    preset = select_visual_preset("cafe")
    policy = build_prompt_quality_policy(preset)
    
    assert policy.no_text_policy is not None
    assert "left" in policy.safe_area_policy
    assert len(policy.fake_text_negative_terms) > 0
    assert len(policy.positive_safe_area_terms) > 0
