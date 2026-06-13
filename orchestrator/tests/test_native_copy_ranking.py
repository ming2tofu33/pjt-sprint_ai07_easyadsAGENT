from orchestrator.app.llm.native_copy_policy import score_native_copy_candidate
from orchestrator.app.schemas.native_creative import NativeCopyCandidate


def test_product_centered_candidate_scores_above_literal_prestige():
    literal = NativeCopyCandidate(candidate_id="literal", strategy="product_name_first", headline="품격 있게 즐기는 된장찌개", headline_basis_ids=["e1"], text_block_count=1, total_character_count=14)
    centered = NativeCopyCandidate(candidate_id="centered", strategy="minimal_identity", headline="된장찌개", supporting_copy="구수한 한 그릇", headline_basis_ids=["e1"], text_block_count=2, total_character_count=11, sensory_terms_used=["구수한"])

    literal_score = score_native_copy_candidate(literal, product_identity="된장찌개", requested_positioning=["premium", "refined"])
    centered_score = score_native_copy_candidate(centered, product_identity="된장찌개", requested_positioning=["premium", "refined"])

    assert centered_score.total_score > literal_score.total_score
    assert centered_score.product_centeredness >= 0.8
    assert centered_score.restraint >= 0.75


def test_headline_support_repetition_is_penalized():
    candidate = NativeCopyCandidate(candidate_id="repeat", strategy="product_name_first", headline="깊은 맛 된장찌개", supporting_copy="깊은 맛 된장찌개", headline_basis_ids=["e1"], text_block_count=2, total_character_count=16)

    score = score_native_copy_candidate(candidate, product_identity="된장찌개", requested_positioning=[])

    assert score.repetition_penalty > 0
    assert "abstract_premium_repetition" in score.blocking_reasons
