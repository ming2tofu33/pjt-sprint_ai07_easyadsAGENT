from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = REPO_ROOT / "data" / "performance" / "db_runtime_v1"
APP_ROOT = REPO_ROOT / "orchestrator" / "app"
API_ROOT = APP_ROOT / "api" / "routers"
REPO_DB_ROOT = APP_ROOT / "db" / "repositories"
HEAVY_COLUMNS = {
    "brief",
    "brand_kit_snapshot",
    "params",
    "request_payload",
    "result_payload",
    "metadata",
    "error",
    "validation_report",
    "plan_policy",
    "model_selections",
    "llm_call_results",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
    parser.add_argument("--self-check", action="store_true")
    return parser.parse_args()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def route_inventory() -> list[dict[str, Any]]:
    inventory: list[dict[str, Any]] = []
    targets = {
        "generation_jobs": API_ROOT / "generation_jobs.py",
        "archive": API_ROOT / "archive.py",
        "chat_threads": API_ROOT / "chat_threads.py",
    }
    for endpoint_group, path in targets.items():
        tree = ast.parse(read_text(path))
        for node in tree.body:
            if not isinstance(node, ast.FunctionDef):
                continue
            decorators = [ast.unparse(dec) for dec in node.decorator_list]
            route_decorators = [dec for dec in decorators if dec.startswith("router.")]
            if not route_decorators:
                continue
            inventory.append(
                {
                    "endpoint_id": node.name,
                    "group": endpoint_group,
                    "method": route_decorators[0].split("(", 1)[0].replace("router.", "").upper(),
                    "route_template": route_decorators[0],
                    "public_response_model": next(
                        (
                            kw.value.id
                            for dec in node.decorator_list
                            if isinstance(dec, ast.Call)
                            for kw in dec.keywords
                            if kw.arg == "response_model" and isinstance(kw.value, ast.Name)
                        ),
                        None,
                    ),
                    "service_symbol": first_called_symbol(node),
                }
            )
    inventory.sort(key=lambda item: item["endpoint_id"])
    return inventory


def first_called_symbol(node: ast.FunctionDef) -> str | None:
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            func = child.func
            if isinstance(func, ast.Name):
                return func.id
            if isinstance(func, ast.Attribute):
                return ast.unparse(func)
    return None


def repository_inventory() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    sql_rows: list[dict[str, Any]] = []
    heavy_rows: list[dict[str, Any]] = []
    star_rows: list[dict[str, Any]] = []
    for path in sorted(REPO_DB_ROOT.glob("*.py")):
        text = read_text(path)
        tree = ast.parse(text)
        for node in tree.body:
            if not isinstance(node, ast.FunctionDef):
                continue
            string_literals = [child.value for child in ast.walk(node) if isinstance(child, ast.Constant) and isinstance(child.value, str)]
            sql_texts = [value for value in string_literals if any(token in value.lower() for token in ("select ", "insert ", "update ", "delete "))]
            for sql in sql_texts:
                normalized = " ".join(sql.split())
                selected_columns = parse_selected_columns(normalized)
                heavy = [col for col in selected_columns if base_column_name(col) in HEAVY_COLUMNS]
                star_kind = classify_select_star(normalized, node.name)
                if star_kind:
                    star_rows.append(
                        {
                            "repository": path.stem,
                            "symbol": node.name,
                            "classification": star_kind,
                            "sql_excerpt": normalized[:200],
                        }
                    )
                sql_rows.append(
                    {
                        "repository": path.stem,
                        "symbol": node.name,
                        "operation": infer_operation(node.name),
                        "sql_fingerprint": stable_hash(normalized),
                        "tables": parse_tables(normalized),
                        "selected_columns": selected_columns,
                        "select_star": "*" in normalized or ".*" in normalized,
                        "heavy_columns_selected": heavy,
                        "public_fields_consumed": [],
                        "unused_selected_columns": [],
                        "candidate_projection": [col for col in selected_columns if base_column_name(col) not in HEAVY_COLUMNS][:12],
                    }
                )
                for col in heavy:
                    heavy_rows.append(
                        {
                            "repository": path.stem,
                            "symbol": node.name,
                            "column": base_column_name(col),
                            "classification": classify_heavy_column(node.name),
                        }
                    )
    return sql_rows, heavy_rows, star_rows


def stable_hash(value: str) -> str:
    import hashlib
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def parse_selected_columns(sql: str) -> list[str]:
    lower = sql.lower()
    if "select " not in lower or " from " not in lower:
        return []
    select_part = sql[lower.index("select ") + 7 : lower.index(" from ")]
    return [part.strip() for part in select_part.split(",") if part.strip()]


def base_column_name(column: str) -> str:
    plain = column.split(" as ", 1)[0].strip()
    return plain.split(".")[-1].replace("->>", "").replace("'", "").strip()


def parse_tables(sql: str) -> list[str]:
    lower = " ".join(sql.lower().split())
    tables: list[str] = []
    for token in (" from ", " join ", " update ", " into "):
        if token not in lower:
            continue
        tail = lower.split(token, 1)[1]
        table = tail.split(" ", 1)[0].strip(",;")
        if table and table not in tables:
            tables.append(table)
    return tables


def classify_select_star(sql: str, symbol: str) -> str | None:
    lower = sql.lower()
    if "returning *" in lower:
        return "approved_write_returning" if any(token in symbol for token in ("create", "update", "upsert", "mark_", "archive_", "restore_")) else "unapproved_internal_query"
    if "select *" in lower or ".*" in lower:
        if any(token in symbol for token in ("list_", "count_", "status")):
            return "unapproved_list_query" if "status" not in symbol else "unapproved_status_query"
        if any(token in symbol for token in ("get_", "detail")):
            return "approved_detail_query"
        return "unapproved_internal_query"
    return None


def classify_heavy_column(symbol: str) -> str:
    if "status" in symbol:
        return "status_required"
    if "list_" in symbol:
        return "list_required"
    if "get_" in symbol or "detail" in symbol:
        return "detail_only"
    if any(token in symbol for token in ("create", "update", "upsert", "mark_")):
        return "write_only"
    return "unknown"


def infer_operation(symbol: str) -> str:
    if symbol.startswith("list_"):
        return "list"
    if symbol.startswith("count_"):
        return "internal_validation"
    if symbol.startswith("get_"):
        return "detail"
    if symbol.startswith("create_") or symbol.startswith("update_") or symbol.startswith("upsert_"):
        return "sync/write"
    return "internal_validation"


def projection_contracts(sql_rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "projection_types_added": [
            "JobScopeRow",
            "ArchiveListRow",
            "FinalGenerationOutputRow",
            "ChatMessageJobLookupRow",
        ],
        "status_projection_added": any(row["symbol"] == "get_generation_job_scope_row_by_public_id" for row in sql_rows),
        "list_projection_count": sum(1 for row in sql_rows if row["operation"] == "list"),
        "detail_projection_count": sum(1 for row in sql_rows if row["operation"] == "detail"),
    }


def run_self_check() -> dict[str, Any]:
    sql_rows, heavy_rows, star_rows = repository_inventory()
    assert any(row["repository"] == "archive_items" for row in sql_rows)
    assert any(row["classification"].startswith("approved") or row["classification"].startswith("unapproved") for row in star_rows)
    assert heavy_rows
    assert route_inventory()
    return {"status": "ok", "checked": ["route_inventory", "sql_inventory", "heavy_column_classification", "select_star_guard"]}


def main() -> None:
    args = parse_args()
    if args.self_check:
        print(json.dumps(run_self_check(), ensure_ascii=False))
        return
    output_dir = Path(args.output_dir)
    endpoints = route_inventory()
    sql_rows, heavy_rows, star_rows = repository_inventory()
    write_json(output_dir / "endpoint_query_inventory.json", endpoints)
    write_json(output_dir / "sql_projection_inventory.json", sql_rows)
    write_json(output_dir / "heavy_column_classification.json", heavy_rows)
    write_json(output_dir / "select_star_violations.json", star_rows)
    write_json(output_dir / "projection_contracts.json", projection_contracts(sql_rows))


if __name__ == "__main__":
    main()
