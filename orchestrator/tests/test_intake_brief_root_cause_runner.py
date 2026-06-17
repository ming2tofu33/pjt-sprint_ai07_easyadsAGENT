import json

from orchestrator.app.api import chat as chat_api
from scripts import diagnose_intake_brief_flow as runner


def test_runner_writes_expected_artifacts_without_actual_llm_calls(tmp_path):
    summary = runner.run_diagnostic(tmp_path)

    assert summary["status"] == "completed"
    assert summary["case_count"] == 6
    assert summary["actual_llm_calls"] == 0

    expected_files = [
        "summary.json",
        "pipeline_inventory.json",
        "hardcoding_inventory.json",
        "case_manifest.json",
        "case_results.json",
        "field_lineage.json",
        "question_decisions.json",
        "state_transitions.json",
        "api_contract_comparison.json",
        "frontend_state_comparison.json",
        "root_cause_matrix.json",
        "recommended_work_breakdown.json",
        "report.md",
    ]
    for name in expected_files:
        path = tmp_path / name
        assert path.exists(), name
        if path.suffix == ".json":
            json.loads(path.read_text(encoding="utf-8"))


def test_runner_records_multiturn_business_answer_projection(tmp_path):
    runner.run_diagnostic(tmp_path)

    payload = json.loads((tmp_path / "case_results.json").read_text(encoding="utf-8"))
    r6 = next(item for item in payload if item["case_id"] == "R6")

    assert r6["chat_start"]["payload"]["type"] == "option_question"
    assert r6["multiturn"]["answer_status_code"] == 200
    assert r6["multiturn"]["answer_payload"]["context"]["businessType"] == "뷰티"


def test_empty_context_projection_uses_user_visible_defaults():
    projected = chat_api._context_from_state({"context": {}})

    assert projected.business_type == "카페"
    assert projected.item_or_service == "대표 메뉴"
    assert projected.promotion_goal == "광고 홍보"
