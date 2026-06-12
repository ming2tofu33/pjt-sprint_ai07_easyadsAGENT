from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from orchestrator.app.llm.product_copy_context_service import build_dynamic_product_copy_context
from scripts import _actual_creative_pipeline as pipeline


def test_actual_pipeline_normalizes_input_before_copy(monkeypatch, tmp_path):
    calls: list[str] = []

    class Adapter:
        def normalize_input_evidence(self, *, request, model):
            calls.append("normalize")
            return {
                "input_mode": request.input_mode,
                "user_text": request.user_text,
                "explicit_product_mentions": ["치즈케이크"],
                "explicit_user_facts": [
                    {"key": "product_name", "value": "치즈케이크", "source": "user_text", "evidence_class": "verified_fact", "confidence": 1.0, "usable_for_copy": True}
                ],
                "visual_observations": [{"key": "product_identity", "value": "cheesecake", "source": "image_vlm", "evidence_class": "visual_observation", "confidence": 0.9, "usable_for_copy": True}],
                "input_conflicts": [],
                "unknown_fields": [],
                "unresolved_questions": [],
                "clarification_required": False,
                "manual_review_required": False,
                "overall_confidence": 0.95,
                "provider_metadata": {"vision": {"provider": "openai", "model": "gpt-5.4", "fallback_used": False, "token_usage": {"input_tokens": 3, "output_tokens": 2}}},
            }

        def generate_product_copy(self, *, request, evidence, model):
            calls.append("copy")
            assert evidence["schema_version"] == "input_evidence_bundle_v1"
            assert evidence["visual_observations"][0]["source"] == "image_vlm"
            assert "image_b64" not in str(evidence)
            return {
                "product_understanding": {"product_name": "치즈케이크", "broad_category": "cafe", "explicit_product_candidate": "치즈케이크", "normalized_product_candidate": "치즈케이크", "product_identity_confidence": 0.95},
                "product_copy_context": {"brand_tone": "premium"},
                "copy_candidates": [{"id": "copy_1", "headline": "Creamy cheesecake", "supporting_copy": "Soft cafe dessert", "cta": "Taste today"}],
                "recommended_candidate_id": "copy_1",
                "selected_copy": {"headline": "Creamy cheesecake", "supporting_copy": "Soft cafe dessert", "cta": "Taste today"},
                "input_conflicts": [],
                "requires_manual_review": False,
                "provider_metadata": {"provider": "openai", "model": "gpt-5.4", "fallback_used": False, "token_usage": {"input_tokens": 3, "output_tokens": 2}},
            }

        def evaluate_final_composite(self, *, request, image_path, copy, model):
            calls.append("vlm")
            return {
                "product_match_score": 0.9,
                "copy_product_grounding_score": 0.9,
                "copy_readability_score": 0.9,
                "copy_visual_fit_score": 0.9,
                "product_obstruction_score": 0.1,
                "wrong_domain_detected": False,
                "unsupported_claim_detected": False,
                "commercial_viability_score": 0.9,
                "failure_reasons": [],
                "recommended_action": "none",
                "confidence": 0.9,
                "detected_text": ["Creamy cheesecake"],
                "provider_metadata": {"provider": "openai", "model": "gpt-5.4", "fallback_used": False, "token_usage": {"input_tokens": 3, "output_tokens": 2}},
            }

    class Flux:
        def generate(self, request):
            path = tmp_path / "background.png"
            Image.new("RGB", (128, 128), "#ffffff").save(path)
            return SimpleNamespace(engine="flux2_klein_4b", image_paths=[str(path)], latency_ms=1, metadata={"model_name": "flux"})

    def fake_renderer(request, copy_output, background_path, case_dir):
        final = case_dir / "final_composite.png"
        Image.new("RGB", (128, 128), "#000000").save(final)
        return {"render_result": {"final_image_path": str(final), "rendered_slot_count": 1, "metadata": {}}, "final_image_path": str(final)}

    source = tmp_path / "source.png"
    Image.new("RGB", (128, 128), "#ffffff").save(source)
    monkeypatch.setattr(pipeline, "execute_production_renderer", fake_renderer)
    monkeypatch.setattr(pipeline, "evaluate_final_composite", lambda state: SimpleNamespace(evaluated_image_sha256=pipeline._sha256(Path(state["final_image_path"]))))

    request = pipeline.ActualCreativeInput(case_id="case", input_mode="text_and_image", user_text="치즈케이크 홍보", source_image_path=str(source), output_dir=str(tmp_path))
    result = pipeline.run_actual_creative_case(request, pipeline.ActualCreativeRuntime(openai_adapter=Adapter(), vision_adapter=Adapter(), flux_engine=Flux()))

    assert calls[:2] == ["normalize", "copy"]
    assert result.status == "completed"
    assert result.input_evidence["schema_version"] == "input_evidence_bundle_v1"


def test_hydrate_bundle_filters_request_metadata_from_image_only_facts(tmp_path):
    request = pipeline.ActualCreativeInput(case_id="case_x", input_mode="image_only", source_image_path=str(tmp_path / "source.png"), output_dir=str(tmp_path), seed=82)
    payload = {
        "explicit_user_facts": ["case_x", {"key": "seed", "value": 82}, {"key": "output_dir", "value": str(tmp_path)}],
        "visual_observations": [{"key": "product_identity", "value": "cheesecake", "confidence": 0.9}],
        "overall_confidence": 0.9,
    }

    data = pipeline._hydrate_bundle_payload(request, payload, "sha")

    assert data["explicit_user_facts"] == []
    assert "case_x" not in str(data["explicit_user_facts"])
    assert str(tmp_path) not in str(data["explicit_user_facts"])


def test_existing_overlay_text_source_requires_manual_review(tmp_path):
    request = pipeline.ActualCreativeInput(case_id="case", input_mode="image_only", source_image_path=str(tmp_path / "source.png"), output_dir=str(tmp_path))
    evidence = {
        "visual_observations": [
            {"key": "existing_overlay_text", "value": "지금 확인하기", "confidence": 0.9, "usable_for_copy": False},
            {"key": "product_identity", "value": "cheesecake", "confidence": 0.9},
        ]
    }

    plan = pipeline.resolve_image_use_plan(request, evidence, {})

    assert plan.mode == "manual_review"
    assert "clean_background_required" in plan.reason_codes


def test_visual_product_signal_hydrates_copy_without_user_facts():
    evidence = {
        "input_mode": "image_only",
        "explicit_user_facts": [],
        "visual_observations": [
            {
                "key": "visual_observation_0",
                "value": "round baked cake or cheesecake-like dessert",
                "source": "image_vlm",
                "evidence_class": "visual_observation",
                "confidence": 0.9,
                "usable_for_copy": True,
            }
        ],
    }

    data = pipeline._hydrate_copy_payload(
        {
            "product_understanding": {"product_name": "Cheesecake"},
            "product_copy_context": {},
            "selected_copy": {"headline": "Baked Dessert Menu", "supporting_copy": "A simple cafe dessert to discover today.", "cta": "View menu"},
        },
        evidence,
    )

    assert evidence["explicit_user_facts"] == []
    assert data["product_understanding"]["product_name"] == "Cheesecake"
    assert data["copy_presence_plan"]["mode"] == "image_only"
    assert data["selected_copy"]["headline"] is None
    assert data["selected_copy"]["subcopy"] is None
    assert data["selected_copy"]["cta"] is None


def test_copy_hydration_does_not_insert_generic_cta_or_subcopy():
    data = pipeline._hydrate_copy_payload(
        {
            "product_understanding": {"product_name": "doenjang jjigae"},
            "product_copy_context": {},
            "selected_copy": {"headline": "Doenjang Jjigae", "primary_text": "Warm stew, simply presented.", "cta": None},
        },
        {"explicit_product_mentions": ["doenjang jjigae"], "explicit_user_facts": []},
    )

    assert data["selected_copy"]["headline"] == "Doenjang Jjigae"
    assert data["copy_presence_plan"]["mode"] == "headline_only"
    assert data["selected_copy"]["subcopy"] is None
    assert data["selected_copy"]["cta"] is None
    assert "A focused introduction to" not in str(data["selected_copy"])
    assert "Learn More" not in str(data["selected_copy"])


def test_dynamic_copy_context_blocks_generic_cta_for_korean_food():
    evidence = {
        "input_mode": "text_only",
        "user_text": "된장찌개 메뉴를 홍보하고 싶어",
        "explicit_product_mentions": ["된장찌개 메뉴"],
        "explicit_user_facts": [
            {
                "evidence_id": "evidence_food",
                "key": "product_name",
                "value": "된장찌개 메뉴",
                "normalized_value": "된장찌개 메뉴",
                "source": "user_text",
                "evidence_class": "verified_fact",
                "confidence": 1.0,
                "usable_for_copy": True,
            }
        ],
        "visual_observations": [],
        "unknown_fields": [],
    }
    data = pipeline._hydrate_copy_payload(
        {
            "product_understanding": {
                "product_name": "된장찌개 메뉴",
                "normalized_product_type": "doenjang_jjigae",
                "broad_category": "food_and_beverage",
                "category_path": ["food_and_beverage", "doenjang_jjigae"],
            },
            "product_copy_context": {},
            "selected_copy": {"headline": "Discover Doenjang Jjigae", "supporting_copy": "A focused introduction to doenjang jjigae", "cta": "Learn More"},
        },
        evidence,
    )

    assert data["language_policy"]["primary_language"] == "korean"
    assert data["language_policy"]["english_headline_allowed"] is False
    assert data["interaction_copy_plan"]["action_cta_allowed"] is False
    assert data["selected_copy"]["cta"] is None
    assert data["copy_presence_plan"]["max_text_blocks"] <= 2
    assert data["copy_presence_plan"]["max_text_area_ratio"] <= 0.12
    assert [item["variant_type"] for item in data["minimal_copy_candidates"]] == [
        "image_only",
        "headline_only",
        "headline_plus_support",
        "headline_plus_closing",
    ]


def test_image_only_visual_signal_allows_no_text_plan():
    evidence = {
        "input_mode": "image_only",
        "explicit_user_facts": [],
        "visual_observations": [
            {
                "evidence_id": "visual_1",
                "key": "product_identity",
                "value": "clear cheesecake dessert product",
                "confidence": 0.9,
                "usable_for_copy": True,
            }
        ],
        "unknown_fields": [],
    }

    context = build_dynamic_product_copy_context(
        {},
        {"product_name": "Cheesecake", "normalized_product_type": "cheesecake", "broad_category": "food_and_beverage", "category_path": ["food_and_beverage", "cheesecake"]},
        evidence,
    )

    assert context.copy_presence_plan.mode == "image_only"
    assert context.copy_presence_plan.allowed_roles == []
    assert context.copy_presence_plan.no_text_allowed is True


def test_minimal_copy_candidates_skip_missing_support_and_closing():
    data = pipeline._hydrate_copy_payload(
        {
            "product_understanding": {
                "product_name": "딸기라떼",
                "normalized_product_type": "strawberry_latte",
                "broad_category": "food_and_beverage",
                "category_path": ["food_and_beverage", "strawberry_latte"],
            },
            "product_copy_context": {},
            "selected_copy": {"headline": "새로 만나는 딸기라떼", "supporting_copy": None, "closing_copy": None, "cta": None},
        },
        {"input_mode": "text_only", "explicit_product_mentions": ["딸기라떼"], "explicit_user_facts": []},
    )

    variants = data["minimal_copy_candidates"]

    assert [item["variant_type"] for item in variants] == ["image_only", "headline_only", "headline_plus_closing"]
    for item in variants:
        actual_roles = sum(1 for key in ("headline", "supporting_copy", "closing_copy", "action_cta") if item.get(key))
        assert item["text_block_count"] == actual_roles


def test_vlm_validation_accepts_string_detected_text():
    data = pipeline._validated_vlm_result(
        {
            "product_match_score": 0.9,
            "copy_product_grounding_score": 0.9,
            "copy_readability_score": 0.9,
            "copy_visual_fit_score": 0.9,
            "product_obstruction_score": 0.1,
            "wrong_domain_detected": False,
            "unsupported_claim_detected": False,
            "commercial_viability_score": 0.9,
            "failure_reasons": [],
            "recommended_action": "none",
            "confidence": 0.9,
            "detected_text": "Doenjang Jjigae",
            "provider_metadata": {
                "provider": "openai",
                "model": "gpt-5.4",
                "fallback_used": False,
                "token_usage": {"input_tokens": 1, "output_tokens": 1},
            },
        },
        "gpt-5.4",
    )

    assert data["detected_text"] == ["Doenjang Jjigae"]


def test_vlm_revision_action_blocks_completed_status(tmp_path):
    background = tmp_path / "background.png"
    final = tmp_path / "final.png"
    Image.new("RGB", (32, 32), "#ffffff").save(background)
    Image.new("RGB", (32, 32), "#000000").save(final)
    result = pipeline.ActualCreativeResult(
        case_id="case",
        input_mode="image_only",
        status="completed",
        background_image_path=str(background),
        final_composite_path=str(final),
        background_sha256=pipeline._sha256(background),
        final_composite_sha256=pipeline._sha256(final),
        copy_provider_metadata={"provider": "openai", "model": "gpt-5.4", "fallback_used": False, "token_usage": {"input_tokens": 1, "output_tokens": 1}},
        vision_provider_metadata={"provider": "openai", "model": "gpt-5.4", "fallback_used": False, "token_usage": {"input_tokens": 1, "output_tokens": 1}},
        renderer_metadata={"rendered_slot_count": 1},
        vlm_result={
            "detected_text": ["headline"],
            "failure_reasons": ["CTA duplicated"],
            "recommended_action": "minor_revision",
            "product_obstruction_score": 0.1,
            "provider_metadata": {"provider": "openai", "model": "gpt-5.4", "fallback_used": False, "token_usage": {"input_tokens": 1, "output_tokens": 1}},
        },
    )

    checked = pipeline.validate_actual_result(result, SimpleNamespace(evaluated_image_sha256=pipeline._sha256(final)))

    assert checked.status == "failed"
    assert "vlm failure reasons present" in checked.failure_reasons
