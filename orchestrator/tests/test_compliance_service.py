"""ComplianceService end-to-end 테스트.

get_compliance_service()의 lru_cache 오염을 막기 위해
모든 테스트에서 _svc()로 직접 인스턴스를 생성한다.
"""


def _svc():
    from orchestrator.app.compliance.rule_loader import load_rules
    from orchestrator.app.compliance.rule_engine import PatternMatcher
    from orchestrator.app.compliance.rewrite_strategy import StaticHintRewriter
    from orchestrator.app.compliance.industry_classifier import IndustryClassifier
    from orchestrator.app.compliance.service import ComplianceService

    rules = load_rules()
    return ComplianceService(
        checker=PatternMatcher(rules),
        rewriter=StaticHintRewriter({r.rule_id: r for r in rules}),
        classifier=IndustryClassifier(),
    )


# ── status 반환값 ──────────────────────────────────────────────────────────────

def test_safe_copy_returns_pass():
    result = _svc().check_copy(
        {"headline": "기분 좋은 딸기라떼 한 잔", "subcopy": "오늘의 카페 타임"},
        business_type="cafe",
    )
    assert result.status == "pass"


def test_food_ambiguous_returns_warn():
    result = _svc().check_copy(
        {"headline": "디톡스 딸기라떼"},
        business_type="cafe",
    )
    assert result.status == "warn"


def test_food_medical_claim_returns_blocked():
    result = _svc().check_copy(
        {"headline": "독소 배출에 도움을 주는 딸기라떼"},
        business_type="cafe",
    )
    assert result.status == "blocked"


def test_superlative_returns_evidence_required():
    result = _svc().check_copy(
        {"headline": "국내 1위 카페"},
        business_type="cafe",
    )
    assert result.status == "evidence_required"


# ── publication_ready 불변 조건 ────────────────────────────────────────────────

def test_pass_is_publication_ready():
    result = _svc().check_copy({"headline": "기분 좋은 딸기라떼"}, business_type="cafe")
    assert result.publication_ready is True


def test_warn_is_publication_ready():
    """warn은 논블로킹이므로 게시 가능해야 한다."""
    result = _svc().check_copy({"headline": "디톡스 딸기라떼"}, business_type="cafe")
    assert result.status == "warn"
    assert result.publication_ready is True


def test_evidence_required_is_not_publication_ready():
    result = _svc().check_copy({"headline": "국내 1위 카페"}, business_type="cafe")
    assert result.publication_ready is False


def test_blocked_is_not_publication_ready():
    result = _svc().check_copy({"headline": "독소 배출 딸기라떼"}, business_type="cafe")
    assert result.publication_ready is False


# ── original_copy 보존 ─────────────────────────────────────────────────────────

def test_original_copy_is_stored_unchanged():
    original = {"headline": "독소 배출 딸기라떼", "subcopy": "좋은 한 잔"}
    result = _svc().check_copy(original, business_type="cafe")
    assert result.original_copy == {"headline": "독소 배출 딸기라떼", "subcopy": "좋은 한 잔"}


def test_original_copy_is_independent_from_input():
    """result.original_copy 수정이 입력 dict에 영향 없어야 한다."""
    original = {"headline": "독소 배출 딸기라떼"}
    result = _svc().check_copy(original, business_type="cafe")
    result.original_copy["headline"] = "변경됨"
    assert original["headline"] == "독소 배출 딸기라떼"


# ── suggested_copy ─────────────────────────────────────────────────────────────

def test_blocked_copy_has_suggested_copy():
    result = _svc().check_copy({"headline": "독소 배출 딸기라떼"}, business_type="cafe")
    assert result.suggested_copy is not None
    assert result.suggested_copy.get("headline") != "독소 배출 딸기라떼"


def test_pass_copy_has_no_suggested_copy():
    result = _svc().check_copy({"headline": "기분 좋은 딸기라떼"}, business_type="cafe")
    assert result.suggested_copy is None


# ── findings 내용 ──────────────────────────────────────────────────────────────

def test_findings_detection_method_is_pattern():
    result = _svc().check_copy({"headline": "독소 배출 딸기라떼"}, business_type="cafe")
    assert all(f.detection_method == "pattern" for f in result.findings)


def test_findings_confidence_is_1_for_pattern():
    result = _svc().check_copy({"headline": "독소 배출 딸기라떼"}, business_type="cafe")
    assert all(f.confidence == 1.0 for f in result.findings)


def test_findings_rag_context_is_none_in_v1():
    result = _svc().check_copy({"headline": "독소 배출 딸기라떼"}, business_type="cafe")
    assert all(f.rag_context is None for f in result.findings)


# ── 업종 fallback ─────────────────────────────────────────────────────────────

def test_unknown_business_type_uses_general_ad_rules():
    result = _svc().check_copy({"headline": "국내 1위 서비스"}, business_type="unknown_xyz")
    assert result.status == "evidence_required"


def test_none_business_type_uses_general_ad_rules():
    result = _svc().check_copy({"headline": "국내 1위 서비스"}, business_type=None)
    assert result.status == "evidence_required"


# ── get_compliance_service() singleton ────────────────────────────────────────

def test_get_compliance_service_returns_working_instance():
    from orchestrator.app.compliance.service import get_compliance_service

    svc = get_compliance_service()
    result = svc.check_copy({"headline": "기분 좋은 딸기라떼"}, business_type="cafe")
    assert result.status == "pass"


# ── fitness 도메인 ─────────────────────────────────────────────────────────────

def test_fitness_guarantee_is_evidence_required():
    result = _svc().check_copy(
        {"headline": "4주 만에 10kg 감량 보장"},
        business_type="fitness",
    )
    assert result.status == "evidence_required"


# ── medical 도메인 ─────────────────────────────────────────────────────────────

def test_medical_treatment_guarantee_is_blocked():
    result = _svc().check_copy(
        {"headline": "여드름 완치 보장"},
        business_type="hospital",
    )
    assert result.status == "blocked"


def test_medical_before_after_is_blocked():
    result = _svc().check_copy(
        {"headline": "Before & After로 확인하는 시술 효과"},
        business_type="hospital",
    )
    assert result.status == "blocked"


# ── cosmetic 도메인 ────────────────────────────────────────────────────────────

def test_cosmetic_medical_claim_is_blocked():
    result = _svc().check_copy(
        {"headline": "여드름 치료 100% 보장"},
        business_type="beauty_skincare",
    )
    assert result.status == "blocked"


# ── 도메인 격리: 다른 업종엔 medical 규칙 적용 안 됨 ─────────────────────────────

def test_medical_rule_does_not_apply_to_cafe():
    result = _svc().check_copy(
        {"headline": "여드름 완치 보장"},
        business_type="cafe",
    )
    medical_findings = [f for f in result.findings if f.rule_id and "MEDICAL" in f.rule_id]
    assert medical_findings == []
