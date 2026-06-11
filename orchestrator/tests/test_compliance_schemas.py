"""schemas.py import + 기본 인스턴스 생성 테스트."""


def test_compliance_finding_instantiates():
    from orchestrator.app.compliance.schemas import ComplianceFinding

    f = ComplianceFinding(
        finding_id="test-001",
        field="headline",
        severity="block",
        matched_text="독소 배출",
        reason="식품 의료 효능 주장",
    )
    assert f.finding_id == "test-001"
    assert f.detection_method == "pattern"
    assert f.confidence == 1.0
    assert f.rag_context is None


def test_copy_compliance_state_defaults():
    from orchestrator.app.compliance.schemas import CopyComplianceState

    state = CopyComplianceState(status="pass")
    assert state.findings == []
    assert state.publication_ready is True
    assert state.user_acknowledged_risk is False
