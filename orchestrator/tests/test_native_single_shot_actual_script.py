from argparse import Namespace
from pathlib import Path

from orchestrator.app.schemas.native_creative import NativeGenerationReview
from scripts import run_final_composite_quality_actual as runner


def test_native_actual_script_uses_single_image_no_renderer(monkeypatch, tmp_path):
    class Bundle:
        def __init__(self, user_text):
            self.user_text = user_text

        def model_dump(self):
            return {
                "schema_version": "input_evidence_bundle_v1",
                "input_mode": "text_only",
                "user_text": self.user_text,
                "explicit_product_mentions": ["된장찌개"],
                "explicit_user_facts": [],
                "visual_observations": [],
                "asset_metadata_evidence": [],
                "brand_profile_evidence": [],
                "reference_evidence": [],
                "creative_inferences": [],
                "input_conflicts": [],
                "unknown_fields": [],
                "unresolved_questions": [],
                "clarification_required": False,
                "manual_review_required": False,
                "overall_confidence": 0.9,
                "provider_metadata": {},
            }

    monkeypatch.setattr(runner, "run_input_evidence_normalizer", lambda request, runtime, case_dir: Bundle(request.user_text))
    monkeypatch.setattr(runner, "run_product_understanding", lambda request, runtime, evidence: {"schema_version": "product_understanding_v1", "product_name": "된장찌개", "normalized_product_type": "doenjang_jjigae", "broad_category": "food_and_beverage", "category_path": ["food_and_beverage", "doenjang_jjigae"], "verified_facts": [], "visual_observations": [], "permissible_inferences": [], "unknown_fields": [], "unsupported_claim_categories": [], "product_name_evidence_ids": [], "confidence": 0.9})

    def fake_brief(**kwargs):
        from orchestrator.app.schemas.native_creative import ApprovedNativeCopyBrief

        return ApprovedNativeCopyBrief(headline="고급진 된장찌개", supporting_copy="진한 구수함 한 그릇", language="korean", message_role="headline_plus_support", allowed_texts=["고급진 된장찌개", "진한 구수함 한 그릇"], forbidden_texts=[], max_text_blocks=2, max_total_characters=48, verified_evidence_ids=[], unsupported_claim_categories=[], compliance_status="approved", rejection_reasons=[])

    monkeypatch.setattr(runner, "generate_approved_native_copy_brief", fake_brief)

    def fake_generate(self, *, prompt_package, output_dir):
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / "final_native_image.png"
        from PIL import Image

        Image.new("RGB", (32, 32), "#ffffff").save(path)
        return {"provider": "openai", "model": "gpt-image-2", "image_call_count": 1, "edit_call_count": 0, "retry_call_count": 0, "image_path": path.as_posix(), "output_sha256": "abc", "width": 32, "height": 32, "format": "png", "prompt_sha256": prompt_package.prompt_sha256}

    monkeypatch.setattr(runner.GPTImage2ActualEngine, "generate_native_single_shot", fake_generate)
    monkeypatch.setattr(runner, "review_native_generation_with_gpt54", lambda image_path, package, model: (NativeGenerationReview(expected_texts=package.exact_allowed_texts, detected_texts=package.exact_allowed_texts, exact_text_match_score=1.0, unexpected_text_detected=False, missing_text_detected=False, product_match_score=0.9, product_obstruction_score=0.1, hierarchy_score=0.9, typography_quality_score=0.9, composition_score=0.9, commercial_viability_score=0.9, decision="accept", failure_reasons=[]), {"provider": "openai", "model": "gpt-5.4", "token_usage": {"input_tokens": 1, "output_tokens": 1}}))

    args = Namespace(native_case="restaurant_doenjang_jjigae_001", seed=62, copy_model="gpt-5.4", vlm_model="gpt-5.4")
    summary = runner.run_gpt_image2_native_single_shot(args=args, output_dir=tmp_path)

    run = summary["runs"][0]
    assert summary["status"] == "completed"
    assert summary["gpt_image_2_image_calls"] == 1
    assert summary["external_renderer_calls"] == 0
    assert summary["flux_calls"] == 0
    assert run["image_api_call_count"] == 1
    assert Path(run["final_image_path"]).exists()
