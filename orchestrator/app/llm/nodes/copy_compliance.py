"""Compliance gate 노드 구현.

copy_compliance_gate_node: marketing_copy를 검사. marketing_copy를 직접 수정하지 않는다.
copy_compliance_interrupt_node: evidence_required/blocked 시 HITL interrupt 발생.
copy_compliance_resolution_node: 사용자 결정을 처리해 다음 노드를 결정한다.
"""

from __future__ import annotations

from typing import Any

from langgraph.types import interrupt

from orchestrator.app.compliance.service import get_compliance_service
from orchestrator.app.graph.state import MarketingState, context_to_model


def copy_compliance_gate_node(state: MarketingState) -> dict[str, Any]:
    copy = dict(state.get("marketing_copy") or {})
    business_type = context_to_model(state.get("context")).business_type
    svc = get_compliance_service()
    result = svc.check_copy(copy, business_type)
    return {
        "copy_compliance_gate": result.model_dump(),
        "copy_compliance_status": result.status,
        "copy_compliance_publication_ready": result.publication_ready,
        "status": "copy_compliance_checked",
    }


def copy_compliance_interrupt_node(state: MarketingState) -> dict[str, Any]:
    gate = dict(state.get("copy_compliance_gate") or {})
    findings = gate.get("findings") or []
    status = state.get("copy_compliance_status") or "evidence_required"

    actions = [
        {"id": "use_suggestion",      "label": "안전한 문구로 수정",          "available": True},
        {"id": "edit_manually",       "label": "직접 수정",                   "available": True},
        {"id": "submit_claim",        "label": "근거자료 제출",               "available": True},
        {"id": "keep_original_draft", "label": "위험을 인지하고 초안으로 계속", "available": status != "blocked"},
        {"id": "cancel",              "label": "생성 취소",                   "available": True},
    ]
    payload = {
        "type": "copy_compliance_review",
        "job_id": state["job_id"],
        "thread_id": state["thread_id"],
        "status": status,
        "summary": _build_summary(findings),
        "findings": _serialize_findings(findings),
        "actions": actions,
    }
    resume_payload = interrupt(payload)
    return {
        "copy_compliance_gate": {**gate, "interrupt_payload": payload},
        "copy_compliance_resolution": resume_payload,
        "status": "waiting_compliance_decision",
    }


def copy_compliance_resolution_node(state: MarketingState) -> dict[str, Any]:
    resolution = dict(state.get("copy_compliance_resolution") or {})
    decision = resolution.get("action") or resolution.get("user_decision")
    gate = dict(state.get("copy_compliance_gate") or {})

    if decision == "use_suggestion":
        suggested = gate.get("suggested_copy")
        if suggested:
            return {
                "marketing_copy": suggested,
                "copy_compliance_gate": {**gate, "user_decision": "use_suggestion", "status": "rewritten_by_user_choice", "publication_ready": True},
                "copy_compliance_status": "rewritten_by_user_choice",
                "copy_compliance_publication_ready": True,
            }

    if decision == "submit_claim":
        evidence = resolution.get("evidence") or {}
        submitted = list(gate.get("evidence_submitted") or [])
        submitted.append(evidence)
        return {
            "copy_compliance_gate": {**gate, "user_decision": "submit_claim", "status": "manual_review_required", "publication_ready": False, "evidence_submitted": submitted},
            "copy_compliance_status": "manual_review_required",
            "copy_compliance_publication_ready": False,
        }

    if decision == "keep_original_draft":
        return {
            "copy_compliance_gate": {**gate, "user_decision": "keep_original_draft", "user_acknowledged_risk": True, "status": "manual_review_required", "publication_ready": False},
            "copy_compliance_status": "manual_review_required",
            "copy_compliance_publication_ready": False,
        }

    if decision == "cancel":
        return {
            "copy_compliance_gate": {
                **gate,
                "user_decision": "cancel",
                "status": "cancelled_by_user",
                "publication_ready": False,
            },
            "copy_compliance_status": "cancelled_by_user",
            "copy_compliance_publication_ready": False,
            "status": "failed",
            "error_info": {
                "error_code": "generation_job_cancelled_by_user",
                "message": "사용자가 광고 규제 검토 단계에서 생성을 취소했습니다.",
            },
            "error_message": "사용자가 광고 규제 검토 단계에서 생성을 취소했습니다.",
        }

    # edit_manually: router가 custom_copy_input으로 분기
    return {
        "copy_compliance_gate": {**gate, "user_decision": "edit_manually"},
    }


def input_compliance_precheck_node(state: MarketingState) -> dict[str, Any]:
    """사용자 입력에서 위험 intent를 사전 감지한다.
    흐름을 절대 멈추지 않는다. 힌트만 state에 저장한다."""
    user_input = state.get("user_input") or ""
    business_type = context_to_model(state.get("context")).business_type
    svc = get_compliance_service()
    result = svc.check_copy({"headline": user_input}, business_type)

    if result.status == "pass":
        return {"input_compliance_risk": None, "status": "input_compliance_prechecked"}

    risk = {
        "detected": True,
        "status": result.status,
        "domains": list({_domain_from_rule_id(f.rule_id) for f in result.findings if f.rule_id}),
        "flagged_terms": [f.matched_text for f in result.findings],
        "safe_direction": _build_safe_direction_hint(result.findings),
    }
    return {"input_compliance_risk": risk, "status": "input_compliance_prechecked"}


def _build_safe_direction_hint(findings: list) -> str:
    """findings: ComplianceFinding Pydantic 객체 또는 dict 모두 지원."""
    domains: set[str] = set()
    for f in findings:
        rule_id = f.rule_id if hasattr(f, "rule_id") else (f.get("rule_id") if isinstance(f, dict) else "")
        if rule_id:
            domains.add(_domain_from_rule_id(rule_id))
    if "food" in domains:
        return "맛·향·분위기·재료·경험 중심으로 생성합니다."
    if "medical" in domains or "cosmetic" in domains:
        return "상담·경험·케어 과정 중심으로 생성합니다."
    return "표현을 완화해 생성합니다."


def _domain_from_rule_id(rule_id: str) -> str:
    parts = rule_id.split("-")
    return parts[1].lower() if len(parts) >= 2 else "general"


def _build_summary(findings: list[dict[str, Any]]) -> str:
    count = len(findings)
    if count == 0:
        return "광고 규제 검토를 통과했습니다."
    return f"광고 규제 위험 표현 {count}개가 발견되었습니다."


def _serialize_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for f in findings:
        legal_basis = f.get("legal_basis") or []
        result.append({
            "finding_id": f.get("finding_id"),
            "field": f.get("field"),
            "matched_text": f.get("matched_text"),
            "severity": f.get("severity"),
            "detection_method": f.get("detection_method", "pattern"),
            "confidence": f.get("confidence", 1.0),
            "reason": f.get("reason"),
            "legal_basis": [
                {
                    "key": b.get("key"),
                    "law_name": b.get("law_name"),
                    "article": b.get("article"),
                    "summary": b.get("summary"),
                    "chunk_id": b.get("chunk_id"),
                }
                for b in legal_basis
            ],
            "suggested_text": f.get("suggested_text"),
            "evidence_requirements": f.get("evidence_requirements") or [],
            "hitl_question": f.get("hitl_question"),
            "rag_context": f.get("rag_context"),
        })
    return result
