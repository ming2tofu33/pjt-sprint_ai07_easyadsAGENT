"""YAML rule pack → ComplianceRule / LegalBasisRef 객체 변환."""

from __future__ import annotations

from pathlib import Path

import yaml

from orchestrator.app.compliance.schemas import ComplianceRule, LegalBasisRef

_DATA_DIR = Path(__file__).parent / "rules"
_RULES_PATH = _DATA_DIR / "rules_kr_v1.yaml"
_LEGAL_BASIS_PATH = _DATA_DIR / "legal_basis_kr_v1.yaml"


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
        rules.append(ComplianceRule(**entry, legal_basis_ref=ref))
    return rules
