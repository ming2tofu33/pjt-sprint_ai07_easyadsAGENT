from orchestrator.app.llm.copy_fallbacks import THEMES, generate_fallback_candidates
from orchestrator.app.llm.copy_quality_v2 import (
    contains_generic_meta_phrase,
    rank_copy_candidates,
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
