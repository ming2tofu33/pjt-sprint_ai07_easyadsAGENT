"""Utilities for parsing and validating structured LLM outputs.

LLM nodes should use this module after receiving raw model output and before
writing parsed data back into MarketingState. The schema source of truth stays
in Pydantic models such as orchestrator.app.schemas.llm_marketing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError


SchemaModelT = TypeVar("SchemaModelT", bound=BaseModel)


@dataclass(slots=True)
class LLMOutputValidationResult:
    """Serializable validation result for LLM structured outputs."""

    ok: bool
    stage: str
    node_name: str | None = None
    schema_name: str | None = None
    data: dict[str, Any] | None = None
    errors: list[dict[str, Any]] = field(default_factory=list)
    error_summary: str | None = None
    raw_payload: Any | None = None

    def to_dict(self, include_raw_payload: bool = False) -> dict[str, Any]:
        result = {
            "ok": self.ok,
            "stage": self.stage,
            "node_name": self.node_name,
            "schema_name": self.schema_name,
            "data": self.data,
            "errors": self.errors,
            "error_summary": self.error_summary,
        }
        if include_raw_payload:
            result["raw_payload"] = self.raw_payload
        return result


def parse_llm_json(raw_output: Any, node_name: str | None = None) -> LLMOutputValidationResult:
    """Parse a raw LLM response into JSON-compatible Python data.

    Dict/list payloads are accepted as already parsed JSON. Strings may be raw
    JSON or fenced JSON blocks such as ```json ... ```.
    """

    if isinstance(raw_output, BaseModel):
        return LLMOutputValidationResult(
            ok=True,
            stage="json_parse",
            node_name=node_name,
            data=raw_output.model_dump(),
            raw_payload=raw_output,
        )

    if isinstance(raw_output, (dict, list)):
        return LLMOutputValidationResult(
            ok=True,
            stage="json_parse",
            node_name=node_name,
            data=raw_output if isinstance(raw_output, dict) else {"items": raw_output},
            raw_payload=raw_output,
        )

    if isinstance(raw_output, bytes):
        raw_output = raw_output.decode("utf-8", errors="replace")

    if not isinstance(raw_output, str):
        return LLMOutputValidationResult(
            ok=False,
            stage="json_parse",
            node_name=node_name,
            errors=[{"msg": f"Unsupported LLM output type: {type(raw_output).__name__}", "type": "type_error"}],
            error_summary="LLM output must be a JSON string, dict, list, bytes, or Pydantic model.",
            raw_payload=raw_output,
        )

    candidate = extract_json_candidate(raw_output)
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError as exc:
        return LLMOutputValidationResult(
            ok=False,
            stage="json_parse",
            node_name=node_name,
            errors=[
                {
                    "loc": [exc.lineno, exc.colno],
                    "msg": exc.msg,
                    "type": "json_decode_error",
                }
            ],
            error_summary=f"Invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}",
            raw_payload=raw_output,
        )

    return LLMOutputValidationResult(
        ok=True,
        stage="json_parse",
        node_name=node_name,
        data=payload if isinstance(payload, dict) else {"items": payload},
        raw_payload=payload,
    )


def validate_llm_output(
    payload: Any,
    schema_model: type[SchemaModelT],
    node_name: str | None = None,
) -> LLMOutputValidationResult:
    """Validate parsed LLM output against a Pydantic schema model."""

    schema_name = schema_model.__name__
    try:
        parsed = schema_model.model_validate(payload)
    except ValidationError as exc:
        errors = normalize_pydantic_errors(exc)
        return LLMOutputValidationResult(
            ok=False,
            stage="schema_validation",
            node_name=node_name,
            schema_name=schema_name,
            errors=errors,
            error_summary=summarize_errors(errors),
            raw_payload=payload,
        )

    return LLMOutputValidationResult(
        ok=True,
        stage="schema_validation",
        node_name=node_name,
        schema_name=schema_name,
        data=parsed.model_dump(),
        raw_payload=payload,
    )


def parse_and_validate_llm_json(
    raw_output: Any,
    schema_model: type[SchemaModelT],
    node_name: str | None = None,
) -> LLMOutputValidationResult:
    """Parse raw LLM output, then validate it against a Pydantic schema."""

    parse_result = parse_llm_json(raw_output, node_name=node_name)
    if not parse_result.ok:
        parse_result.schema_name = schema_model.__name__
        return parse_result
    return validate_llm_output(parse_result.raw_payload, schema_model, node_name=node_name)


def extract_json_candidate(raw_text: str) -> str:
    """Return the most likely JSON segment from a raw model response."""

    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].lstrip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    if not text:
        return text

    starts = [index for index in (text.find("{"), text.find("[")) if index >= 0]
    if not starts:
        return text
    start = min(starts)
    decoder = json.JSONDecoder()
    try:
        _, end = decoder.raw_decode(text[start:])
    except json.JSONDecodeError:
        return text
    return text[start : start + end]


def normalize_pydantic_errors(exc: ValidationError) -> list[dict[str, Any]]:
    """Convert Pydantic errors into JSON-safe dictionaries."""

    normalized: list[dict[str, Any]] = []
    for error in exc.errors():
        normalized.append(
            {
                "loc": list(error.get("loc", [])),
                "msg": str(error.get("msg", "")),
                "type": str(error.get("type", "")),
                "input": repr(error.get("input")) if "input" in error else None,
            }
        )
    return normalized


def summarize_errors(errors: list[dict[str, Any]], limit: int = 3) -> str:
    """Build a compact human-readable error summary."""

    if not errors:
        return "Unknown validation error."

    parts: list[str] = []
    for error in errors[:limit]:
        loc = ".".join(str(item) for item in error.get("loc", [])) or "<root>"
        msg = error.get("msg", "validation error")
        parts.append(f"{loc}: {msg}")

    remaining = len(errors) - limit
    if remaining > 0:
        parts.append(f"...and {remaining} more error(s)")
    return "; ".join(parts)
