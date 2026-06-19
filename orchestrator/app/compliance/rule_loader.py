"""YAML rule pack → ComplianceRule / LegalBasisRef 객체 변환."""

from __future__ import annotations

from pathlib import Path
import re

import yaml

from orchestrator.app.compliance.schemas import ComplianceRule, LegalBasisRef

_DATA_DIR = Path(__file__).parent / "rules"
_RULES_PATH = _DATA_DIR / "rules_kr_v1.yaml"
_LEGAL_BASIS_PATH = _DATA_DIR / "legal_basis_kr_v1.yaml"


def validate_regex_pattern(pattern: str) -> re.Pattern[str]:
    if not isinstance(pattern, str):
        raise ValueError("regex pattern must be a string")
    if not pattern.strip():
        raise ValueError("empty regex pattern is not allowed")
    try:
        compiled = re.compile(pattern)
    except re.error as exc:
        raise ValueError(f"invalid regex pattern: {pattern!r}") from exc
    if compiled.match("") is not None:
        raise ValueError(f"zero-width regex pattern is not allowed: {pattern!r}")
    return compiled


def load_legal_basis(path: Path = _LEGAL_BASIS_PATH) -> dict[str, LegalBasisRef]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {
        key: LegalBasisRef(key=key, **{k: v for k, v in entry.items() if v is not None})
        for key, entry in (raw.get("legal_basis") or {}).items()
    }


def load_rules(path: Path = _RULES_PATH) -> list[ComplianceRule]:
    legal_basis_map = load_legal_basis()
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    rules = []
    for entry in raw.get("rules") or []:
        entry = dict(entry)
        ref_raw = entry.pop("legal_basis_ref", None) or {}
        ref_key = ref_raw.get("key") if isinstance(ref_raw, dict) else None
        ref = legal_basis_map.get(ref_key) if ref_key else None
        rule = ComplianceRule(**entry, legal_basis_ref=ref)
        for pattern in rule.patterns:
            validate_regex_pattern(pattern)
        rules.append(rule)
    return rules
