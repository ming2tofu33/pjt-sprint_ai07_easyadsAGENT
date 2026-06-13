from orchestrator.app.llm.native_copy_candidate_service import candidate_semantic_key, coerce_native_copy_strategy_bundle
from orchestrator.app.schemas.input_evidence import EvidenceItem, InputEvidenceBundle
from orchestrator.app.schemas.native_creative import NativeCopyCandidate
from orchestrator.app.schemas.product_understanding import ProductUnderstanding


def test_candidate_semantic_key_normalizes_visible_copy():
    left = NativeCopyCandidate(candidate_id="a", strategy="minimal_identity", headline="Product A!", supporting_copy=None)
    right = NativeCopyCandidate(candidate_id="b", strategy="minimal_identity", headline="product a", supporting_copy=None)

    assert candidate_semantic_key(left) == candidate_semantic_key(right)


def test_duplicate_candidates_are_removed():
    fact = EvidenceItem(key="product_name", value="Product A", source="user_text", evidence_class="verified_fact", confidence=1.0, usable_for_copy=True)
    evidence = InputEvidenceBundle(input_mode="text_only", user_text="Promote Product A", user_request_utterance="Promote Product A", explicit_product_mentions=["Product A"], explicit_user_facts=[fact], overall_confidence=0.9)
    product = ProductUnderstanding(product_name="Product A", normalized_product_type="product", broad_category="other", category_path=["other"], verified_facts=[fact], product_name_evidence_ids=[fact.evidence_id], confidence=0.9)

    bundle = coerce_native_copy_strategy_bundle({"candidates": [{"candidate_id": "c1", "strategy": "minimal_identity", "headline": "Product A"}, {"candidate_id": "c2", "strategy": "brand_editorial", "headline": "Product A"}]}, input_evidence=evidence, product_understanding=product)

    assert bundle.effective_candidate_count == 1
    assert bundle.deduplication_reasons
