from types import SimpleNamespace

from PIL import Image

from scripts import run_final_composite_quality_actual as runner
from scripts import _actual_creative_pipeline as pipeline


def test_run_actual_creative_case_uses_shared_provider_flux_and_renderer(monkeypatch, tmp_path):
    calls = {"normalize": 0, "copy": 0, "vision": 0, "flux": 0, "renderer": 0}

    class Adapter:
        def normalize_input_evidence(self, *, request, model):
            calls["normalize"] += 1
            return {
                "input_mode": request.input_mode,
                "user_text": request.user_text,
                "user_intent": "product_promotion",
                "explicit_product_mentions": ["cheesecake"],
                "explicit_user_facts": [
                    {
                        "key": "product_name",
                        "value": "cheesecake",
                        "normalized_value": "cheesecake",
                        "source": "user_text",
                        "evidence_class": "verified_fact",
                        "confidence": 1.0,
                        "usable_for_copy": True,
                    }
                ],
                "visual_observations": [],
                "input_conflicts": [],
                "unknown_fields": [],
                "unresolved_questions": [],
                "clarification_required": False,
                "manual_review_required": False,
                "overall_confidence": 0.95,
                "provider_metadata": {
                    "normalizer": {"provider": "openai", "model": "gpt-5.4", "fallback_used": False, "token_usage": {"input_tokens": 10, "output_tokens": 5}}
                },
            }

        def generate_product_copy(self, *, request, evidence, model):
            calls["copy"] += 1
            assert evidence["schema_version"] == "input_evidence_bundle_v1"
            assert evidence["explicit_product_mentions"] == ["cheesecake"]
            return {
                "product_understanding": {
                    "product_name": "cheesecake",
                    "broad_category": "bakery",
                    "explicit_product_candidate": "cheesecake",
                    "normalized_product_candidate": "cheesecake",
                    "product_identity_confidence": 0.95,
                },
                "product_copy_context": {"goal": "brand_awareness", "brand_tone": "premium"},
                "copy_candidates": [{"id": "copy_1", "headline": "Creamy cheesecake", "subcopy": "A soft cafe dessert", "cta": "Taste today"}],
                "recommended_candidate_id": "copy_1",
                "selected_copy": {"headline": "Creamy cheesecake", "subcopy": "A soft cafe dessert", "cta": "Taste today"},
                "input_conflicts": [],
                "requires_manual_review": False,
                "provider_metadata": {"provider": "openai", "model": "gpt-5.4", "fallback_used": False, "token_usage": {"input_tokens": 10, "output_tokens": 5}},
            }

        def evaluate_final_composite(self, *, request, image_path, copy, model):
            calls["vision"] += 1
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
                "provider_metadata": {"provider": "openai", "model": "gpt-5.4", "fallback_used": False, "token_usage": {"input_tokens": 10, "output_tokens": 5}},
            }

    class Flux:
        def generate(self, request):
            calls["flux"] += 1
            path = tmp_path / "background.png"
            Image.new("RGB", (128, 128), "#ffffff").save(path)
            return SimpleNamespace(engine="flux2_klein_4b", image_paths=[str(path)], latency_ms=5, metadata={"model_name": "black-forest-labs/FLUX.2-klein-4B"})

    def fake_renderer(request, copy_output, background_path, case_dir):
        calls["renderer"] += 1
        final = case_dir / "final_composite.png"
        Image.new("RGB", (128, 128), "#000000").save(final)
        return {
            "render_result": {
                "final_image_path": str(final),
                "background_image_path": str(background_path),
                "rendered_slot_count": 1,
                "metadata": {"rendered_slot_count": 1},
            },
            "artifact_refs": [{"type": "final_image", "path": str(final)}],
            "final_image_path": str(final),
            "final_ocr_gate": {"ocr": {"detected_text": ["Creamy cheesecake"]}},
        }

    monkeypatch.setattr(pipeline, "execute_production_renderer", fake_renderer)
    monkeypatch.setattr(pipeline, "evaluate_final_composite", lambda state: SimpleNamespace(evaluated_image_sha256=pipeline._sha256(tmp_path / "case" / "final_composite.png")))
    request = pipeline.ActualCreativeInput(case_id="case", input_mode="text_only", user_text="cheesecake", output_dir=str(tmp_path))
    runtime = pipeline.ActualCreativeRuntime(openai_adapter=Adapter(), vision_adapter=Adapter(), flux_engine=Flux())

    result = pipeline.run_actual_creative_case(request, runtime)

    assert result.status == "completed"
    assert calls == {"normalize": 1, "copy": 1, "vision": 1, "flux": 1, "renderer": 1}
    assert result.mock_or_fixture_count == 0
    assert [item["variant_type"] for item in result.minimal_copy_candidates] == [
        "image_only",
        "headline_only",
        "headline_plus_support",
        "headline_plus_closing",
    ]
    assert [item["status"] for item in result.variant_results].count("selected") == 1
    assert any(item["status"] == "not_rendered" for item in result.variant_results)


def test_renderer_rejects_missing_product_context(tmp_path):
    background = tmp_path / "background.png"
    Image.new("RGB", (32, 32), "#ffffff").save(background)
    request = pipeline.ActualCreativeInput(case_id="case", input_mode="text_only", user_text="soap", output_dir=str(tmp_path))

    try:
        pipeline.execute_production_renderer(
            request,
            {
                "product_understanding": {},
                "product_copy_context": {},
                "selected_copy": {"headline": "Clean bar"},
            },
            background,
            tmp_path / "case",
        )
    except ValueError as exc:
        assert "product_context_incomplete" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("missing product context was accepted")


def test_validate_actual_result_rejects_missing_detected_text(tmp_path):
    background = tmp_path / "background.png"
    final = tmp_path / "final.png"
    Image.new("RGB", (32, 32), "#ffffff").save(background)
    Image.new("RGB", (32, 32), "#000000").save(final)
    result = pipeline.ActualCreativeResult(
        case_id="case",
        input_mode="text_only",
        status="completed",
        background_image_path=str(background),
        final_composite_path=str(final),
        background_sha256=pipeline._sha256(background),
        final_composite_sha256=pipeline._sha256(final),
        copy_provider_metadata={"provider": "openai", "model": "gpt-5.4", "fallback_used": False, "token_usage": {"input_tokens": 1, "output_tokens": 1}},
        flux_metadata={"engine": "flux2_klein_4b"},
        renderer_metadata={"rendered_slot_count": 1},
        vlm_result={"provider_metadata": {"provider": "openai", "model": "gpt-5.4", "fallback_used": False, "token_usage": {"input_tokens": 1, "output_tokens": 1}}},
    )

    checked = pipeline.validate_actual_result(result, SimpleNamespace(evaluated_image_sha256=pipeline._sha256(final)))

    assert checked.status == "failed"
    assert "ocr detected_text unavailable" in checked.failure_reasons


def test_validate_actual_result_allows_image_only_missing_copy_feedback(tmp_path):
    background = tmp_path / "background.png"
    Image.new("RGB", (32, 32), "#ffffff").save(background)
    result = pipeline.ActualCreativeResult(
        case_id="case",
        input_mode="image_only",
        status="completed",
        copy_presence_plan={"mode": "image_only"},
        background_image_path=str(background),
        final_composite_path=str(background),
        background_sha256=pipeline._sha256(background),
        final_composite_sha256=pipeline._sha256(background),
        copy_provider_metadata={"provider": "openai", "model": "gpt-5.4", "fallback_used": False, "token_usage": {"input_tokens": 1, "output_tokens": 1}},
        vision_provider_metadata={"provider": "openai", "model": "gpt-5.4", "fallback_used": False, "token_usage": {"input_tokens": 1, "output_tokens": 1}},
        renderer_metadata={"rendered_slot_count": 0},
        vlm_result={
            "detected_text": [],
            "failure_reasons": ["No advertising copy or branding present", "Product identity is not explicitly labeled", "Minimal commercial context"],
            "recommended_action": "add_copy",
            "product_obstruction_score": 0.1,
            "provider_metadata": {"provider": "openai", "model": "gpt-5.4", "fallback_used": False, "token_usage": {"input_tokens": 1, "output_tokens": 1}},
        },
    )

    checked = pipeline.validate_actual_result(result, SimpleNamespace(evaluated_image_sha256=pipeline._sha256(background)))

    assert checked.status == "completed"
    assert checked.failure_reasons == []


def test_validate_actual_result_ignores_false_positive_exact_text_failure(tmp_path):
    background = tmp_path / "background.png"
    final = tmp_path / "final.png"
    Image.new("RGB", (32, 32), "#ffffff").save(background)
    Image.new("RGB", (32, 32), "#000000").save(final)
    result = pipeline.ActualCreativeResult(
        case_id="case",
        input_mode="text_only",
        status="completed",
        selected_copy={"headline": "구수하게 끓여낸 한 그릇", "variant_type": "headline_only"},
        background_image_path=str(background),
        final_composite_path=str(final),
        background_sha256=pipeline._sha256(background),
        final_composite_sha256=pipeline._sha256(final),
        copy_provider_metadata={"provider": "openai", "model": "gpt-5.4", "fallback_used": False, "token_usage": {"input_tokens": 1, "output_tokens": 1}},
        flux_metadata={"engine": "flux2_klein_4b"},
        renderer_metadata={"rendered_slot_count": 1},
        vlm_result={
            "detected_text": ["구수하게 끓여낸 한 그릇"],
            "failure_reasons": ["Headline text does not exactly match expected text: detected '구수하게 끓여낸 한 그릇' vs expected '구수하게 끓여낸 한 그릇'."],
            "recommended_action": "approve",
            "product_obstruction_score": 0.1,
            "provider_metadata": {"provider": "openai", "model": "gpt-5.4", "fallback_used": False, "token_usage": {"input_tokens": 1, "output_tokens": 1}},
        },
    )

    checked = pipeline.validate_actual_result(result, SimpleNamespace(evaluated_image_sha256=pipeline._sha256(final)))

    assert checked.status == "completed"
    assert checked.failure_reasons == []


def test_call_budget_blocks_provider_before_call(tmp_path):
    budget = pipeline.ActualCallBudget(max_openai_calls=0)
    request = pipeline.ActualCreativeInput(case_id="case", input_mode="text_only", user_text="soap", output_dir=str(tmp_path))
    runtime = pipeline.ActualCreativeRuntime(openai_adapter=object(), call_budget=budget)

    try:
        pipeline.generate_grounded_copy(request, runtime, {})
    except RuntimeError as exc:
        assert "openai_call_budget_exceeded" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("budget overflow was accepted")


def test_canonical_smoke_runner_reuses_text_only_background(monkeypatch, tmp_path):
    calls = []

    def fake_run(request, runtime):
        calls.append(request)
        background = tmp_path / request.case_id / "background_flux2.png"
        final = tmp_path / request.case_id / "final_composite.png"
        background.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (32, 32), "#ffffff").save(background)
        Image.new("RGB", (32, 32), "#000000").save(final)
        return pipeline.ActualCreativeResult(
            case_id=request.case_id,
            input_mode=request.input_mode,
            status="completed",
            input_evidence={"source_provenance": request.source_provenance},
            background_image_path=str(background),
            final_composite_path=str(final),
            background_sha256=pipeline._sha256(background),
            final_composite_sha256=pipeline._sha256(final),
            copy_provider_metadata={"provider": "openai", "model": "gpt-5.4", "fallback_used": False, "token_usage": {"input_tokens": 1, "output_tokens": 1}},
            vlm_result={"provider_metadata": {"provider": "openai", "model": "gpt-5.4", "fallback_used": False, "token_usage": {"input_tokens": 1, "output_tokens": 1}}},
        )

    monkeypatch.setattr(runner, "_canonical_runtime", lambda args: object())
    monkeypatch.setattr(runner, "run_actual_creative_case", fake_run)
    args = SimpleNamespace(
        copy_model="gpt-5.4",
        vlm_model="gpt-5.4",
        max_openai_calls=6,
        max_flux_generations=1,
        source_image=None,
        reuse_text_only_background_as_source=True,
        resume=False,
    )

    summary = runner.run_canonical_smoke(args=args, output_dir=tmp_path)

    assert summary["status"] == "completed"
    assert [request.input_mode for request in calls] == ["text_only", "image_only", "text_and_image"]
    assert calls[1].source_provenance == "actual_generated_reuse"
    assert (tmp_path / "cross_input_comparison.json").exists()
    assert (tmp_path / "comparison_all_modes.png").exists()


def test_canonical_smoke_does_not_reuse_failed_text_only_background(monkeypatch, tmp_path):
    calls = []

    def fake_run(request, runtime):
        calls.append(request)
        background = tmp_path / request.case_id / "background_flux2.png"
        background.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (32, 32), "#ffffff").save(background)
        return pipeline.ActualCreativeResult(
            case_id=request.case_id,
            input_mode=request.input_mode,
            status="failed",
            background_image_path=str(background),
            failure_reasons=["failed"],
        )

    monkeypatch.setattr(runner, "_canonical_runtime", lambda args: object())
    monkeypatch.setattr(runner, "run_actual_creative_case", fake_run)
    args = SimpleNamespace(copy_model="gpt-5.4", vlm_model="gpt-5.4", max_openai_calls=6, max_flux_generations=1, source_image=None, reuse_text_only_background_as_source=True, resume=False)

    summary = runner.run_canonical_smoke(args=args, output_dir=tmp_path)

    assert summary["status"] == "failed"
    assert [request.input_mode for request in calls] == ["text_only"]
