"""PatternMatcher — scan() 및 aggregate_status() 테스트."""


def _matcher():
    from orchestrator.app.compliance.rule_loader import load_rules
    from orchestrator.app.compliance.rule_engine import PatternMatcher
    return PatternMatcher(load_rules())


# ── scan(): 매칭 기본 ─────────────────────────────────────────────────────────

def test_scan_returns_empty_for_safe_copy():
    findings = _matcher().scan(
        {"headline": "기분 좋은 딸기라떼 한 잔"},
        domains=["food", "general_ad"],
    )
    assert findings == []


def test_scan_detects_block_pattern_in_headline():
    findings = _matcher().scan(
        {"headline": "독소 배출에 도움을 주는 딸기라떼"},
        domains=["food"],
    )
    assert len(findings) == 1
    assert findings[0].severity == "block"
    assert findings[0].matched_text == "독소 배출"
    assert findings[0].field == "headline"


def test_scan_detects_warn_pattern():
    findings = _matcher().scan(
        {"headline": "디톡스 딸기라떼"},
        domains=["food"],
    )
    assert len(findings) >= 1
    assert any(f.severity == "warn" for f in findings)


def test_scan_detects_evidence_required_pattern():
    findings = _matcher().scan(
        {"headline": "국내 1위 카페"},
        domains=["general_ad"],
    )
    assert len(findings) >= 1
    assert any(f.severity == "evidence_required" for f in findings)


def test_scan_checks_subcopy_field():
    findings = _matcher().scan(
        {"headline": "안전한 헤드라인", "subcopy": "독소 배출 효과"},
        domains=["food"],
    )
    assert any(f.field == "sub_copy" for f in findings)


def test_scan_checks_cta_field():
    findings = _matcher().scan(
        {"headline": "안전한 문구", "cta": "독소 배출"},
        domains=["food"],
    )
    assert any(f.field == "cta" for f in findings)


def test_scan_only_applies_rules_matching_domain():
    """food 도메인 규칙은 general_ad만 요청하면 적용되지 않아야 한다."""
    findings = _matcher().scan(
        {"headline": "독소 배출 딸기라떼"},
        domains=["general_ad"],
    )
    food_block = [f for f in findings if f.rule_id == "KR-FOOD-MEDICAL-CLAIM-001"]
    assert food_block == []


def test_scan_finding_has_legal_basis_for_block_rule():
    findings = _matcher().scan(
        {"headline": "독소 배출 딸기라떼"},
        domains=["food"],
    )
    block_findings = [f for f in findings if f.severity == "block"]
    assert len(block_findings) > 0
    assert len(block_findings[0].legal_basis) > 0
    assert block_findings[0].legal_basis[0].law_name != ""


def test_scan_finding_has_rule_id():
    findings = _matcher().scan(
        {"headline": "독소 배출"},
        domains=["food"],
    )
    assert all(f.rule_id is not None for f in findings)


def test_scan_finding_ids_are_unique():
    findings = _matcher().scan(
        {"headline": "독소 배출", "subcopy": "면역력 강화"},
        domains=["food"],
    )
    ids = [f.finding_id for f in findings]
    assert len(ids) == len(set(ids)), "finding_id가 중복됨"


# ── aggregate_status() ────────────────────────────────────────────────────────

def test_aggregate_status_empty_returns_pass():
    from orchestrator.app.compliance.rule_engine import aggregate_status
    assert aggregate_status([]) == "pass"


def test_aggregate_status_warn_returns_warn():
    from orchestrator.app.compliance.rule_engine import aggregate_status
    from orchestrator.app.compliance.schemas import ComplianceFinding

    findings = [ComplianceFinding(finding_id="x", field="headline", severity="warn", matched_text="디톡스", reason="test")]
    assert aggregate_status(findings) == "warn"


def test_aggregate_status_block_wins_over_warn():
    from orchestrator.app.compliance.rule_engine import aggregate_status
    from orchestrator.app.compliance.schemas import ComplianceFinding

    findings = [
        ComplianceFinding(finding_id="a", field="headline", severity="warn", matched_text="디톡스", reason="w"),
        ComplianceFinding(finding_id="b", field="sub_copy", severity="block", matched_text="독소 배출", reason="b"),
    ]
    assert aggregate_status(findings) == "blocked"


def test_aggregate_status_evidence_required_wins_over_warn():
    from orchestrator.app.compliance.rule_engine import aggregate_status
    from orchestrator.app.compliance.schemas import ComplianceFinding

    findings = [
        ComplianceFinding(finding_id="a", field="headline", severity="warn", matched_text="디톡스", reason="w"),
        ComplianceFinding(finding_id="b", field="sub_copy", severity="evidence_required", matched_text="1위", reason="e"),
    ]
    assert aggregate_status(findings) == "evidence_required"


def test_aggregate_status_block_wins_over_evidence_required():
    from orchestrator.app.compliance.rule_engine import aggregate_status
    from orchestrator.app.compliance.schemas import ComplianceFinding

    findings = [
        ComplianceFinding(finding_id="a", field="headline", severity="evidence_required", matched_text="1위", reason="e"),
        ComplianceFinding(finding_id="b", field="sub_copy", severity="block", matched_text="독소 배출", reason="b"),
    ]
    assert aggregate_status(findings) == "blocked"
