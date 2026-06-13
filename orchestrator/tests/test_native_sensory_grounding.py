from orchestrator.app.llm.native_copy_policy import score_native_copy_candidate
from orchestrator.app.schemas.native_creative import NativeCopyCandidate


def test_supporting_copy_with_sensory_terms_improves_specificity():
    plain = NativeCopyCandidate(candidate_id="plain", strategy="minimal_identity", headline="된장찌개", headline_basis_ids=["e1"], text_block_count=1, total_character_count=4)
    sensory = NativeCopyCandidate(candidate_id="sensory", strategy="sensory_first", headline="된장찌개", supporting_copy="구수한 한 그릇", headline_basis_ids=["e1"], support_basis_ids=["e1"], sensory_terms_used=["구수한"], text_block_count=2, total_character_count=11)

    plain_score = score_native_copy_candidate(plain, product_identity="된장찌개")
    sensory_score = score_native_copy_candidate(sensory, product_identity="된장찌개")

    assert sensory_score.sensory_specificity >= plain_score.sensory_specificity
    assert sensory_score.support_complementarity >= 0.75
