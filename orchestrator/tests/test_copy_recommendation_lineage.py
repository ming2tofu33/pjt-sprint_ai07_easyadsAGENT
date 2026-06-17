import json
from pathlib import Path

from orchestrator.app.graph.state import create_initial_marketing_state
from orchestrator.app.llm.nodes.copy_candidates import copy_candidate_generation_node
from orchestrator.app.schemas.llm_marketing import CopyCandidate, CopyCandidateListOutput, InitialMarketingRequest, MarketingContext
from scripts import run_copy_recommendation_lineage_qa as lineage_runner


def _state() -> dict:
    return create_initial_marketing_state(
        InitialMarketingRequest(
            user_input="강남 직장인을 위한 영어 회화반 배너 문구 3개 추천해줘. 평일 저녁 수업, 소수 정원, 사전 전화 상담.",
            copy_generation_mode="suggest_candidates",
            requested_ad_format="banner",
            user_plan="premium",
            context=MarketingContext(
                business_type="education",
                item_or_service="영어 회화반",
                promotion_goal="student_recruitment",
                target_persona="강남 직장인",
                time_context="평일 저녁",
                contact_or_order_method="사전 전화 상담",
                extra={"ad_format": "banner"},
            ),
        )
    )


def test_copy_candidate_generation_emits_lineage_trace(monkeypatch):
    llm_output = CopyCandidateListOutput(
        candidates=[
            CopyCandidate(id="copy_1", headline="강남 직장인을 위한 영어 회화반", subcopy="평일 저녁 수업과 소수 정원", cta="전화 상담 문의"),
            CopyCandidate(id="copy_2", headline="퇴근 후 시작하는 영어 회화반", subcopy="사전 전화 상담 가능", cta="상담 신청"),
            CopyCandidate(id="copy_3", headline="소수 정원 영어 회화반 모집", subcopy="강남 직장인 대상 저녁 수업", cta="문의하기"),
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
    assert trace["lineage"]["model"] == "gpt-5.4-mini"
    assert trace["lineage"]["call_id"] == "req_123"
    assert trace["lineage"]["fallback_used"] is False
    assert len(trace["raw_candidates"]) == 3
    assert len(trace["parsed_candidates"]) == 3
    assert len(trace["final_candidates"]) == 3
    assert trace["prompt_projection"]["ad_format_present"] is True
    assert "raw_text" not in json.dumps(trace, ensure_ascii=False)


def test_mock_lineage_runner_writes_expected_artifacts(tmp_path):
    args = type(
        "Args",
        (),
        {
            "mode": "mock",
            "runs": 1,
            "max_actual_calls": 1,
            "confirm_paid_calls": False,
            "env_file": None,
        },
    )()

    summary = lineage_runner.build_summary(args, env_report={"env_file_found": False}, output_dir=tmp_path)
    run_dir = tmp_path / "runs" / "language_academy_banner_1"

    assert summary["status"] == "mock_completed"
    assert summary["llm_calls"]
    assert summary["frontend_comparison"][0]["matched"] is True
    assert (run_dir / "input_projection.json").exists()
    assert (run_dir / "lineage.json").exists()
    assert (run_dir / "frontend_projection.json").exists()


def test_actual_lineage_runner_blocks_without_required_env(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("EASYADS_ENABLE_LLM_CALLS", raising=False)
    monkeypatch.delenv("EASYADS_LLM_PROVIDER", raising=False)
    args = type(
        "Args",
        (),
        {
            "mode": "actual",
            "runs": 1,
            "max_actual_calls": 1,
            "confirm_paid_calls": True,
            "env_file": None,
        },
    )()

    summary = lineage_runner.build_summary(args, env_report={"env_file_found": False}, output_dir=tmp_path)

    assert summary["status"] == "blocked"
    assert "OPENAI_API_KEY" in summary["missing_requirements"]
    assert "EASYADS_ENABLE_LLM_CALLS=true" in summary["missing_requirements"]
