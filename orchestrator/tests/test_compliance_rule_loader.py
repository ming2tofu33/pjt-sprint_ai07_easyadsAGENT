"""rule_loader.py — YAML 로딩 및 계약 검증 테스트."""


def test_load_legal_basis_returns_dict():
    from orchestrator.app.compliance.rule_loader import load_legal_basis

    basis = load_legal_basis()
    assert isinstance(basis, dict)
    assert len(basis) > 0


def test_legal_basis_has_expected_keys():
    from orchestrator.app.compliance.rule_loader import load_legal_basis

    basis = load_legal_basis()
    assert "KR-FOOD-AD-8" in basis
    assert "KR-FAIR-AD-3" in basis


def test_legal_basis_entry_has_law_name():
    from orchestrator.app.compliance.rule_loader import load_legal_basis

    basis = load_legal_basis()
    entry = basis["KR-FOOD-AD-8"]
    assert entry.law_name != ""
    assert entry.article != ""


def test_load_rules_returns_list():
    from orchestrator.app.compliance.rule_loader import load_rules

    rules = load_rules()
    assert isinstance(rules, list)
    assert len(rules) >= 3


def test_rules_have_required_fields():
    from orchestrator.app.compliance.rule_loader import load_rules
    from orchestrator.app.compliance.schemas import ComplianceRule

    for rule in load_rules():
        assert isinstance(rule, ComplianceRule)
        assert rule.rule_id != ""
        assert rule.severity in {"warn", "evidence_required", "block"}
        assert len(rule.patterns) > 0


def test_rules_legal_basis_ref_resolved():
    """legal_basis_ref key가 법령 메타데이터로 실제로 연결되는지 확인."""
    from orchestrator.app.compliance.rule_loader import load_rules

    for rule in load_rules():
        if rule.legal_basis_ref is not None:
            assert rule.legal_basis_ref.law_name != "", (
                f"{rule.rule_id}: legal_basis_ref.key가 legal_basis_kr_v1.yaml에 없음"
            )


def test_no_duplicate_rule_ids():
    from orchestrator.app.compliance.rule_loader import load_rules

    ids = [r.rule_id for r in load_rules()]
    assert len(ids) == len(set(ids)), f"중복 rule_id: {[x for x in ids if ids.count(x) > 1]}"


def test_yaml_contract_block_rules_have_examples():
    """block 규칙은 반드시 examples가 있어야 suggested_copy를 생성할 수 있다."""
    from orchestrator.app.compliance.rule_loader import load_rules

    for rule in load_rules():
        if rule.severity == "block":
            assert len(rule.examples) > 0, f"{rule.rule_id}: block 규칙에 examples 누락"


def test_yaml_contract_warn_rules_have_hitl_question():
    """warn 규칙은 사용자에게 맥락 확인 질문이 있어야 한다."""
    from orchestrator.app.compliance.rule_loader import load_rules

    for rule in load_rules():
        if rule.severity == "warn":
            assert rule.hitl_question, f"{rule.rule_id}: warn 규칙에 hitl_question 누락"


def test_yaml_contract_evidence_required_rules_have_requirements():
    """evidence_required 규칙은 어떤 근거를 제출해야 하는지 명시해야 한다."""
    from orchestrator.app.compliance.rule_loader import load_rules

    for rule in load_rules():
        if rule.severity == "evidence_required":
            assert len(rule.evidence_requirements) > 0, (
                f"{rule.rule_id}: evidence_required 규칙에 evidence_requirements 누락"
            )


def test_yaml_contract_all_rules_have_embedding_text():
    """RAG 확장 준비: embedding_text 없으면 벡터 인덱싱 불가."""
    from orchestrator.app.compliance.rule_loader import load_rules

    for rule in load_rules():
        assert rule.embedding_text.strip(), f"{rule.rule_id}: embedding_text 누락"
