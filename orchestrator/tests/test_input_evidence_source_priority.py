from __future__ import annotations

from orchestrator.app.llm.nodes.input_evidence_normalizer import build_input_evidence_bundle, resolve_product_identity


def test_user_text_identity_wins_over_matching_visual_identity():
    bundle = build_input_evidence_bundle(
        {
            "user_input": "치즈케이크 홍보",
            "context": {"item_or_service": "치즈케이크"},
            "input_visual_observations": [{"key": "product_identity", "value": "치즈케이크", "confidence": 0.95}],
        }
    )

    assert resolve_product_identity(bundle) == "치즈케이크"
    assert bundle.input_conflicts == []


def test_unrelated_visual_identity_requires_manual_review():
    bundle = build_input_evidence_bundle(
        {
            "user_input": "치즈케이크 홍보",
            "context": {"item_or_service": "치즈케이크"},
            "input_visual_observations": [{"key": "product_identity", "value": "macaron", "confidence": 0.95}],
        }
    )

    assert bundle.manual_review_required is True
    assert bundle.input_conflicts[0].severity == "manual_review"

