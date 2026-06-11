"""Phase 5: ComplianceService.get_rules_for_domains + metadata compliance 주입 테스트."""
from orchestrator.app.compliance.service import ComplianceService
from orchestrator.app.compliance.rule_engine import PatternMatcher
from orchestrator.app.compliance.rule_loader import load_rules
from orchestrator.app.compliance.rewrite_strategy import StaticHintRewriter
from orchestrator.app.compliance.industry_classifier import IndustryClassifier


def _svc() -> ComplianceService:
    rules = load_rules()
    return ComplianceService(
        checker=PatternMatcher(rules),
        rewriter=StaticHintRewriter({r.rule_id: r for r in rules}),
        classifier=IndustryClassifier(),
    )


# ── get_rules_for_domains ────────────────────────────────────

def test_get_rules_for_domains_returns_food_rules():
    svc = _svc()
    food_rules = svc.get_rules_for_domains(["food"])
    assert len(food_rules) > 0
    assert all(r.domain == "food" for r in food_rules)


def test_get_rules_for_domains_returns_cosmetic_rules():
    svc = _svc()
    rules = svc.get_rules_for_domains(["cosmetic"])
    assert len(rules) > 0
    assert all(r.domain == "cosmetic" for r in rules)


def test_get_rules_for_domains_empty_returns_empty():
    svc = _svc()
    rules = svc.get_rules_for_domains([])
    assert rules == []


def test_get_rules_for_domains_multi_domain():
    svc = _svc()
    rules = svc.get_rules_for_domains(["food", "general_ad"])
    domains = {r.domain for r in rules}
    assert "food" in domains
    assert "general_ad" in domains


# ── build_copy_generation_metadata compliance 주입 ─────────

from orchestrator.app.llm.metadata_builders import build_copy_generation_metadata


def test_build_copy_generation_metadata_has_compliance_for_food():
    state = {"context": {"business_type": "cafe", "item_or_service": "딸기라떼"}}
    metadata = build_copy_generation_metadata(state)
    constraints = metadata["constraints"]
    assert "compliance" in constraints


def test_compliance_blocked_terms_for_food_business():
    state = {"context": {"business_type": "cafe"}}
    metadata = build_copy_generation_metadata(state)
    compliance = metadata["constraints"]["compliance"]
    blocked = compliance["blocked_terms"]
    assert any(term in blocked for term in ["독소 배출", "붓기 제거", "체지방 감소"])


def test_compliance_domains_for_beauty_skincare():
    state = {"context": {"business_type": "beauty_skincare"}}
    metadata = build_copy_generation_metadata(state)
    compliance = metadata["constraints"]["compliance"]
    assert "cosmetic" in compliance["domains"]
    assert len(compliance["blocked_terms"]) > 0


def test_no_compliance_without_business_type():
    state = {"context": {}}
    metadata = build_copy_generation_metadata(state)
    compliance = metadata["constraints"].get("compliance")
    assert compliance is None or compliance == {}


def test_compliance_has_safe_direction():
    state = {"context": {"business_type": "cafe"}}
    metadata = build_copy_generation_metadata(state)
    compliance = metadata["constraints"]["compliance"]
    assert isinstance(compliance["safe_direction"], list)
    assert len(compliance["safe_direction"]) > 0


def test_existing_constraints_not_overwritten():
    state = {
        "context": {"business_type": "cafe"},
        "tone_binding_output": {"forbidden_claims": ["특허 성분"], "channel_copy_rules": [], "copy_constraints": []},
    }
    metadata = build_copy_generation_metadata(state)
    constraints = metadata["constraints"]
    assert "특허 성분" in constraints["forbidden_claims"]
    assert "compliance" in constraints
