from argparse import Namespace
from pathlib import Path

from orchestrator.app.schemas.native_creative import NativeCopyCandidate, NativeCopyScorecard, NativeCopyStrategyBundle, NativeCreativePreflightReview, NativeGenerationReview, PositioningRealizationPlan, ProductExpressionBasis
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
                "user_request_utterance": self.user_text,
                "campaign_intent": "product_promotion",
                "desired_positioning": ["premium", "refined"],
                "non_display_instruction_fragments": ["홍보하고 싶어"],
                "user_exact_display_copy": [],
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
    monkeypatch.setattr(
        runner,
        "run_product_understanding",
        lambda request, runtime, evidence: {
            "schema_version": "product_understanding_v1",
            "product_name": "된장찌개",
            "normalized_product_type": "doenjang_jjigae",
            "broad_category": "food_and_beverage",
            "category_path": ["food_and_beverage", "doenjang_jjigae"],
            "verified_facts": [],
            "visual_observations": [],
            "permissible_inferences": [],
            "unknown_fields": [],
            "unsupported_claim_categories": [],
            "product_name_evidence_ids": ["e1"],
            "confidence": 0.9,
        },
    )

    def fake_brief(**kwargs):
        from orchestrator.app.schemas.native_creative import ApprovedNativeCopyBrief

        return ApprovedNativeCopyBrief(
            headline="된장찌개",
            supporting_copy=None,
            language="korean",
            message_role="headline_only",
            allowed_texts=["된장찌개"],
            forbidden_texts=[],
            max_text_blocks=2,
            max_total_characters=48,
            verified_evidence_ids=["e1"],
            unsupported_claim_categories=[],
            compliance_status="approved",
            rejection_reasons=[],
            source_user_request="고급진 된장찌개를 홍보하고 싶어",
            non_display_instructions=["홍보하고 싶어"],
            product_identity="된장찌개",
            campaign_intent="product_promotion",
            desired_positioning=["premium", "refined"],
                transformation_performed=True,
                product_evidence_ids=["e1"],
                selected_candidate_id="c1",
                positioning_realization_plan=PositioningRealizationPlan(requested_positioning=["premium", "refined"]).model_dump(),
                candidate_scorecard={
                    "candidate_id": "c1",
                    "product_centeredness": 0.9,
                    "consumer_naturalness": 0.9,
                    "restraint": 0.9,
                    "native_typography_fit": 0.9,
                    "blocked": False,
                },
            )

    monkeypatch.setattr(runner, "generate_approved_native_copy_brief", fake_brief)
    monkeypatch.setattr(
        runner,
        "generate_native_copy_strategy_bundle",
        lambda **kwargs: NativeCopyStrategyBundle(
            product_expression_basis=ProductExpressionBasis(product_identity="된장찌개", selected_headline_basis_ids=["e1"]),
            positioning_plan=PositioningRealizationPlan(requested_positioning=["premium", "refined"]),
                candidates=[NativeCopyCandidate(candidate_id="c1", strategy="minimal_identity", headline="된장찌개", headline_basis_ids=["e1"], text_block_count=1, total_character_count=4)],
            scorecards=[
                NativeCopyScorecard(
                    candidate_id="c1",
                    product_identity_clarity=0.9,
                    product_centeredness=0.9,
                    sensory_specificity=0.8,
                    evidence_grounding=0.9,
                    consumer_naturalness=0.9,
                    positioning_alignment=0.8,
                    headline_strength=0.85,
                    support_complementarity=0.85,
                    restraint=0.9,
                    native_typography_fit=0.9,
                    direct_positioning_penalty=0,
                    generic_prestige_penalty=0,
                    abstract_language_penalty=0,
                    repetition_penalty=0,
                    unsupported_claim_penalty=0,
                    total_score=0.88,
                    blocked=False,
                    blocking_reasons=[],
                )
            ],
            recommended_candidate_id="c1",
        ),
    )
    monkeypatch.setattr(
        runner,
        "review_native_creative_preflight",
        lambda **kwargs: NativeCreativePreflightReview(
            decision="approved",
            copy_grounded=True,
            claims_supported=True,
            language_natural=True,
            generic_cta_absent=True,
            text_budget_valid=True,
            native_typography_suitable=True,
            product_visual_direction_valid=True,
            consumer_facing_copy=True,
            meta_instruction_absent=True,
            user_request_transformed=True,
            product_identity_clean=True,
            copy_relevance_score=0.9,
            headline_quality_score=0.85,
            positioning_alignment_score=0.8,
            failure_reasons=[],
            revision_instructions=[],
            provider_metadata={"provider": "openai", "model": "gpt-5.4", "token_usage": {"input_tokens": 1, "output_tokens": 1}},
        ),
    )

    def fake_generate(self, *, prompt_package, output_dir):
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / "final_native_image.png"
        from PIL import Image

        Image.new("RGB", (32, 32), "#ffffff").save(path)
        return {"provider": "openai", "model": "gpt-image-2", "image_call_count": 1, "edit_call_count": 0, "retry_call_count": 0, "image_path": path.as_posix(), "output_sha256": "abc", "width": 32, "height": 32, "format": "png", "prompt_sha256": prompt_package.prompt_sha256}

    monkeypatch.setattr(runner.GPTImage2ActualEngine, "generate_native_single_shot", fake_generate)
    monkeypatch.setattr(
        runner,
        "review_native_generation_with_gpt54",
        lambda image_path, package, model: (
            NativeGenerationReview(
                expected_texts=package.exact_allowed_texts,
                detected_texts=package.exact_allowed_texts,
                exact_text_match_score=1.0,
                unexpected_text_detected=False,
                missing_text_detected=False,
                product_match_score=0.9,
                product_obstruction_score=0.1,
                hierarchy_score=0.9,
                typography_quality_score=0.9,
                composition_score=0.9,
                commercial_viability_score=0.9,
                meta_instruction_exposed=False,
                consumer_facing_copy_score=0.9,
                copy_semantic_quality_score=0.9,
                decision="accept",
                failure_reasons=[],
            ),
            {"provider": "openai", "model": "gpt-5.4", "token_usage": {"input_tokens": 1, "output_tokens": 1}},
        ),
    )

    args = Namespace(native_case="restaurant_doenjang_jjigae_001", seed=62, copy_model="gpt-5.4", vlm_model="gpt-5.4", user_text="고급진 된장찌개를 홍보하고 싶어", placement="restaurant_poster", promotion_goal="product_promotion")
    summary = runner.run_gpt_image2_native_single_shot(args=args, output_dir=tmp_path)

    run = summary["runs"][0]
    assert summary["status"] == "completed"
    assert summary["gpt_image_2_image_calls"] == 1
    assert summary["external_renderer_calls"] == 0
    assert summary["flux_calls"] == 0
    assert run["image_api_call_count"] == 1
    assert Path(run["final_image_path"]).exists()
