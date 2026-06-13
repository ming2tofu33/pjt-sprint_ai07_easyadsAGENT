from __future__ import annotations

from PIL import Image

from orchestrator.app.llm.nodes.input_evidence_normalizer import build_input_evidence_bundle, input_evidence_normalizer_node


def test_text_intent_and_product_are_separated():
    bundle = build_input_evidence_bundle(
        {
            "user_input": "카페 신메뉴 치즈케이크를 홍보하고 싶어",
            "promotion_goal": "menu_discovery",
            "context": {"business_type": "cafe", "item_or_service": "치즈케이크"},
        }
    )

    assert bundle.input_mode == "text_only"
    assert bundle.user_intent == "menu_discovery"
    assert [item.key for item in bundle.explicit_user_facts] == ["product_name", "launch_status", "business_context"]
    assert not bundle.visual_observations


def test_korean_request_separates_product_intent_and_positioning():
    bundle = build_input_evidence_bundle({"user_input": "고급진 된장찌개를 홍보하고 싶어"})

    assert bundle.explicit_product_mentions == ["된장찌개"]
    assert bundle.campaign_intent == "product_promotion"
    assert "premium" in bundle.desired_positioning
    assert "refined" in bundle.desired_positioning
    assert bundle.non_display_instruction_fragments == ["홍보하고 싶어"]
    assert all("홍보하고 싶어" not in item.value for item in bundle.explicit_user_facts)


def test_image_only_uses_visual_observations_without_user_facts(tmp_path):
    image = tmp_path / "source.png"
    Image.new("RGB", (16, 16), "#ffffff").save(image)

    bundle = build_input_evidence_bundle(
        {
            "source_image_path": str(image),
            "input_visual_observations": [{"key": "product_identity", "value": "cheesecake", "confidence": 0.82}],
        }
    )

    assert bundle.input_mode == "image_only"
    assert bundle.source_image_sha256
    assert bundle.explicit_user_facts == []
    assert bundle.visual_observations[0].source == "image_vlm"


def test_normalizer_node_marks_conflict_manual_review():
    result = input_evidence_normalizer_node(
        {
            "user_input": "치즈케이크 홍보",
            "context": {"item_or_service": "치즈케이크"},
            "input_visual_observations": [{"key": "product_identity", "value": "macaron", "confidence": 0.9}],
        }
    )

    assert result["input_normalization_status"] == "manual_review"
    assert result["input_conflicts"][0]["field"] == "product_identity"


def test_existing_overlay_text_is_not_usable_for_copy():
    bundle = build_input_evidence_bundle(
        {
            "source_image_path": "source.png",
            "input_visual_observations": [
                {"key": "existing_overlay_text", "value": "지금 확인하기", "confidence": 0.9},
                {"key": "product_identity", "value": "cheesecake", "confidence": 0.9},
            ],
        }
    )

    overlay = next(item for item in bundle.visual_observations if item.key == "existing_overlay_text")
    assert overlay.usable_for_copy is False
