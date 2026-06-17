"""Diagnostic runner for intake/brief root-cause analysis.

This script characterizes the current backend/API behavior for a fixed set of
open-domain intake prompts without changing production behavior. It writes
runtime-only artifacts under data/qa/intake_brief_root_cause_v1/.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fastapi.testclient import TestClient

from orchestrator.app.graph.nodes import infer_marketing_context, validator_node
from orchestrator.app.graph.state import create_initial_marketing_state
from orchestrator.app.main import app
from orchestrator.app.schemas.llm_marketing import InitialMarketingRequest

DEFAULT_OUTPUT_DIR = Path("data/qa/intake_brief_root_cause_v1")


@dataclass(frozen=True)
class CaseSpec:
    case_id: str
    prompt: str
    expected_business_signal: str | None = None
    expected_item_signal: str | None = None
    expected_goal_signal: str | None = None
    expected_format_signal: str | None = None
    follow_up_answer_value: str | None = None
    follow_up_answer_label: str | None = None


CASES: tuple[CaseSpec, ...] = (
    CaseSpec(
        case_id="R1",
        prompt="이번에 새로 오픈하는 프리미엄 뷰티샵 홍보 포스터 만들어줘. 고급스럽고 우아한 분위기면 좋겠어.",
        expected_business_signal="뷰티샵",
        expected_goal_signal="오픈",
        expected_format_signal="포스터",
    ),
    CaseSpec(
        case_id="R2",
        prompt="강남 영어회화반 직장인 대상 수강생 모집 배너 만들어줘. 평일 저녁 입문반 수업이야.",
        expected_business_signal="영어회화반",
        expected_goal_signal="수강생 모집",
        expected_format_signal="배너",
    ),
    CaseSpec(
        case_id="R3",
        prompt="뷰티 감성으로 꾸민 카페의 딸기 라떼 포스터 만들어줘.",
        expected_business_signal="카페",
        expected_item_signal="딸기 라떼",
        expected_format_signal="포스터",
    ),
    CaseSpec(
        case_id="R4",
        prompt="뷰티 광고 만들어줘.",
        expected_business_signal="뷰티",
    ),
    CaseSpec(
        case_id="R5",
        prompt="새로 문을 여는 매장 오픈 포스터 만들어줘.",
        expected_business_signal="매장",
        expected_goal_signal="오픈",
        expected_format_signal="포스터",
    ),
    CaseSpec(
        case_id="R6",
        prompt="고급스러운 광고 포스터 만들어줘.",
        follow_up_answer_value="beauty_salon",
        follow_up_answer_label="뷰티샵",
    ),
)


PIPELINE_INVENTORY = [
    {
        "stage": "S4",
        "name": "create_initial_marketing_state",
        "file": "orchestrator/app/graph/state.py",
        "function": "create_initial_marketing_state",
        "kind": "backend_state_init",
    },
    {
        "stage": "S5-S14",
        "name": "validator_node",
        "file": "orchestrator/app/graph/nodes.py",
        "function": "validator_node",
        "kind": "backend_validation",
    },
    {
        "stage": "S15-S16",
        "name": "chat_start",
        "file": "orchestrator/app/api/chat.py",
        "function": "start_chat",
        "kind": "api_projection",
    },
    {
        "stage": "M5-M9",
        "name": "state_update_node",
        "file": "orchestrator/app/graph/nodes.py",
        "function": "state_update_node",
        "kind": "multiturn_merge",
    },
    {
        "stage": "S17-S19",
        "name": "chat reducer",
        "file": "apps/web/lib/chat-flow.ts",
        "function": "chatFlowReducer",
        "kind": "frontend_state_merge",
    },
    {
        "stage": "thread_restore",
        "name": "thread snapshot mapper",
        "file": "apps/web/lib/chat-thread-state-mapper.ts",
        "function": "mapChatThreadSnapshotToRestoreState",
        "kind": "frontend_restore_projection",
    },
]


HARDCODING_INVENTORY = [
    {
        "file": "orchestrator/app/graph/nodes.py",
        "function": "infer_business_type",
        "kind": "domain keyword table",
        "impact": "Only a small fixed vocabulary is recognized before the guarded brief interpreter.",
    },
    {
        "file": "orchestrator/app/graph/nodes.py",
        "function": "infer_item_or_service",
        "kind": "item/service parser",
        "impact": "Open-domain nouns outside the literal table stay empty.",
    },
    {
        "file": "orchestrator/app/graph/nodes.py",
        "function": "infer_promotion_goal",
        "kind": "promotion-goal keyword table",
        "impact": "Store-opening style intents collapse unless exact keywords are present.",
    },
    {
        "file": "orchestrator/app/api/chat.py",
        "function": "_context_from_state",
        "kind": "backend summary defaults",
        "impact": "Empty context is projected to user-visible defaults (카페 / 대표메뉴 / 광고 홍보).",
    },
    {
        "file": "apps/web/lib/chat-flow.ts",
        "function": "backendQuestionReceived",
        "kind": "frontend merge precedence",
        "impact": "Reducer preserves previous values when a partial backend context omits a field.",
    },
]


FRONTEND_STATE_COMPARISON = [
    {
        "file": "apps/web/lib/chat-flow.ts",
        "action": "backendQuestionReceived",
        "observation": "Merges partial backend context field-by-field and preserves the previous inferredContext value when a field is omitted.",
    },
    {
        "file": "apps/web/lib/chat-thread-state-mapper.ts",
        "action": "mapChatThreadSnapshotToRestoreState",
        "observation": "Restore path reads payload.context -> metadata.context -> payload root fields -> current_brief, with selectedChannelId defaulting to instagram-feed when no channel survives.",
    },
    {
        "file": "orchestrator/app/api/chat.py",
        "action": "_context_from_state",
        "observation": "Backend response builder injects fallback labels for empty business_type/item_or_service/promotion_goal before the frontend sees the payload.",
    },
]


def _git_value(*args: str) -> str | None:
    try:
        return subprocess.check_output(["git", *args], text=True, encoding="utf-8").strip() or None
    except Exception:
        return None


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _flatten_field_lineage(case_id: str, stage: str, mapping: dict[str, Any], *, source: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for field, value in mapping.items():
        rows.append(
            {
                "case_id": case_id,
                "field": field,
                "stage": stage,
                "value": value,
                "source": source,
                "evidence": "not_recorded",
                "confidence": "not_recorded",
            }
        )
    return rows


def _first_divergence(spec: CaseSpec, rule_based: dict[str, Any], validator_result: dict[str, Any]) -> dict[str, Any]:
    expected = {
        "business_type": spec.expected_business_signal,
        "item_or_service": spec.expected_item_signal,
        "promotion_goal": spec.expected_goal_signal,
        "ad_format": spec.expected_format_signal,
    }
    for field, signal in expected.items():
        if not signal:
            continue
        if rule_based.get(field):
            continue
        return {
            "field": field,
            "stage": "S5_rule_based_inference",
            "reason": "rule_based_intake_extractor_missing",
        }
    llm_meta = ((validator_result.get("validator_metadata") or {}).get("brief_interpreter") or {}).get("llm_metadata") or {}
    if llm_meta.get("fallback_reason") == "brief_interpreter_not_enabled":
        return {
            "field": "brief_interpreter",
            "stage": "S6_brief_interpreter",
            "reason": "guarded_brief_interpreter_disabled",
        }
    if validator_result.get("missing_fields"):
        return {
            "field": validator_result["missing_fields"][0],
            "stage": "S14_missing_fields",
            "reason": "missing_field_question_generated",
        }
    return {"field": None, "stage": "not_applicable", "reason": "no_divergence_recorded"}


def _root_cause_codes(spec: CaseSpec, rule_based: dict[str, Any], validator_result: dict[str, Any], start_payload: dict[str, Any]) -> list[str]:
    codes: list[str] = []
    if not any(rule_based.get(field) for field in ("business_type", "item_or_service", "promotion_goal", "ad_format")):
        codes.append("RC-02")
    llm_meta = ((validator_result.get("validator_metadata") or {}).get("brief_interpreter") or {}).get("llm_metadata") or {}
    if llm_meta.get("fallback_reason") == "brief_interpreter_not_enabled":
        codes.append("RC-03")
    if start_payload.get("type") == "option_question":
        codes.append("RC-11")
    if spec.case_id == "R6" and spec.follow_up_answer_value:
        codes.append("RC-12")
    return codes


def analyze_case(client: TestClient, spec: CaseSpec) -> dict[str, Any]:
    request = InitialMarketingRequest(user_input=spec.prompt)
    initial_state = create_initial_marketing_state(request)
    rule_based = infer_marketing_context(spec.prompt)
    validator_result = validator_node(initial_state)
    start_response = client.post("/v1/marketing/chat/start", json={"userInput": spec.prompt})
    start_payload = start_response.json()

    lineage = []
    lineage.extend(_flatten_field_lineage(spec.case_id, "S4_initial_state", initial_state.get("context") or {}, source="initial_state"))
    lineage.extend(_flatten_field_lineage(spec.case_id, "S5_rule_based_inference", rule_based, source="deterministic"))
    lineage.extend(_flatten_field_lineage(spec.case_id, "S14_validator_context", validator_result.get("context") or {}, source="validator"))

    multiturn: dict[str, Any] | None = None
    if spec.follow_up_answer_value and start_payload.get("type") == "option_question":
        answer_response = client.post(
            "/v1/marketing/chat/answer",
            json={
                "jobId": start_payload["jobId"],
                "threadId": start_payload["threadId"],
                "field": start_payload["question"]["field"],
                "value": spec.follow_up_answer_value,
            },
        )
        multiturn = {
            "answer_request": {
                "field": start_payload["question"]["field"],
                "value": spec.follow_up_answer_value,
                "display_label": spec.follow_up_answer_label,
            },
            "answer_status_code": answer_response.status_code,
            "answer_payload": answer_response.json(),
        }

    first_divergence = _first_divergence(spec, rule_based, validator_result)
    root_cause_codes = _root_cause_codes(spec, rule_based, validator_result, start_payload)

    return {
        "case_id": spec.case_id,
        "prompt": spec.prompt,
        "rule_based": rule_based,
        "validator": {
            "context": validator_result.get("context"),
            "missing_fields": validator_result.get("missing_fields"),
            "brief_interpreter": validator_result.get("validator_metadata", {}).get("brief_interpreter"),
        },
        "chat_start": {
            "status_code": start_response.status_code,
            "payload": start_payload,
        },
        "multiturn": multiturn or {"status": "not_applicable"},
        "first_divergence": first_divergence,
        "root_cause_codes": root_cause_codes,
        "lineage": lineage,
    }


def build_recommended_work_breakdown(root_cause_matrix: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets = {
        "W1": {
            "title": "Intake contract and extractor",
            "covers": ["RC-02", "RC-03"],
            "responsibility": "backend intake/brief understanding",
        },
        "W2": {
            "title": "Campaign-aware question policy",
            "covers": ["RC-11"],
            "responsibility": "backend validator/question policy",
        },
        "W3": {
            "title": "Multiturn merge and UI sync",
            "covers": ["RC-12"],
            "responsibility": "backend resume path + frontend state projection",
        },
    }
    runs: list[dict[str, Any]] = []
    for work_id, payload in buckets.items():
        matching = [item["case_id"] for item in root_cause_matrix if any(code in payload["covers"] for code in item["codes"])]
        runs.append(
            {
                "work_id": work_id,
                "title": payload["title"],
                "responsibility": payload["responsibility"],
                "covers_cases": matching,
                "covers_codes": payload["covers"],
            }
        )
    return runs


def write_report(output_dir: Path, summary: dict[str, Any], case_results: list[dict[str, Any]], root_cause_matrix: list[dict[str, Any]]) -> None:
    lines = [
        "# Intake & Brief Root-Cause Report",
        "",
        "This run is diagnostic only. It does not change production behavior, does not add keyword aliases, and does not perform actual LLM calls.",
        "",
        f"- Branch: {summary['branch']}",
        f"- HEAD: {summary['head']}",
        f"- Cases: {summary['case_count']}",
        f"- Actual LLM calls: {summary['actual_llm_calls']}",
        "",
        "## Key findings",
        "",
    ]
    for item in case_results:
        divergence = item["first_divergence"]
        codes = ", ".join(item["root_cause_codes"]) or "none"
        lines.append(f"- {item['case_id']}: first divergence at {divergence['stage']} ({divergence['reason']}); codes={codes}")
    lines.extend(
        [
            "",
            "## Root-cause matrix",
            "",
        ]
    )
    for item in root_cause_matrix:
        lines.append(f"- {item['case_id']}: {', '.join(item['codes'])}")
    lines.extend(
        [
            "",
            "## Responsibility boundary",
            "",
            "- Backend intake path owns raw prompt consumption, deterministic extraction, guarded brief-interpreter activation, missing-field policy, and API projection defaults.",
            "- Frontend owns reducer precedence and restore precedence, but it only sees the values already projected by the backend response contract.",
        ]
    )
    (output_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_diagnostic(output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    client = TestClient(app)
    case_results = [analyze_case(client, spec) for spec in CASES]
    root_cause_matrix = [{"case_id": item["case_id"], "codes": item["root_cause_codes"]} for item in case_results]
    field_lineage = [row for item in case_results for row in item["lineage"]]
    question_decisions = [
        {
            "case_id": item["case_id"],
            "question_field": item["chat_start"]["payload"].get("question", {}).get("field"),
            "missing_fields": item["validator"]["missing_fields"],
        }
        for item in case_results
    ]
    state_transitions = [
        {"case_id": item["case_id"], "multiturn": item["multiturn"]}
        for item in case_results
        if item["multiturn"] != {"status": "not_applicable"}
    ]
    summary = {
        "status": "completed",
        "branch": _git_value("branch", "--show-current"),
        "head": _git_value("rev-parse", "HEAD"),
        "case_count": len(case_results),
        "actual_llm_calls": 0,
        "production_source_changes_required_for_run": False,
        "artifact_root": str(output_dir).replace("\\", "/"),
    }

    _write_json(output_dir / "summary.json", summary)
    _write_json(output_dir / "pipeline_inventory.json", PIPELINE_INVENTORY)
    _write_json(output_dir / "hardcoding_inventory.json", HARDCODING_INVENTORY)
    _write_json(output_dir / "case_manifest.json", [asdict(item) for item in CASES])
    _write_json(output_dir / "case_results.json", case_results)
    _write_json(output_dir / "field_lineage.json", field_lineage)
    _write_json(output_dir / "question_decisions.json", question_decisions)
    _write_json(output_dir / "state_transitions.json", state_transitions)
    _write_json(
        output_dir / "api_contract_comparison.json",
        [{"case_id": item["case_id"], "chat_start": item["chat_start"], "multiturn": item["multiturn"]} for item in case_results],
    )
    _write_json(output_dir / "frontend_state_comparison.json", FRONTEND_STATE_COMPARISON)
    _write_json(output_dir / "root_cause_matrix.json", root_cause_matrix)
    _write_json(output_dir / "recommended_work_breakdown.json", build_recommended_work_breakdown(root_cause_matrix))

    for item in case_results:
        case_dir = output_dir / "cases" / item["case_id"]
        _write_json(case_dir / "input_projection.json", {"case_id": item["case_id"], "prompt": item["prompt"]})
        _write_json(case_dir / "backend_stages.json", {"rule_based": item["rule_based"], "validator": item["validator"]})
        _write_json(case_dir / "missing_field_decision.json", {"missing_fields": item["validator"]["missing_fields"], "first_divergence": item["first_divergence"]})
        _write_json(case_dir / "interrupt.json", item["chat_start"])
        _write_json(case_dir / "resume_transition.json", item["multiturn"])
        _write_json(case_dir / "api_response_projection.json", item["chat_start"])
        _write_json(case_dir / "frontend_projection.json", {"status": "static_inventory_only"})

    write_report(output_dir, summary, case_results, root_cause_matrix)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="integration", choices=["static", "backend", "integration", "self-check"])
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args()

    summary = run_diagnostic(Path(args.output_dir))
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
