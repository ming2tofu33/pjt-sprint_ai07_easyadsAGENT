"""Plan-based image engine selection policy."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ImagePlanTier = Literal["free", "economic", "premium"]
ImageEngineName = Literal["gpt_image_1", "gpt_image_2", "sd35_large", "flux"]
ExecutionBackend = Literal["local", "modal", "external_api"]

_KNOWN_ENGINES: tuple[ImageEngineName, ...] = ("gpt_image_1", "gpt_image_2", "sd35_large", "flux")


class ImageEnginePolicy(BaseModel):
    plan: ImagePlanTier
    default_engine: ImageEngineName
    allowed_engines: list[ImageEngineName]
    blocked_engines: list[ImageEngineName] = Field(default_factory=list)
    allow_parallel_comparison: bool = False
    allow_external_api: bool = False
    allow_local_or_modal: bool = True
    notes: list[str] = Field(default_factory=list)


def normalize_image_plan(value: str | None) -> ImagePlanTier:
    normalized = (value or "").strip().lower()
    if normalized in {"economic", "economy", "standard"}:
        return "economic"
    if normalized in {"premium", "pro", "business"}:
        return "premium"
    return "free"


def get_image_engine_policy(plan: str | None) -> ImageEnginePolicy:
    normalized = normalize_image_plan(plan)
    if normalized == "free":
        return ImageEnginePolicy(
            plan="free",
            default_engine="flux",
            allowed_engines=["sd35_large", "flux"],
            blocked_engines=["gpt_image_1", "gpt_image_2"],
            allow_parallel_comparison=False,
            allow_external_api=False,
            allow_local_or_modal=True,
            notes=["Free plans use local or Modal-capable engines only."],
        )
    if normalized == "economic":
        return ImageEnginePolicy(
            plan="economic",
            default_engine="gpt_image_1",
            allowed_engines=["gpt_image_1", "sd35_large", "flux"],
            allow_parallel_comparison=False,
            allow_external_api=True,
            allow_local_or_modal=True,
            notes=["Economic plans allow one selected engine including GPT-image-1."],
        )
    return ImageEnginePolicy(
        plan="premium",
        default_engine="gpt_image_1",
        allowed_engines=["gpt_image_1", "gpt_image_2", "sd35_large", "flux"],
        allow_parallel_comparison=True,
        allow_external_api=True,
        allow_local_or_modal=True,
        notes=["Premium plans can run parallel engine comparisons when explicitly requested."],
    )


def is_engine_allowed_for_plan(engine: str, plan: str | None) -> bool:
    return _normalize_engine(engine) in get_image_engine_policy(plan).allowed_engines


def choose_default_engine_for_plan(plan: str | None) -> str:
    return get_image_engine_policy(plan).default_engine


def resolve_requested_engines_for_plan(
    *,
    plan: str | None,
    requested_engines: list[str] | None = None,
    include_comparison: bool = False,
) -> list[str]:
    policy = get_image_engine_policy(plan)
    if include_comparison and policy.allow_parallel_comparison:
        return list(policy.allowed_engines)

    if not requested_engines:
        return [policy.default_engine]

    resolved: list[str] = []
    for engine in requested_engines:
        normalized = _normalize_engine(engine)
        if normalized is None or normalized not in policy.allowed_engines or normalized in resolved:
            continue
        resolved.append(normalized)
    return resolved


def _normalize_engine(engine: str | None) -> ImageEngineName | None:
    normalized = (engine or "").strip().lower()
    if normalized in _KNOWN_ENGINES:
        return normalized  # type: ignore[return-value]
    return None
