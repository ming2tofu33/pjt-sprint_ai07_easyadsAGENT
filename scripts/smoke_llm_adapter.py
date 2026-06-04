"""Smoke runner for guarded LLM adapters."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestrator.app.llm.adapters.registry import get_llm_adapter  # noqa: E402
from orchestrator.app.llm.metadata_contracts import sanitize_metadata  # noqa: E402
from orchestrator.app.llm.settings import get_llm_settings  # noqa: E402
from orchestrator.app.schemas.llm_model_policy import ModelSelection  # noqa: E402


def run_smoke(
    *,
    provider: str,
    task: str,
    dry_run: bool,
    confirm_actual: bool,
    output_dir: Path,
) -> dict[str, Any]:
    settings = get_llm_settings()
    actual_allowed = confirm_actual and settings.enable_api_call and provider != "mock" and not dry_run
    selected_model_class = "local_quality" if provider == "local_openai_compat" else "api_mini"
    allowed_providers = {"mock", "openai", "openai_compatible", "local_openai_compat"}
    selection = ModelSelection(
        node_name=task,
        user_plan="premium",
        selected_model_class=selected_model_class if provider != "mock" else "mock",
        provider=provider if provider in allowed_providers else "mock",
        structured_output=False,
        reason="llm adapter smoke",
    )
    if dry_run or not actual_allowed:
        result = {
            "success": False,
            "error": None if dry_run else "actual_call_not_confirmed_or_disabled",
            "metadata": {
                "dry_run": dry_run,
                "confirm_actual": confirm_actual,
                "enable_api_call": settings.enable_api_call,
                "provider": provider,
                "openai_api_key_present": bool(settings.openai_api_key),
                "local_api_key_present": bool(settings.local_llm_api_key),
                "local_base_url_configured": bool(settings.local_llm_base_url),
                "local_model_configured": bool(settings.local_llm_model),
                "local_api_style": settings.local_llm_api_style,
            },
        }
    else:
        adapter = get_llm_adapter(provider, strict=False, allow_mock_fallback=True)
        call = adapter.invoke_text(
            "Return a concise smoke response.",
            selection,
            metadata={"task": task, "smoke": True},
        )
        result = _safe_smoke_call_result(call.model_dump(mode="json"))

    report = {
        "schema_version": "llm_adapter_smoke_v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "provider": provider,
        "task": task,
        "dry_run": dry_run,
        "actual_call_attempted": actual_allowed,
        "result": sanitize_metadata(result),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"llm_adapter_smoke_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    report["report_path"] = path.as_posix()
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", default="mock")
    parser.add_argument("--task", default="copy_candidate_generation")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--confirm-actual", action="store_true")
    parser.add_argument("--output-dir", default="data/logs")
    return parser.parse_args(argv)


def _preview_value(value: Any, max_length: int = 240) -> str | None:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False)
    else:
        text = str(value)
    normalized = " ".join(text.split())
    if len(normalized) <= max_length:
        return normalized
    return f"{normalized[: max_length - 3]}..."


def _safe_smoke_call_result(call: dict[str, Any]) -> dict[str, Any]:
    return {
        "success": call.get("success"),
        "error": call.get("error"),
        "latency_ms": call.get("latency_ms"),
        "token_usage": call.get("token_usage"),
        "cost_estimate": call.get("cost_estimate"),
        "output_preview": _preview_value(call.get("output")),
        "raw_text_present": bool(call.get("raw_text")),
        "metadata": sanitize_metadata(call.get("metadata") or {}),
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = run_smoke(
        provider=args.provider,
        task=args.task,
        dry_run=args.dry_run or not args.confirm_actual,
        confirm_actual=args.confirm_actual,
        output_dir=Path(args.output_dir),
    )
    print(json.dumps({"status": "ok", "report_path": report["report_path"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
