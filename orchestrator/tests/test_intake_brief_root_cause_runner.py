import json

from orchestrator.app.api import chat as chat_api
from scripts import diagnose_intake_brief_flow as runner


def test_runner_writes_expected_artifacts_without_actual_llm_calls(tmp_path):
    summary = runner.run_diagnostic(tmp_path)

    assert summary["status"] == "completed"
    assert summary["case_count"] == 7
    assert summary["actual_llm_calls"] == 0

    expected_files = [
        "summary.json",
        "pipeline_inventory.json",
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


def test_runner_splits_r4_and_replaces_r5_fixture(tmp_path):
    runner.run_diagnostic(tmp_path)

    manifest = json.loads((tmp_path / "case_manifest.json").read_text(encoding="utf-8"))
    case_ids = [item["case_id"] for item in manifest]

    assert "R4-A" in case_ids
    assert "R4-B" in case_ids
    r5 = next(item for item in manifest if item["case_id"] == "R5")
    assert "동네 서점" in r5["prompt"]


def test_runner_records_multiturn_business_answer_projection_without_false_rc12(tmp_path):
    runner.run_diagnostic(tmp_path)

    payload = json.loads((tmp_path / "case_results.json").read_text(encoding="utf-8"))
    r6 = next(item for item in payload if item["case_id"] == "R6")

    assert r6["chat_start"]["payload"]["type"] == "option_question"
    assert r6["multiturn"]["answer_status_code"] == 200
    assert r6["multiturn"]["answer_payload"]["context"]["businessType"] == "뷰티"
    assert "MULTITURN_BACKEND_UPDATE_CONFIRMED" in r6["root_cause_codes"]
    assert "RC-12" not in r6["root_cause_codes"]
    assert r6["frontend_projection"]["status"] == "executed"


def test_empty_context_projection_returns_null_contract():
    projected = chat_api._context_from_state({"context": {}})

    assert projected.business_type is None
    assert projected.item_or_service is None
    assert projected.promotion_goal is None
    assert projected.advertised_subject is None
    assert projected.campaign_intent is None
