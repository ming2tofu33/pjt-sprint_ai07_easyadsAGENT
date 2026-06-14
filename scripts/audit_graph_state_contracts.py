from __future__ import annotations

import argparse
import ast
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = REPO_ROOT / "data" / "performance" / "state_contract_v1"
STATE_FILE = REPO_ROOT / "orchestrator" / "app" / "graph" / "state.py"
SCAN_ROOTS = [
    REPO_ROOT / "orchestrator" / "app" / "graph",
    REPO_ROOT / "orchestrator" / "app" / "llm" / "nodes",
    REPO_ROOT / "orchestrator" / "app" / "vision",
    REPO_ROOT / "orchestrator" / "app" / "reference_catalog",
    REPO_ROOT / "orchestrator" / "app" / "generation_jobs",
]
APPEND_ONLY_CANDIDATES = {
    "messages",
    "model_selections",
    "llm_call_results",
    "vision_pipeline_results",
    "artifact_refs",
}
REPLACE_ONLY_CANDIDATES = {
    "context",
    "validator_output",
    "progress_state",
    "missing_fields",
    "option_question",
    "dirty_fields",
    "status",
    "revision",
    "copy_candidates",
    "candidates",
    "t2i_request",
    "t2i_result",
    "result_payload",
}
PARTIAL_DICT_MERGE_CANDIDATES = {"current_brief"}
PERSISTED_REFERENCE_CANDIDATES = {
    "source_asset_id",
    "reference_asset_id",
    "selected_reference_template_id",
    "final_image_path",
    "asset_id",
    "output_id",
}
HELPER_MUTATION_NAMES = {
    "append_message",
    "append_model_selection",
    "append_llm_call_result",
    "update_current_brief",
    "set_requested_ad_format",
    "append_model_selection_safe",
    "append_llm_call_result_safe",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=str(OUTPUT_ROOT))
    parser.add_argument("--self-check", action="store_true")
    return parser.parse_args()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


class StateSchemaVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.channels: dict[str, str] = {}
        self.initial_values: dict[str, Any] = {}
        self.initial_exprs: dict[str, str] = {}
        self.initial_key_count = 0

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        if node.name == "MarketingState":
            for item in node.body:
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                    self.channels[item.target.id] = ast.unparse(item.annotation)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if node.name != "create_initial_marketing_state":
            self.generic_visit(node)
            return
        for stmt in node.body:
            if not isinstance(stmt, ast.Assign):
                continue
            if len(stmt.targets) != 1 or not isinstance(stmt.targets[0], ast.Name) or stmt.targets[0].id != "state":
                continue
            if not isinstance(stmt.value, ast.Dict):
                continue
            for key_node, value_node in zip(stmt.value.keys, stmt.value.values):
                if isinstance(key_node, ast.Constant) and isinstance(key_node.value, str):
                    key = key_node.value
                    self.initial_exprs[key] = ast.unparse(value_node)
                    self.initial_values[key] = literal_or_unparsed(value_node)
            self.initial_key_count = len(self.initial_values)
        self.generic_visit(node)


class FileScanVisitor(ast.NodeVisitor):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.read_get = Counter()
        self.read_index = Counter()
        self.direct_writes = Counter()
        self.in_place = Counter()
        self.helper_calls: list[dict[str, Any]] = []
        self.nodes: list[dict[str, Any]] = []
        self.function_stack: list[dict[str, Any]] = []

    def current_fn(self) -> dict[str, Any] | None:
        return self.function_stack[-1] if self.function_stack else None

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        entry = {
            "node_name": node.name,
            "file": rel(self.path),
            "symbol": node.name,
            "returned_keys": [],
            "passthrough_return_keys": [],
            "full_list_return_keys": [],
            "full_dict_return_keys": [],
            "in_place_mutated_keys": [],
            "helper_mutation_calls": [],
            "direct_state_writes": [],
            "proposed_contract": "partial_update",
            "risk": "low",
        }
        self.function_stack.append(entry)
        self.generic_visit(node)
        entry["returned_keys"] = sorted(set(entry["returned_keys"]))
        entry["passthrough_return_keys"] = sorted(set(entry["passthrough_return_keys"]))
        entry["full_list_return_keys"] = sorted(set(entry["full_list_return_keys"]))
        entry["full_dict_return_keys"] = sorted(set(entry["full_dict_return_keys"]))
        entry["in_place_mutated_keys"] = sorted(set(entry["in_place_mutated_keys"]))
        entry["helper_mutation_calls"] = sorted(set(entry["helper_mutation_calls"]))
        entry["direct_state_writes"] = sorted(set(entry["direct_state_writes"]))
        if entry["passthrough_return_keys"] or entry["in_place_mutated_keys"]:
            entry["risk"] = "high"
        elif entry["helper_mutation_calls"] or entry["direct_state_writes"]:
            entry["risk"] = "medium"
        if entry["node_name"].endswith("_node") or entry["node_name"] == "input_node":
            self.nodes.append(entry)
        self.function_stack.pop()

    def visit_Return(self, node: ast.Return) -> None:
        current = self.current_fn()
        if current and isinstance(node.value, ast.Dict):
            for key_node, value_node in zip(node.value.keys, node.value.values):
                if not isinstance(key_node, ast.Constant) or not isinstance(key_node.value, str):
                    continue
                key = key_node.value
                current["returned_keys"].append(key)
                if is_passthrough_state_get(value_node, key):
                    current["passthrough_return_keys"].append(key)
                if is_full_list_passthrough(value_node, key):
                    current["full_list_return_keys"].append(key)
                if is_full_dict_passthrough(value_node, key):
                    current["full_dict_return_keys"].append(key)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        current = self.current_fn()
        if is_state_get_call(node):
            key = get_first_string_arg(node)
            if key:
                self.read_get[key] += 1
        if current:
            helper = helper_mutation_name(node)
            if helper:
                current["helper_mutation_calls"].append(helper)
                self.helper_calls.append(
                    {
                        "file": rel(self.path),
                        "symbol": current["node_name"],
                        "line": node.lineno,
                        "helper": helper,
                    }
                )
                if helper in {"update_current_brief", "set_requested_ad_format"}:
                    current["in_place_mutated_keys"].append("current_brief")
            if is_state_setdefault_call(node):
                key = get_first_string_arg(node)
                if key:
                    self.in_place[key] += 1
                    current["in_place_mutated_keys"].append(key)
            if is_state_update_call(node):
                self.in_place["*state_update*"] += 1
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        key = subscript_string_key(node)
        if key and is_name(node.value, "state"):
            if isinstance(node.ctx, ast.Load):
                self.read_index[key] += 1
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        current = self.current_fn()
        if current:
            for target in node.targets:
                key = assigned_state_key(target)
                if key:
                    self.direct_writes[key] += 1
                    current["direct_state_writes"].append(key)
                    current["in_place_mutated_keys"].append(key)
        self.generic_visit(node)


def literal_or_unparsed(node: ast.AST) -> Any:
    try:
        return ast.literal_eval(node)
    except Exception:
        return {"expr": ast.unparse(node)}


def is_name(node: ast.AST, value: str) -> bool:
    return isinstance(node, ast.Name) and node.id == value


def get_first_string_arg(node: ast.Call) -> str | None:
    if not node.args:
        return None
    first = node.args[0]
    return first.value if isinstance(first, ast.Constant) and isinstance(first.value, str) else None


def subscript_string_key(node: ast.Subscript) -> str | None:
    sl = node.slice
    if isinstance(sl, ast.Constant) and isinstance(sl.value, str):
        return sl.value
    return None


def is_state_get_call(node: ast.Call) -> bool:
    return isinstance(node.func, ast.Attribute) and node.func.attr == "get" and is_name(node.func.value, "state")


def is_state_setdefault_call(node: ast.Call) -> bool:
    return isinstance(node.func, ast.Attribute) and node.func.attr == "setdefault" and is_name(node.func.value, "state")


def is_state_update_call(node: ast.Call) -> bool:
    return isinstance(node.func, ast.Attribute) and node.func.attr == "update" and is_name(node.func.value, "state")


def is_passthrough_state_get(node: ast.AST, key: str) -> bool:
    if not isinstance(node, ast.Call) or not is_state_get_call(node):
        return False
    return get_first_string_arg(node) == key


def is_full_list_passthrough(node: ast.AST, key: str) -> bool:
    return is_passthrough_state_get(node, key) and key in APPEND_ONLY_CANDIDATES


def is_full_dict_passthrough(node: ast.AST, key: str) -> bool:
    return is_passthrough_state_get(node, key) and key in PARTIAL_DICT_MERGE_CANDIDATES


def helper_mutation_name(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Name) and func.id in HELPER_MUTATION_NAMES:
        return func.id
    return None


def assigned_state_key(node: ast.AST) -> str | None:
    if isinstance(node, ast.Subscript) and is_name(node.value, "state"):
        return subscript_string_key(node)
    if (
        isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Subscript)
        and subscript_string_key(node.value) == "current_brief"
        and is_name(node.value.value, "state")
    ):
        return "current_brief"
    return None


def classify_channel(channel: str) -> tuple[str, bool, list[str]]:
    evidence: list[str] = []
    if channel in APPEND_ONLY_CANDIDATES:
        evidence.append("listed_append_only_candidate")
        return "append_only", channel != "messages", evidence
    if channel in REPLACE_ONLY_CANDIDATES:
        evidence.append("listed_replace_only_candidate")
        return "replace_only", False, evidence
    if channel in PARTIAL_DICT_MERGE_CANDIDATES:
        evidence.append("listed_partial_dict_merge_candidate")
        return "partial_dict_merge", True, evidence
    if channel in PERSISTED_REFERENCE_CANDIDATES or channel.endswith("_id") or channel.endswith("_path"):
        evidence.append("persisted_reference_heuristic")
        return "persisted_reference", False, evidence
    if channel.startswith("selected_") or channel.endswith("_status") or channel.endswith("_decision"):
        evidence.append("replace_scalar_heuristic")
        return "replace_only", False, evidence
    if channel.endswith("_output") or channel.endswith("_report") or channel.endswith("_result"):
        evidence.append("public_output_shape_heuristic")
        return "public_output_shape", False, evidence
    return "unknown", False, evidence


def initial_contract_decision(channel: str, value: Any) -> dict[str, Any]:
    expr = value if not isinstance(value, dict) or "expr" not in value else value["expr"]
    public_shape = channel in {
        "artifact_refs",
        "render_result",
        "result_payload",
        "final_image_path",
        "copy_compliance",
        "copy_compliance_publication_ready",
    }
    reducer_identity = channel in {"messages", "model_selections", "llm_call_results", "vision_pipeline_results", "artifact_refs"}
    optional_until_written = value in (None, [], {}, {"expr": "None"})
    safe_to_omit = optional_until_written and not reducer_identity and not public_shape
    decision = "retain" if not safe_to_omit else "candidate_sparse"
    return {
        "current_initial_value": expr,
        "direct_read_requires_presence": channel in {"job_id", "thread_id", "status", "revision"},
        "public_final_shape_requires_presence": public_shape,
        "resume_requires_presence": channel in {"job_id", "thread_id", "current_brief", "status"},
        "safe_to_omit_initially": safe_to_omit,
        "final_normalization_required": public_shape and safe_to_omit,
        "decision": decision,
        "required_reducer_identity": reducer_identity,
    }


def run_self_check() -> dict[str, Any]:
    sample = """
def sample_node(state):
    state.setdefault("messages", [])
    state["messages"].append({"role": "user"})
    update_current_brief(state, {"x": 1})
    return {
        "messages": state.get("messages", []),
        "current_brief": state.get("current_brief", {}),
        "status": "ok",
    }
"""
    tree = ast.parse(sample)
    visitor = FileScanVisitor(REPO_ROOT / "sample.py")
    visitor.visit(tree)
    node = visitor.nodes[0]
    assert "messages" in node["passthrough_return_keys"]
    assert "current_brief" in node["passthrough_return_keys"]
    assert "messages" in node["in_place_mutated_keys"]
    assert "update_current_brief" in node["helper_mutation_calls"]
    return {"status": "ok", "checked": ["passthrough_return_detection", "in_place_mutation_detection", "helper_mutation_detection"]}


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    if args.self_check:
        write_json(output_dir / "audit_self_check.json", run_self_check())
        return

    schema_tree = ast.parse(STATE_FILE.read_text(encoding="utf-8-sig"))
    schema = StateSchemaVisitor()
    schema.visit(schema_tree)

    aggregate_get = Counter()
    aggregate_index = Counter()
    aggregate_writes = Counter()
    aggregate_in_place = Counter()
    nodes: list[dict[str, Any]] = []
    mutation_sites: list[dict[str, Any]] = []

    for root in SCAN_ROOTS:
        for path in sorted(root.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            visitor = FileScanVisitor(path)
            visitor.visit(tree)
            aggregate_get.update(visitor.read_get)
            aggregate_index.update(visitor.read_index)
            aggregate_writes.update(visitor.direct_writes)
            aggregate_in_place.update(visitor.in_place)
            nodes.extend(visitor.nodes)
            mutation_sites.extend(visitor.helper_calls)

    passthrough_violations = []
    for node in nodes:
        for key in node["passthrough_return_keys"]:
            if not (node["node_name"] == "input_node"):
                passthrough_violations.append(
                    {
                        "file": node["file"],
                        "symbol": node["symbol"],
                        "key": key,
                    }
                )

    channel_rows = []
    for channel, declared_type in sorted(schema.channels.items()):
        classification, reducer_candidate, evidence = classify_channel(channel)
        row = {
            "channel": channel,
            "declared_type": declared_type,
            "current_initial_value": schema.initial_values.get(channel),
            "direct_index_read_count": aggregate_index[channel],
            "get_read_count": aggregate_get[channel],
            "write_site_count": aggregate_writes[channel],
            "full_return_site_count": sum(channel in node["passthrough_return_keys"] for node in nodes),
            "delta_return_site_count": sum(channel in node["returned_keys"] and channel not in node["passthrough_return_keys"] for node in nodes),
            "in_place_mutation_site_count": aggregate_in_place[channel],
            "public_contract_consumer_count": int(channel in {"result_payload", "artifact_refs", "render_result", "final_image_path"}),
            "resume_consumer_count": int(channel in {"job_id", "thread_id", "current_brief", "status", "messages"}),
            "checkpoint_required": channel not in {"latency_ms", "updated_at", "created_at"},
            "classification": classification,
            "reducer_candidate": reducer_candidate,
            "decision": "pending",
            "evidence": evidence,
        }
        channel_rows.append(row)

    initial_contract = []
    for channel in sorted(schema.initial_values):
        row = {"channel": channel}
        row.update(initial_contract_decision(channel, schema.initial_values[channel]))
        initial_contract.append(row)

    mutation_details = sorted(
        mutation_sites + [
            {
                "file": node["file"],
                "symbol": node["symbol"],
                "line": None,
                "helper": key,
            }
            for node in nodes
            for key in node["direct_state_writes"]
        ],
        key=lambda item: (item["file"], item["symbol"], str(item["line"])),
    )

    write_json(output_dir / "state_channel_classification.json", channel_rows)
    write_json(output_dir / "node_return_contracts.json", nodes)
    write_json(output_dir / "in_place_mutation_sites.json", mutation_details)
    write_json(output_dir / "passthrough_return_violations.json", passthrough_violations)
    write_json(
        output_dir / "initial_state_contract.json",
        {
            "initial_key_count": schema.initial_key_count,
            "channels": initial_contract,
        },
    )


if __name__ == "__main__":
    main()
