import pytest

from orchestrator.app.compliance.rule_loader import load_rules, validate_regex_pattern
from orchestrator.app.compliance.rewrite_strategy import StaticHintRewriter


@pytest.mark.parametrize("pattern", ["", "   "])
def test_empty_regex_pattern_is_rejected(pattern):
    with pytest.raises(ValueError, match="empty regex pattern"):
        validate_regex_pattern(pattern)


@pytest.mark.parametrize("pattern", [".*", "^"])
def test_zero_width_regex_pattern_is_rejected(pattern):
    with pytest.raises(ValueError, match="zero-width regex pattern"):
        validate_regex_pattern(pattern)


def test_invalid_regex_pattern_is_rejected():
    with pytest.raises(ValueError, match="invalid regex pattern"):
        validate_regex_pattern("^?")


@pytest.mark.parametrize("pattern", [r"최고\s*품질", r"best\s+quality", r"100%\s*보장"])
def test_non_empty_regex_pattern_is_accepted(pattern):
    assert validate_regex_pattern(pattern).search("최고 품질 best quality 100% 보장")


def test_static_rewrite_patterns_are_validated():
    StaticHintRewriter({})


def test_existing_compliance_rule_pack_passes_validation():
    rules = load_rules()

    assert rules
    assert all(rule.patterns for rule in rules)
