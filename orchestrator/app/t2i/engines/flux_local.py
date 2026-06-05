"""Guarded FLUX local engine lane."""

from __future__ import annotations

import inspect
import re
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

from orchestrator.app.t2i.engines.base import T2IGenerationInput, T2IGenerationOutput
from orchestrator.app.t2i.settings import (
    T2IEngineUnavailableError,
    get_hf_token,
    load_t2i_settings,
    require_t2i_enabled,
)

_PIPELINE = None

MANDATORY_FLUX_CONSTRAINTS = (
    "no readable text",
    "no Korean letters",
    "no logos",
    "no signage",
    "reserved negative space",
    "copy overlay",
)

_CONSERVATIVE_CLIP_WORD_LIMIT = 60


class FluxPromptTokenBudgetError(T2IEngineUnavailableError):
    error_code = "flux_prompt_token_budget_unresolvable"


@dataclass(frozen=True)
class FluxPromptBundle:
    clip_prompt: str
    t5_prompt: str
    clip_token_count: int | None
    clip_max_tokens: int
    clip_truncated: bool
    t5_token_count: int | None
    t5_max_tokens: int
    t5_truncated: bool
    critical_constraints_preserved: bool
    subject_preserved: bool
    business_context_preserved: bool


class FluxLocalEngine:
    engine_name = "flux"

    def generate(self, request: T2IGenerationInput) -> T2IGenerationOutput:
        started = perf_counter()
        settings = load_t2i_settings()
        require_t2i_enabled(self.engine_name, settings)
        _require_flux_model_readiness(settings)

        model_ref = settings.flux_local_path or settings.flux_model_id
        pipe = _load_pipeline(model_ref, settings.flux_device)
        prompt_bundle = prepare_flux_prompt_bundle(
            pipe=pipe,
            full_prompt=request.prompt,
            metadata=request.metadata,
            t5_max_tokens=settings.flux_max_sequence_length,
        )

        output_dir = Path(request.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        call_kwargs = _build_flux_call_kwargs(
            pipe=pipe,
            prompt_bundle=prompt_bundle,
            request=request,
            settings=settings,
        )
        result = pipe(**call_kwargs)  # pragma: no cover - heavy local opt-in only

        image_paths: list[str] = []
        for index, image in enumerate(getattr(result, "images", []) or []):
            path = output_dir / f"flux_{index}.png"
            image.save(path)
            image_paths.append(path.as_posix())

        if not image_paths:
            raise T2IEngineUnavailableError("FLUX response did not include generated images.")

        safe_request_metadata = _safe_flux_metadata(request.metadata)
        return T2IGenerationOutput(
            engine=self.engine_name,
            image_paths=image_paths,
            latency_ms=int((perf_counter() - started) * 1000),
            metadata={
                **safe_request_metadata,
                "api_call": False,
                "model": settings.flux_model_id if not settings.flux_local_path else None,
                "model_source": "local_path" if settings.flux_local_path else "model_id",
                "local_path_present": bool(settings.flux_local_path),
                "hf_token_present": settings.hf_token_present,
                "num_inference_steps": settings.flux_num_inference_steps,
                "guidance_scale": settings.flux_guidance_scale,
                "clip_token_count": prompt_bundle.clip_token_count,
                "clip_max_tokens": prompt_bundle.clip_max_tokens,
                "clip_truncated": prompt_bundle.clip_truncated,
                "prompt_2_used": "prompt_2" in call_kwargs,
                "t5_token_count": prompt_bundle.t5_token_count,
                "t5_max_tokens": prompt_bundle.t5_max_tokens,
                "t5_truncated": prompt_bundle.t5_truncated,
                "critical_constraints_preserved": prompt_bundle.critical_constraints_preserved,
                "subject_preserved": prompt_bundle.subject_preserved,
                "business_context_preserved": prompt_bundle.business_context_preserved,
            },
        )


def prepare_flux_prompt_bundle(
    *,
    pipe: object,
    full_prompt: str,
    metadata: dict[str, Any] | None = None,
    t5_max_tokens: int = 256,
) -> FluxPromptBundle:
    """Build CLIP-safe prompt plus full T5 prompt for FLUX dual conditioning."""
    clip_tokenizer = getattr(pipe, "tokenizer", None)
    t5_tokenizer = getattr(pipe, "tokenizer_2", None)
    clip_max_tokens = _tokenizer_max_length(clip_tokenizer, default=77, upper_bound=77)
    t5_max_tokens = max(64, min(int(t5_max_tokens or 256), 512))

    full_clip_token_count = _count_tokens(clip_tokenizer, full_prompt, max_tokens=None)
    subject = _subject_fragment_from_metadata(full_prompt, metadata or {})
    business_fragment = _business_fragment(metadata or {})
    if (
        full_clip_token_count is not None
        and full_clip_token_count <= clip_max_tokens
        and _contains_mandatory_constraints(full_prompt)
    ):
        clip_prompt = full_prompt.strip()
        clip_token_count = full_clip_token_count
        clip_truncated = False
    else:
        fragments = _clip_priority_fragments(full_prompt, metadata or {})
        clip_prompt, clip_token_count, clip_truncated = _fit_clip_fragments(
            fragments=fragments,
            tokenizer=clip_tokenizer,
            max_tokens=clip_max_tokens,
        )
        if full_clip_token_count and full_clip_token_count > clip_max_tokens:
            clip_truncated = True
    critical_constraints_preserved = _critical_constraints_preserved(clip_prompt, full_prompt)
    subject_preserved = _fragment_preserved(clip_prompt, subject)
    business_context_preserved = _business_context_preserved(clip_prompt, metadata or {}, business_fragment)
    if not critical_constraints_preserved:
        raise FluxPromptTokenBudgetError(
            "FLUX CLIP prompt could not preserve mandatory subject and no-text constraints within the tokenizer limit."
        )

    t5_token_count = _count_tokens(t5_tokenizer, full_prompt, max_tokens=None)
    return FluxPromptBundle(
        clip_prompt=clip_prompt,
        t5_prompt=full_prompt,
        clip_token_count=clip_token_count,
        clip_max_tokens=clip_max_tokens,
        clip_truncated=clip_truncated,
        t5_token_count=t5_token_count,
        t5_max_tokens=t5_max_tokens,
        t5_truncated=bool(t5_token_count and t5_token_count > t5_max_tokens),
        critical_constraints_preserved=critical_constraints_preserved,
        subject_preserved=subject_preserved,
        business_context_preserved=business_context_preserved,
    )


def _build_flux_call_kwargs(*, pipe: object, prompt_bundle: FluxPromptBundle, request: T2IGenerationInput, settings) -> dict:
    call_kwargs = {
        "prompt": prompt_bundle.clip_prompt,
        "width": request.width,
        "height": request.height,
        "num_images_per_prompt": min(request.num_images, settings.max_images_per_job),
        "num_inference_steps": settings.flux_num_inference_steps,
        "guidance_scale": settings.flux_guidance_scale,
    }
    parameters = inspect.signature(pipe.__call__).parameters
    if "prompt_2" in parameters:
        call_kwargs["prompt_2"] = prompt_bundle.t5_prompt
    if "max_sequence_length" in parameters:
        call_kwargs["max_sequence_length"] = settings.flux_max_sequence_length
    return call_kwargs


def _clip_priority_fragments(full_prompt: str, metadata: dict[str, Any]) -> list[str]:
    subject = _subject_fragment_from_metadata(full_prompt, metadata)
    business_fragment = _business_fragment(metadata)
    return [
        "Text-free commercial advertising background",
        "no readable text",
        "no Korean letters",
        "no logos",
        "no signage",
        "reserved negative space for copy overlay",
        subject,
        business_fragment,
        "clear hero product or subject",
        "realistic premium commercial lighting",
        "uncluttered composition",
    ]


def _fit_clip_fragments(*, fragments: list[str], tokenizer: object | None, max_tokens: int) -> tuple[str, int | None, bool]:
    selected: list[str] = []
    truncated = False
    for fragment in fragments:
        candidate = _join_fragments([*selected, fragment])
        token_count = _count_tokens(tokenizer, candidate, max_tokens=None)
        if token_count is None:
            selected.append(fragment)
            continue
        if token_count <= max_tokens:
            selected.append(fragment)
        else:
            truncated = True
            continue

    prompt = _join_fragments(selected)
    if tokenizer is None:
        words = prompt.split()
        if len(words) > _CONSERVATIVE_CLIP_WORD_LIMIT:
            prompt = " ".join(words[:_CONSERVATIVE_CLIP_WORD_LIMIT])
            truncated = True
        return prompt, len(prompt.split()) + 2, truncated

    token_count = _count_tokens(tokenizer, prompt, max_tokens=None)
    return prompt, token_count, truncated


def _join_fragments(fragments: list[str]) -> str:
    return ". ".join(fragment.strip(" .") for fragment in fragments if fragment.strip()) + "."


def _subject_fragment(full_prompt: str) -> str:
    normalized = " ".join(full_prompt.split())
    for prefix in (
        "Create a clean advertising background for the following request:",
        "Create a premium",
        "Create a clean",
    ):
        normalized = normalized.replace(prefix, " ")
    normalized = re.sub(r"\bdo not include\b.*", "", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\bavoid visible\b.*", "", normalized, flags=re.IGNORECASE)
    normalized = " ".join(normalized.split())
    words = normalized.split()[:10]
    return " ".join(words) if words else "clear advertising subject"


def _subject_fragment_from_metadata(full_prompt: str, metadata: dict[str, Any]) -> str:
    subject = str(metadata.get("primary_subject") or metadata.get("item_or_service") or "").strip()
    return subject or _subject_fragment(full_prompt)


def _business_fragment(metadata: dict[str, Any]) -> str:
    business_type = str(metadata.get("business_type") or metadata.get("business_subtype") or "").replace("_", " ").strip()
    return f"{business_type} advertising scene" if business_type else "commercial advertising scene"


def _tokenizer_max_length(tokenizer: object | None, *, default: int, upper_bound: int | None = None) -> int:
    value = getattr(tokenizer, "model_max_length", default)
    try:
        value = int(value)
    except (TypeError, ValueError):
        value = default
    if value <= 0 or value > 10000:
        value = default
    if upper_bound is not None:
        value = min(value, upper_bound)
    return value


def _count_tokens(tokenizer: object | None, text: str, max_tokens: int | None) -> int | None:
    if tokenizer is None:
        return None
    kwargs = {"add_special_tokens": True, "truncation": False, "verbose": False}
    if max_tokens is not None:
        kwargs.update({"truncation": True, "max_length": max_tokens})
    encoded = tokenizer(text, **kwargs)
    input_ids = encoded.get("input_ids") if isinstance(encoded, dict) else getattr(encoded, "input_ids", None)
    if input_ids is None:
        return None
    if input_ids and isinstance(input_ids[0], list):
        return len(input_ids[0])
    return len(input_ids)


def _critical_constraints_preserved(clip_prompt: str, full_prompt: str) -> bool:
    combined = f"{clip_prompt}\n{full_prompt}".lower()
    clip_lower = clip_prompt.lower()
    constraints = tuple(constraint.lower() for constraint in MANDATORY_FLUX_CONSTRAINTS)
    return all(constraint in combined for constraint in constraints) and all(
        constraint in clip_lower for constraint in constraints
    )


def _contains_mandatory_constraints(prompt: str) -> bool:
    lower = prompt.lower()
    return all(constraint.lower() in lower for constraint in MANDATORY_FLUX_CONSTRAINTS)


def _fragment_preserved(prompt: str, fragment: str) -> bool:
    if not fragment:
        return False
    return fragment.lower() in prompt.lower()


def _business_context_preserved(prompt: str, metadata: dict[str, Any], business_fragment: str) -> bool:
    business_type = str(metadata.get("business_type") or metadata.get("business_subtype") or "").replace("_", " ").strip()
    if business_type:
        return business_type.lower() in prompt.lower()
    return business_fragment.lower() in prompt.lower()


def _safe_flux_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    sanitized = _sanitize_metadata_recursive(metadata)
    return sanitized if isinstance(sanitized, dict) else {}


def _sanitize_metadata_recursive(value):
    blocked = {"api_key", "openai_api_key", "hf_token", "huggingface_token", "token", "authorization", "secret", "password"}
    if isinstance(value, dict):
        return {
            key: _sanitize_metadata_recursive(item)
            for key, item in value.items()
            if str(key).lower() not in blocked
        }
    if isinstance(value, list):
        return [_sanitize_metadata_recursive(item) for item in value]
    return value


def _load_pipeline(model_ref: str | None, device: str):
    global _PIPELINE
    if _PIPELINE is not None:
        return _PIPELINE

    try:
        import torch  # type: ignore
        from diffusers import FluxPipeline  # type: ignore
    except Exception as exc:  # pragma: no cover - optional dependency
        raise T2IEngineUnavailableError("FLUX dependencies are unavailable.") from exc

    if not model_ref:
        raise T2IEngineUnavailableError("FLUX model reference is missing.")

    kwargs = {}
    token = get_hf_token()
    if token:
        kwargs["token"] = token

    _PIPELINE = FluxPipeline.from_pretrained(model_ref, **kwargs)  # pragma: no cover

    target_device = device
    if target_device == "auto":
        target_device = "cuda" if torch.cuda.is_available() else "cpu"
    if hasattr(_PIPELINE, "to"):  # pragma: no cover
        _PIPELINE = _PIPELINE.to(target_device)

    return _PIPELINE

def _require_flux_model_readiness(settings) -> None:
    if settings.flux_local_path or settings.hf_token_present:
        return
    raise T2IEngineUnavailableError(
        "FLUX local lane requires HF_TOKEN/HUGGINGFACE_TOKEN or EASYADS_FLUX_LOCAL_PATH."
    )
