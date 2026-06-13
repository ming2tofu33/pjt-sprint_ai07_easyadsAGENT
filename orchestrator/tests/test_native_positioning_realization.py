from orchestrator.app.llm.native_copy_policy import build_positioning_realization_plan, direct_positioning_terms_used, score_native_copy_candidate
from orchestrator.app.schemas.native_creative import NativeCopyCandidate


def test_positioning_plan_defaults_to_visual_channels():
    plan = build_positioning_realization_plan(requested_positioning=["premium", "refined"])

    assert plan.realization_mode == "implicit"
    assert plan.copy_expression_policy == "avoid_direct_positioning_terms"
    assert plan.copy_should_carry_positioning is False
    assert "visual_style" in plan.preferred_channels
    assert "typography" in plan.preferred_channels


def test_literal_positioning_gets_penalty():
    candidate = NativeCopyCandidate(
        candidate_id="c1",
        strategy="product_name_first",
        headline="품격 있게 즐기는 된장찌개",
        headline_basis_ids=["e1"],
        language="korean",
        text_block_count=1,
        total_character_count=14,
    )

    score = score_native_copy_candidate(candidate, product_identity="된장찌개", requested_positioning=["premium", "refined"])

    assert "품격" in direct_positioning_terms_used(candidate.headline)
    assert score.direct_positioning_penalty > 0


def test_exact_user_copy_can_use_positioning_term():
    candidate = NativeCopyCandidate(
        candidate_id="c1",
        strategy="product_name_first",
        headline="프리미엄 한우 세트",
        headline_basis_ids=["e1"],
        language="korean",
        text_block_count=1,
        total_character_count=10,
    )

    score = score_native_copy_candidate(candidate, product_identity="한우 세트", requested_positioning=["premium"], exact_user_copy=True)

    assert score.direct_positioning_penalty == 0
