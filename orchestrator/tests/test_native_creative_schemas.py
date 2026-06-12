from orchestrator.app.schemas.native_creative import CreativeExecutionPlan, NativeGenerationBudget


def test_native_schema_enforces_single_image_call():
    plan = CreativeExecutionPlan(
        image_engine="gpt_image_2",
        execution_lane="gpt_native_single_shot",
        copy_authoring_mode="gpt_structured",
        text_rendering_mode="native_typography",
        copy_precision="exact",
        max_text_blocks=2,
        native_text_allowed=True,
        reason_codes=[],
    )

    assert plan.image_call_limit == 1
    assert plan.automatic_edit_allowed is False
    assert plan.external_renderer_fallback_allowed is False


def test_native_budget_defaults_block_retry_and_external_renderer():
    budget = NativeGenerationBudget(request_fingerprint="abc")

    assert budget.max_image_calls == 1
    assert budget.allow_edit_retry is False
    assert budget.allow_generation_retry is False
    assert budget.allow_external_renderer is False
