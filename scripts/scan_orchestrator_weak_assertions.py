from __future__ import annotations

import argparse
import ast
import json
from collections import Counter
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = REPO_ROOT / "data/test_optimization/assertion_quality_v1"
PROTECTED_PATTERNS = (
    "secret",
    "raw_response",
    "local_path",
    "internal uuid",
    "workspace access returns none",
    "at-most-once",
    "rollback",
    "fail-closed",
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
MANUAL_DECISIONS = {
    "orchestrator/tests/test_generation_outputs_repository_v1.py": "strengthened",
    "orchestrator/tests/test_generation_outputs_service_v1.py": "strengthened",
    "orchestrator/tests/test_archive.py": "strengthened",
    "orchestrator/tests/test_marketing_graph.py": "strengthened",
    "orchestrator/tests/test_chat_threads.py": "strengthened",
    "orchestrator/tests/test_r2_storage.py": "strengthened",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tests-root", default="orchestrator/tests")
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR.relative_to(REPO_ROOT)).replace("\\", "/"))
    return parser.parse_args()


class ScanVisitor(ast.NodeVisitor):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.function: str | None = None
        self.findings: list[dict] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
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
    if "len(" in text and any(op in text for op in ("> 0", ">= 1")):
        return "length_check"
    if "status_code !=" in text or text == "response.ok":
        return "http_negative_check"
    if text.endswith(".called") or "call_count > 0" in text or "call_count >= 1" in text:
        return "mock_called"
    if isinstance(test, ast.Subscript):
        return "truthiness"
    if isinstance(test, ast.Name):
        return "truthiness"
    return None


def build_finding(path: Path, function: str, line: int, pattern: str, assertion: str) -> dict:
    rel = path.relative_to(REPO_ROOT).as_posix()
    node_id = f"{rel}::{function}"
    owner = owner_layer(rel)
    protected = any(token in assertion.lower() for token in PROTECTED_PATTERNS)
    if protected:
        decision = "kept"
        reason = "protected contract assertion"
    else:
        decision = MANUAL_DECISIONS.get(rel, default_decision(pattern))
        reason = default_reason(pattern, owner)
    return {
        "node_id": node_id,
        "file": rel,
        "line": line,
        "pattern": pattern,
        "assertion": assertion,
        "owner_layer": owner,
        "contract_id": infer_contract_id(rel, function),
        "risk": risk_for(pattern, owner),
        "decision": decision,
        "reason": reason,
        "replacement_assertions": replacements(rel, pattern, owner),
    }


def owner_layer(rel: str) -> str:
    for key, value in OWNER_HINTS.items():
        if key in rel:
            return value
    return "test"


def infer_contract_id(rel: str, function: str) -> str:
    stem = Path(rel).stem.removeprefix("test_")
    return f"{stem}:{function.removeprefix('test_').replace('_', '-')}"


def risk_for(pattern: str, owner: str) -> str:
    if owner in {"repository", "api", "graph"}:
        return "medium"
    if pattern in {"manual_exception", "broad_exception"}:
        return "medium"
    return "low"


def default_decision(pattern: str) -> str:
    if pattern in {"manual_exception", "not_none", "length_check", "mock_called", "truthiness"}:
        return "candidate_for_removal"
    if pattern == "broad_exception":
        return "kept"
    return "kept"


def default_reason(pattern: str, owner: str) -> str:
    return f"{pattern} does not fully validate {owner} observable contract"


def replacements(rel: str, pattern: str, owner: str) -> list[str]:
    if rel in MANUAL_DECISIONS:
        if "generation_outputs_repository" in rel:
            return ["assert workspace/public-id/job/final filters are reflected in SQL clauses and params"]
        if "generation_outputs_service" in rel:
            return ["assert transaction connection is forwarded to lookup, mutation, and archive sync"]
        if "archive" in rel:
            return ["use pytest.raises(ExpectedError)", "assert exact public error contract fields"]
        if "marketing_graph" in rel:
            return ["assert copy_spec/text_layout/t2i metadata instead of bare truthiness"]
        if "chat_threads" in rel:
            return ["assert finalImagePath naming contract and brief copy semantics"]
        if "r2_storage" in rel:
            return ["assert signed_url_expires_at is parseable ISO timestamp in the future"]
    if pattern == "broad_exception":
        return ["replace with domain exception when backend contract is known"]
    return []


def discover_tests(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("test_*.py") if "__pycache__" not in path.parts)


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_report(output_dir: Path, findings: list[dict], counts: Counter[str]) -> None:
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
        f"- Converted to contract test: {counts['converted_to_contract_test']}",
        "",
        "## Focused strengthened files",
        "",
    ]
    for rel in sorted(MANUAL_DECISIONS):
        lines.append(f"- `{rel}`")
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- Protected negative/security/transaction patterns are recorded but not auto-downgraded.")
    lines.append("- Broad exception patterns remain `kept` unless domain-specific replacement is obvious.")
    (output_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    tests_root = (REPO_ROOT / args.tests_root).resolve()
    output_dir = (REPO_ROOT / args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    findings: list[dict] = []
    scanned_files = discover_tests(tests_root)
    for path in scanned_files:
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        visitor = ScanVisitor(path)
        visitor.visit(tree)
        findings.extend(visitor.findings)

    strengthened = [item for item in findings if item["decision"] == "strengthened"]
    kept = [item for item in findings if item["decision"] == "kept"]
    removal = [item for item in findings if item["decision"] == "candidate_for_removal"]
    converted: list[dict] = []
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
            "decision_counts": {
                "strengthened": counts["strengthened"],
                "kept": counts["kept"],
                "candidate_for_removal": counts["candidate_for_removal"],
                "converted_to_contract_test": counts["converted_to_contract_test"],
            },
            "focused_files": sorted(MANUAL_DECISIONS),
        },
    )
    write_report(output_dir, findings, counts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
