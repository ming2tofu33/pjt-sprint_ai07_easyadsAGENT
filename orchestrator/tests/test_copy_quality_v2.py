from orchestrator.app.llm.copy_fallbacks import THEMES, generate_fallback_candidates
from orchestrator.app.llm.copy_quality_v2 import (
    build_deterministic_copy_output_v2,
    contains_generic_meta_phrase,
    rank_copy_candidates,
    select_recommended_copy,
    validate_candidate_diversity,
)
from orchestrator.app.schemas.llm_marketing import CopyCandidate, MarketingContext


def test_copy_fallbacks_cover_at_least_ten_themes():
    assert len(THEMES) >= 10


def test_fallback_candidates_use_three_distinct_angles():
    candidates = generate_fallback_candidates(MarketingContext(business_type="cafe", item_or_service="딸기라떼"))

    assert [candidate.angle for candidate in candidates] == ["product_first", "emotion_first", "benefit_action_first"]
    assert validate_candidate_diversity(candidates)["overall_pass"] is True


def test_ranker_hard_blocks_generic_meta_phrase():
    candidates = [
        CopyCandidate(id="copy_1", headline="상품의 장점을 쉽게 확인해보세요", cta="자세히 보기", angle="product_first"),
        CopyCandidate(id="copy_2", headline="딸기라떼 신메뉴", subcopy="부드럽고 산뜻한 오늘의 한 잔", cta="신메뉴 보기", angle="emotion_first"),
    ]

    ranking = rank_copy_candidates(candidates, business_type="cafe")

    assert contains_generic_meta_phrase(candidates[0].headline)
    assert ranking.recommended_candidate_id == "copy_2"
    assert ranking.blocked_candidate_ids == ["copy_1"]


def test_ranker_flags_near_duplicate_candidates():
    candidates = [
        CopyCandidate(id="copy_1", headline="딸기라떼 신메뉴", subcopy="오늘의 달콤한 한 잔", cta="메뉴 보기", angle="product_first"),
        CopyCandidate(id="copy_2", headline="딸기라떼 신메뉴", subcopy="오늘의 달콤한 한 잔", cta="메뉴 보기", angle="product_first"),
        CopyCandidate(id="copy_3", headline="오늘의 달콤한 한 잔", subcopy="부드러운 카페 메뉴", cta="신메뉴 보기", angle="emotion_first"),
    ]

    diversity = validate_candidate_diversity(candidates)
    ranking = rank_copy_candidates(candidates, business_type="cafe")

    assert diversity["overall_pass"] is False
    assert ranking.diversity_warnings


def test_all_blocked_candidates_require_regeneration_without_recommendation():
    candidates = [
        CopyCandidate(id="copy_1", headline="상품의 장점을 쉽게 확인해보세요", cta="지금 확인하기", angle="product_first"),
        CopyCandidate(id="copy_2", headline="필요한 정보를 간결하게 안내", cta="자세히 보기", angle="emotion_first"),
    ]

    ranking = rank_copy_candidates(candidates, business_type="generic")

    assert ranking.recommended_candidate_id is None
    assert ranking.requires_regeneration is True
    assert select_recommended_copy(candidates, ranking) is None


def test_copy_quality_v2_limits_candidates_to_three():
    output = build_deterministic_copy_output_v2({"context": MarketingContext(business_type="retail", item_or_service="컬렉션")}, max_candidates=5)

    assert len(output.candidates) == 3


def test_fallback_matrix_has_no_generic_meta_phrases_for_core_cases():
    contexts = [
        MarketingContext(business_type="macaron", item_or_service="마카롱 컬렉션", promotion_goal="menu_discovery"),
        MarketingContext(business_type="restaurant_bbq", item_or_service="숯불구이", promotion_goal="reservation_cta"),
        MarketingContext(business_type="beauty_nail", item_or_service="네일 디자인", promotion_goal="consultation"),
        MarketingContext(business_type="photo_studio", item_or_service="꽃다발 프로필 촬영", promotion_goal="reservation_cta"),
        MarketingContext(business_type="car_detailing", item_or_service="차량 디테일링", promotion_goal="inquiry"),
    ]

    for context in contexts:
        output = build_deterministic_copy_output_v2({"context": context})
        assert output.recommended_candidate_id
        assert all(not contains_generic_meta_phrase(" ".join([candidate.headline, candidate.subcopy or "", candidate.cta or ""])) for candidate in output.candidates)
