import argparse

from orchestrator.app.graph.state import create_initial_marketing_state
from orchestrator.app.llm.copy_recommendation_lineage import (
    build_candidate_quality_metrics,
    build_copy_prompt_projection,
)
from orchestrator.app.llm.nodes.copy_candidates import copy_candidate_generation_node
from orchestrator.app.llm.settings import LLMSettings
from orchestrator.app.schemas.llm_marketing import (
    CopyCandidate,
    CopyCandidateListOutput,
    InitialMarketingRequest,
    MarketingContext,
)
from scripts import run_copy_recommendation_lineage_qa as lineage_runner


def _context() -> MarketingContext:
    return MarketingContext(
        business_type="education",
        item_or_service="English speaking class",
        promotion_goal="student_recruitment",
        target_persona="Gangnam office workers",
        time_context="weekday evening",
        contact_or_order_method="phone consultation",
        location_text="Gangnam Station",
        extra={"ad_format": "banner"},
    )


def _state() -> dict:
    return create_initial_marketing_state(
        InitialMarketingRequest(
            user_input="Recommend three banner copy options for an English speaking class.",
            copy_generation_mode="suggest_candidates",
            requested_ad_format="banner",
            user_plan="premium",
            context=_context(),
        )
    )


def _candidate(candidate_id: str, headline: str, subcopy: str, *, cta: str = "Call now", angle: str = "product_first", metadata=None) -> dict:
    return {
        "id": candidate_id,
        "headline": headline,
        "subcopy": subcopy,
        "cta": cta,
        "angle": angle,
        "metadata": metadata or {},
    }


def _mock_update(state: dict, *, fallback_used: bool, call_succeeded: bool) -> dict:
    raw_context = state["context"]
    context = raw_context if isinstance(raw_context, MarketingContext) else MarketingContext(**raw_context)
    source = "fallback" if fallback_used else "llm"
    copy_candidates = [
        _candidate(
            "copy_1",
            f"{context.item_or_service} for {context.target_persona}",
            f"{context.time_context} near {context.location_text}",
            cta=context.contact_or_order_method,
            metadata={"copy_quality_v2_score": {"warnings": []}},
        ),
        _candidate(
            "copy_2",
            f"Join {context.item_or_service}",
            f"{context.time_context} sessions available",
            cta=context.contact_or_order_method,
            angle="benefit_action_first",
            metadata={"copy_quality_v2_score": {"warnings": []}},
        ),
        _candidate(
            "copy_3",
            f"{context.item_or_service} at {context.location_text}",
            f"For {context.target_persona}",
            cta=context.contact_or_order_method,
            angle="emotion_first",
            metadata={"copy_quality_v2_score": {"warnings": []}},
        ),
    ]
    llm_raw = [] if fallback_used else copy_candidates
    fallback = copy_candidates if fallback_used else []
    lineage = {
        "provider": "openai",
        "selected_provider": "openai",
        "executed_provider": None if fallback_used else "openai",
        "model": "gpt-5.4-mini",
        "call_attempted": True,
        "call_succeeded": call_succeeded,
        "fallback_used": fallback_used,
        "fallback_reason": "api_call_disabled" if fallback_used else None,
        "copy_source_mode": source,
        "latency_ms": 0 if fallback_used else 321,
    }
    return {
        "status": "generating_copy_candidates",
        "copy_candidate_origin": source,
        "copy_candidates": copy_candidates,
        "copy_generation_trace": {
            "input_projection": {
                "item_or_service": context.item_or_service,
                "target_persona": context.target_persona,
                "time_context": context.time_context,
                "contact_or_order_method": context.contact_or_order_method,
                "location_text": context.location_text,
            },
            "prompt_projection": {"diversity_instruction_present": False},
            "lineage": lineage,
            "llm_raw_candidates": llm_raw,
            "fallback_candidates": fallback,
            "schema_parsed_candidates": copy_candidates,
            "validated_candidates": copy_candidates,
            "tone_normalized_candidates": copy_candidates,
            "ranked_candidates": copy_candidates,
            "compliance_annotated_candidates": copy_candidates,
            "api_candidates": copy_candidates,
        },
    }


def test_copy_candidate_generation_emits_stage_split_and_provider_lineage(monkeypatch):
    llm_output = CopyCandidateListOutput(
        candidates=[
            CopyCandidate(
                id="copy_1",
                headline="English speaking class for Gangnam office workers",
                subcopy="Weekday evening sessions near Gangnam Station",
                cta="Phone consultation",
            ),
            CopyCandidate(
                id="copy_2",
                headline="Join an English speaking class",
                subcopy="Weekday evening coaching",
                cta="Phone consultation",
            ),
            CopyCandidate(
                id="copy_3",
                headline="English speaking class at Gangnam Station",
                subcopy="For busy office workers",
                cta="Phone consultation",
            ),
        ],
        recommended_candidate_id="copy_1",
    )
    monkeypatch.setattr(
        "orchestrator.app.llm.nodes.copy_candidates.run_structured_node",
        lambda *args, **kwargs: (
            llm_output,
            {
                "fallback_used": False,
                "model_selection": {
                    "node_name": "copy_candidate_generation",
                    "provider": "openai",
                    "selected_model_class": "api_mini",
                    "model_name": "gpt-5.4-mini",
                },
                "llm_call_result": {
                    "success": True,
                    "provider": "openai",
                    "model_name": "gpt-5.4-mini",
                    "latency_ms": 321,
                    "token_usage": {"input_tokens": 12, "output_tokens": 34},
                    "metadata": {"provider_request_id": "req_123"},
                },
            },
        ),
    )

    update = copy_candidate_generation_node(_state())
    trace = update["copy_generation_trace"]

    assert trace["lineage"]["provider"] == "openai"
    assert trace["lineage"]["selected_provider"] == "openai"
    assert trace["lineage"]["executed_provider"] == "openai"
    assert trace["lineage"]["call_succeeded"] is True
    assert trace["lineage"]["fallback_used"] is False
    assert len(trace["llm_raw_candidates"]) == 3
    assert trace["fallback_candidates"] == []
    assert len(trace["schema_parsed_candidates"]) == 3
    assert len(trace["validated_candidates"]) == 3
    assert len(trace["tone_normalized_candidates"]) == 3
    assert len(trace["api_candidates"]) == 3


def test_prompt_projection_measures_diversity_instruction_from_prompt_text():
    projection_without_diversity = build_copy_prompt_projection(
        {"available_state": {"context": {}, "plan_policy": {"max_candidates": 3}}, "constraints": {}},
        {"context": {}, "current_brief": {"requested_ad_format": "banner"}},
        prompt="Write three banner copy options.",
    )
    projection_with_diversity = build_copy_prompt_projection(
        {"available_state": {"context": {}, "plan_policy": {"max_candidates": 3}}, "constraints": {}},
        {"context": {}, "current_brief": {"requested_ad_format": "banner"}},
        prompt="Return exactly three distinct candidates with a different message angle.",
    )

    assert projection_without_diversity["diversity_instruction_present"] is False
    assert projection_with_diversity["diversity_instruction_present"] is True


def test_candidate_quality_metrics_are_computed_from_candidates(monkeypatch):
    monkeypatch.setattr(
        "orchestrator.app.llm.copy_recommendation_lineage._is_generic_only_candidate",
        lambda text: "generic" in text,
    )
    candidates = [
        _candidate(
            "copy_1",
            "English speaking class for Gangnam office workers",
            "Weekday evening near Gangnam Station",
            cta="phone consultation",
            metadata={"copy_quality_v2_score": {"warnings": []}},
        ),
        _candidate(
            "copy_2",
            "English speaking class for Gangnam office workers",
            "Weekday evening near Gangnam Station",
            cta="phone consultation",
            metadata={"copy_quality_v2_score": {"warnings": []}},
        ),
        _candidate(
            "copy_3",
            "Generic lifestyle upgrade",
            "Ask about a luxury brunch event",
            cta="Reserve now",
            angle="emotion_first",
            metadata={"copy_quality_v2_score": {"warnings": ["unsupported_claim:luxury_brunch_event"]}},
        ),
    ]
    metrics = build_candidate_quality_metrics(
        candidates,
        input_projection={
            "item_or_service": "English speaking class",
            "target_persona": "Gangnam office workers",
            "time_context": "weekday evening",
            "contact_or_order_method": "phone consultation",
            "location_text": "Gangnam Station",
        },
        context=_context(),
    )

    assert metrics["candidate_count"] == 3
    assert metrics["explicit_fact_count"] == 5
    assert metrics["fact_hits_by_field"]["item_or_service"] == 2
    assert metrics["fact_hits_by_field"]["target_persona"] == 2
    assert metrics["fact_hits_by_field"]["time_context"] == 2
    assert metrics["fact_hits_by_field"]["contact_or_order_method"] == 2
    assert metrics["fact_hits_by_field"]["location_text"] == 2
    assert metrics["grounded_fact_coverage"] == 1.0
    assert metrics["generic_only_candidate_count"] == 1
    assert metrics["unsupported_claim_count"] == 1
    assert metrics["distinct_angle_count"] == 2
    assert metrics["duplicate_candidate_count"] == 1


def test_mock_lineage_runner_writes_expected_artifacts(tmp_path):
    args = argparse.Namespace(
        mode="mock",
        primary_runs=1,
        control_runs=1,
        max_actual_calls=5,
        confirm_paid_calls=False,
        env_file=None,
    )

    summary = lineage_runner.build_summary(args, env_report={"env_file_found": False}, output_dir=tmp_path)
    run_dir = tmp_path / "runs" / "language_academy_banner_1"

    assert summary["status"] == "mock_completed"
    assert summary["run_manifest"]["primary_runs"] == 1
    assert summary["run_manifest"]["control_runs"] == 1
    assert summary["run_manifest"]["attempted_actual_calls"] == 0
    assert summary["serialization_projection_comparison"][0]["comparison_type"] == "serialization_projection_comparison"
    assert (run_dir / "input_projection.json").exists()
    assert (run_dir / "llm_raw_candidates.json").exists()
    assert (run_dir / "fallback_candidates.json").exists()
    assert (run_dir / "quality_metrics.json").exists()


def test_actual_lineage_runner_blocks_without_required_env(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(
        lineage_runner,
        "get_llm_settings",
        lambda: LLMSettings(enable_api_call=False, default_provider="mock", llm_model="gpt-5.4-mini"),
    )
    args = argparse.Namespace(
        mode="actual",
        primary_runs=1,
        control_runs=1,
        max_actual_calls=5,
        confirm_paid_calls=True,
        env_file=None,
    )

    summary = lineage_runner.build_summary(args, env_report={"env_file_found": False}, output_dir=tmp_path)

    assert summary["status"] == "blocked"
    assert "OPENAI_API_KEY" in summary["missing_requirements"]
    assert "EASYADS_ENABLE_LLM_CALLS=true" in summary["missing_requirements"]
    assert "EASYADS_LLM_PROVIDER=openai" in summary["missing_requirements"]


def test_actual_fallback_is_not_marked_completed_and_preserves_stage_split(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        lineage_runner,
        "get_llm_settings",
        lambda: LLMSettings(enable_api_call=True, default_provider="openai", llm_model="gpt-5.4-mini"),
    )
    monkeypatch.setattr(
        lineage_runner,
        "copy_candidate_generation_node",
        lambda state: _mock_update(state, fallback_used=True, call_succeeded=False),
    )
    args = argparse.Namespace(
        mode="actual",
        primary_runs=1,
        control_runs=1,
        max_actual_calls=5,
        confirm_paid_calls=True,
        env_file=None,
    )

    summary = lineage_runner.build_summary(args, env_report={"env_file_found": False}, output_dir=tmp_path)

    assert summary["status"] == "failed"
    assert all(run["status"] == "completed_with_fallback" for run in summary["run_manifest"]["runs"])
    assert all(item["llm_raw_candidate_count"] == 0 for item in summary["stage_comparison"])
    assert all(item["fallback_candidate_count"] == 3 for item in summary["stage_comparison"])


def test_actual_runner_uses_split_budget_and_marks_real_success(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        lineage_runner,
        "get_llm_settings",
        lambda: LLMSettings(enable_api_call=True, default_provider="openai", llm_model="gpt-5.4-mini"),
    )
    monkeypatch.setattr(
        lineage_runner,
        "copy_candidate_generation_node",
        lambda state: _mock_update(state, fallback_used=False, call_succeeded=True),
    )
    args = argparse.Namespace(
        mode="actual",
        primary_runs=3,
        control_runs=1,
        max_actual_calls=5,
        confirm_paid_calls=True,
        env_file=None,
    )

    summary = lineage_runner.build_summary(args, env_report={"env_file_found": False}, output_dir=tmp_path)

    assert summary["status"] == "completed"
    assert summary["run_manifest"]["attempted_actual_calls"] == 5
    assert len(summary["run_manifest"]["runs"]) == 5
    assert all(run["status"] == "completed" for run in summary["run_manifest"]["runs"])
