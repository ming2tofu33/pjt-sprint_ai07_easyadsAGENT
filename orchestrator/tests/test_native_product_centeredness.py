from orchestrator.app.llm.native_copy_policy import score_native_copy_candidate
from orchestrator.app.schemas.native_creative import NativeCopyCandidate


def test_product_identity_missing_blocks_candidate():
    candidate = NativeCopyCandidate(candidate_id="abstract", strategy="context_first", headline="깊이를 담은 순간", headline_basis_ids=["e1"], text_block_count=1, total_character_count=8)

    score = score_native_copy_candidate(candidate, product_identity="된장찌개", requested_positioning=["premium"])

    assert score.blocked is True
    assert "product_identity_missing" in score.blocking_reasons


def test_minimal_product_name_is_valid_candidate():
    candidate = NativeCopyCandidate(candidate_id="minimal", strategy="minimal_identity", headline="된장찌개", headline_basis_ids=["e1"], text_block_count=1, total_character_count=4)

    score = score_native_copy_candidate(candidate, product_identity="된장찌개", requested_positioning=["premium"])

    assert score.blocked is False
    assert score.product_centeredness >= 0.8
