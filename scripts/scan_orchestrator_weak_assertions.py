from __future__ import annotations

import argparse
import ast
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data/test_optimization/assertion_quality_v1"
PROTECTED_TOKENS = (
    "secret",
    "raw_response",
    "local_path",
    "internal uuid",
    "rollback",
    "fail-closed",
    "at-most-once",
)
OWNER_HINTS = {
    "archive": "api",
    "chat": "api",
    "generation_outputs": "repository",
    "graph": "graph",
    "marketing_graph": "graph",
    "r2": "storage",
    "storage": "storage",
    "validation": "policy",
    "copywriting": "policy",
}
DECISION_OVERRIDES: dict[str, dict[str, Any]] = {
    "orchestrator/tests/test_archive.py::test_archive_detail_user_isolation|manual_exception|try/assert False/except": {
        "decision": "strengthened",
        "decision_source": "manual_override",
        "reason": "manual exception pattern replaced with pytest.raises",
        "replacement_test_id": "orchestrator/tests/test_archive.py::test_archive_detail_user_isolation",
        "replacement_contract_id": "archive:user-isolation-not-found",
        "branch_evidence_pending": True,
        "mutation_evidence_pending": True,
    },
    "orchestrator/tests/test_chat_threads.py::test_chat_start_auto_pilot_returns_brief_ready_response|truthiness|assert payload['brief']['copy']": {
        "decision": "strengthened",
        "decision_source": "manual_override",
        "reason": "copy truthiness replaced by non-empty string contract",
        "replacement_test_id": "orchestrator/tests/test_chat_threads.py::test_chat_start_auto_pilot_returns_brief_ready_response",
        "replacement_contract_id": "chat:brief-copy-present",
        "branch_evidence_pending": True,
        "mutation_evidence_pending": True,
    },
    "orchestrator/tests/test_chat_threads.py::test_photo_start_auto_pilot_returns_brief_ready_response|truthiness|assert payload['brief']['copy']": {
        "decision": "strengthened",
        "decision_source": "manual_override",
        "reason": "copy truthiness replaced by non-empty string contract",
        "replacement_test_id": "orchestrator/tests/test_chat_threads.py::test_photo_start_auto_pilot_returns_brief_ready_response",
        "replacement_contract_id": "chat:brief-copy-present",
        "branch_evidence_pending": True,
        "mutation_evidence_pending": True,
    },
    "orchestrator/tests/test_chat_threads.py::test_chat_state_snapshot_repo_requires_connection|broad_exception|with pytest.raises(Exception)": {
        "decision": "kept",
        "decision_source": "manual_override",
        "reason": "DB-disabled integration guard has no stable domain exception contract yet",
        "review_required": True,
        "branch_evidence_pending": True,
        "mutation_evidence_pending": True,
    },
    "orchestrator/tests/test_marketing_graph.py::test_marketing_graph_runs_to_mock_t2i_when_context_is_complete|truthiness|assert result[key]": {
        "decision": "strengthened",
        "decision_source": "manual_override",
        "reason": "graph state contract partially strengthened in-node",
        "replacement_test_id": "orchestrator/tests/test_marketing_graph.py::test_marketing_graph_runs_to_mock_t2i_when_context_is_complete",
        "replacement_contract_id": "graph:t2i-result-contract",
        "branch_evidence_pending": True,
        "mutation_evidence_pending": True,
    },
    "orchestrator/tests/test_marketing_graph.py::test_marketing_graph_resume_continues_to_mock_t2i|truthiness|assert resumed['t2i_result']['image_paths']": {
        "decision": "strengthened",
        "decision_source": "manual_override",
        "reason": "resume path now checks concrete png output contract",
        "replacement_test_id": "orchestrator/tests/test_marketing_graph.py::test_marketing_graph_resume_continues_to_mock_t2i",
        "replacement_contract_id": "graph:resume-output-path",
        "branch_evidence_pending": True,
        "mutation_evidence_pending": True,
    },
}
CONVERTED_CONTRACT_OVERRIDES = [
    {
        "node_id": "orchestrator/tests/test_generation_outputs_repository_v1.py::test_generation_output_create_get_list_count",
        "replacement_test_id": "orchestrator/tests/test_generation_outputs_repository_v1.py::test_generation_output_create_get_list_count",
        "replacement_contract_id": "generation-output-repository:sql-params",
        "reason": "repository mock passthrough converted to SQL clause/params contract coverage",
    },
    {
        "node_id": "orchestrator/tests/test_generation_outputs_service_v1.py::test_select_final_generation_output_transaction",
        "replacement_test_id": "orchestrator/tests/test_generation_outputs_service_v1.py::test_select_final_generation_output_transaction",
        "replacement_contract_id": "generation-output-service:transaction-forwarding",
        "reason": "service mock passthrough converted to transaction-forwarding contract",
    },
    {
        "node_id": "orchestrator/tests/test_archive.py::test_archive_detail_user_isolation",
        "replacement_test_id": "orchestrator/tests/test_archive.py::test_archive_detail_user_isolation",
        "replacement_contract_id": "archive:user-isolation-not-found",
        "reason": "manual exception handling converted to explicit not-found contract",
    },
    {
        "node_id": "orchestrator/tests/test_r2_storage.py::test_upload_file_to_r2_returns_signed_urls",
        "replacement_test_id": "orchestrator/tests/test_r2_storage.py::test_upload_file_to_r2_returns_signed_urls",
        "replacement_contract_id": "r2:signed-url-expiry-contract",
        "reason": "signed-url presence converted to ISO timestamp and future-expiry contract",
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tests-root", default="orchestrator/tests")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR.relative_to(REPO_ROOT)).replace("\\", "/"))
    return parser.parse_args()


class ScanVisitor(ast.NodeVisitor):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.function: str | None = None
        self.findings: list[dict[str, Any]] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_test_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_test_function(node)

    def _visit_test_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        prev = self.function
        self.function = node.name
        self.generic_visit(node)
        self.function = prev

    def visit_Assert(self, node: ast.Assert) -> None:
        if self.function is None:
            return
        text = ast.unparse(node.test)
        pattern = detect_assert_pattern(node.test, text)
        if pattern:
            self.findings.append(build_finding(self.path, self.function, node.lineno, pattern, f"assert {text}"))
        self.generic_visit(node)

    def visit_With(self, node: ast.With) -> None:
        if self.function is None:
            return
        for item in node.items:
            expr = item.context_expr
            if isinstance(expr, ast.Call) and ast.unparse(expr.func) == "pytest.raises":
                if expr.args and ast.unparse(expr.args[0]) == "Exception":
                    self.findings.append(
                        build_finding(self.path, self.function, node.lineno, "broad_exception", "with pytest.raises(Exception)")
                    )
        self.generic_visit(node)

    def visit_Try(self, node: ast.Try) -> None:
        if self.function is None:
            return
        if any(isinstance(stmt, ast.Assert) and ast.unparse(stmt.test) == "False" for stmt in node.body):
            self.findings.append(build_finding(self.path, self.function, node.lineno, "manual_exception", "try/assert False/except"))
        self.generic_visit(node)


def detect_assert_pattern(test: ast.AST, text: str) -> str | None:
    normalized = text.replace(" ", "")
    if normalized.endswith("isnotNone"):
        return "not_none"
    if "len(" in text and any(op in text for op in (">0", ">=1", "> 0", ">= 1")):
        return "length_check"
    if "status_code !=" in text or text == "response.ok":
        return "http_negative_check"
    if text.endswith(".called") or "call_count > 0" in text or "call_count >= 1" in text:
        return "mock_called"
    if isinstance(test, ast.Subscript) or isinstance(test, ast.Name):
        return "truthiness"
    return None


def build_finding(path: Path, function: str, line: int, pattern: str, assertion: str) -> dict[str, Any]:
    rel = path.relative_to(REPO_ROOT).as_posix()
    node_id = f"{rel}::{function}"
    fingerprint = fingerprint_assertion(assertion)
    owner = owner_layer(rel)
    protected_traits = [token for token in PROTECTED_TOKENS if token in assertion.lower()]
    override_key = f"{node_id}|{pattern}|{assertion}"
    override = DECISION_OVERRIDES.get(override_key)
    if override:
        decision = override["decision"]
        decision_source = override.get("decision_source", "manual_override")
        reason = override["reason"]
    elif protected_traits:
        decision = "kept"
        decision_source = "protected_traits"
        reason = "protected contract assertion"
    else:
        decision = default_decision(pattern)
        decision_source = "heuristic"
        reason = default_reason(pattern, owner)

    finding = {
        "node_id": node_id,
        "file": rel,
        "line": line,
        "pattern": pattern,
        "assertion": assertion,
        "assertion_fingerprint": fingerprint,
        "owner_layer": owner,
        "contract_id": infer_contract_id(rel, function),
        "risk": risk_for(pattern, owner),
        "decision": decision,
        "decision_source": decision_source,
        "reason": reason,
        "review_required": decision != "strengthened",
        "replacement_test_id": None,
        "replacement_contract_id": None,
        "branch_evidence_pending": decision in {"kept", "candidate_for_removal"},
        "mutation_evidence_pending": decision in {"kept", "candidate_for_removal"},
        "protected_traits": protected_traits,
    }
    if override:
        finding.update(override)
    if finding["decision"] == "candidate_for_removal":
        finding["review_required"] = True
        finding["branch_evidence_pending"] = True
        finding["mutation_evidence_pending"] = True
    return finding


def fingerprint_assertion(assertion: str) -> str:
    return hashlib.sha256(assertion.encode("utf-8")).hexdigest()[:12]


def owner_layer(rel: str) -> str:
    for key, value in OWNER_HINTS.items():
        if key in rel:
            return value
    return "test"


def infer_contract_id(rel: str, function: str) -> str:
    stem = Path(rel).stem.removeprefix("test_")
    return f"{stem}:{function.removeprefix('test_').replace('_', '-')}"


def risk_for(pattern: str, owner: str) -> str:
    if owner in {"repository", "api", "graph"} or pattern in {"manual_exception", "broad_exception"}:
        return "medium"
    return "low"


def default_decision(pattern: str) -> str:
    if pattern in {"manual_exception", "not_none", "length_check", "mock_called", "truthiness"}:
        return "candidate_for_removal"
    return "kept"


def default_reason(pattern: str, owner: str) -> str:
    return f"{pattern} does not fully validate {owner} observable contract"


def discover_tests(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("test_*.py") if "__pycache__" not in path.parts)


def load_contract_matrix() -> dict[str, Any] | None:
    path = REPO_ROOT / "data/test_optimization/layer_contract_dedup_v1/contract_matrix.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def enrich_removal_candidates(findings: list[dict[str, Any]], contract_matrix: dict[str, Any] | None) -> None:
    matrix_available = contract_matrix is not None
    for finding in findings:
        if finding["decision"] != "candidate_for_removal":
            continue
        finding["review_required"] = True
        finding["branch_evidence_pending"] = True
        finding["mutation_evidence_pending"] = True
        if not matrix_available:
            finding["decision"] = "kept"
            finding["decision_source"] = "artifact_missing"
            finding["reason"] = "contract matrix unavailable; keep pending branch evidence"
            continue
        finding["decision_source"] = "contract_matrix_pending_review"
        finding["reason"] = "branch/replacement evidence required before removal"


def build_converted_contract_tests() -> list[dict[str, Any]]:
    return sorted(CONVERTED_CONTRACT_OVERRIDES, key=lambda item: item["node_id"])


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_report(output_dir: Path, findings: list[dict[str, Any]], counts: Counter[str], converted: list[dict[str, Any]], contract_matrix_available: bool) -> None:
    lines = [
        "# Weak Assertion Quality Cleanup v1",
        "",
        "This report summarizes AST-detected weak assertion candidates in `orchestrator/tests`.",
        "",
        "## Totals",
        "",
        f"- Scanned findings: {len(findings)}",
        f"- Strengthened: {counts['strengthened']}",
        f"- Kept: {counts['kept']}",
        f"- Candidate for removal: {counts['candidate_for_removal']}",
        f"- Converted to contract test: {len(converted)}",
        "",
        "## Scanner Notes",
        "",
        f"- contract_matrix_available: `{str(contract_matrix_available).lower()}`",
        "- file-wide manual decisions removed; exact node/pattern/assertion overrides only",
        "- async test functions are scanned",
        "- candidate_for_removal remains review-only until branch evidence exists",
        "",
    ]
    (output_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    tests_root = (REPO_ROOT / args.tests_root).resolve()
    output_dir = (REPO_ROOT / args.output_dir).resolve()

    findings: list[dict[str, Any]] = []
    scanned_files = discover_tests(tests_root)
    for path in scanned_files:
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        visitor = ScanVisitor(path)
        visitor.visit(tree)
        findings.extend(visitor.findings)

    contract_matrix = load_contract_matrix()
    enrich_removal_candidates(findings, contract_matrix)
    converted = build_converted_contract_tests()

    strengthened = [item for item in findings if item["decision"] == "strengthened"]
    kept = [item for item in findings if item["decision"] == "kept"]
    removal = [item for item in findings if item["decision"] == "candidate_for_removal"]
    counts = Counter(item["decision"] for item in findings)

    write_json(output_dir / "weak_assertion_scan.json", {"findings": findings})
    write_json(output_dir / "assertion_decisions.json", {"findings": findings})
    write_json(output_dir / "strengthened_tests.json", {"findings": strengthened})
    write_json(output_dir / "kept_assertions.json", {"findings": kept})
    write_json(output_dir / "removal_candidates.json", {"findings": removal})
    write_json(output_dir / "converted_contract_tests.json", {"findings": converted})
    write_json(
        output_dir / "summary.json",
        {
            "status": "completed",
            "scanned_files": len(scanned_files),
            "scanned_findings": len(findings),
            "contract_matrix_available": contract_matrix is not None,
            "weak_assertion_artifact_available": True,
            "decision_counts": {
                "strengthened": counts["strengthened"],
                "kept": counts["kept"],
                "candidate_for_removal": counts["candidate_for_removal"],
                "converted_to_contract_test": len(converted),
            },
            "review_required_count": sum(1 for item in findings if item["review_required"]),
        },
    )
    write_report(output_dir, findings, counts, converted, contract_matrix is not None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
