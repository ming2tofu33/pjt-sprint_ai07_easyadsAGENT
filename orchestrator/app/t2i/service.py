"""Service-level T2I generation entrypoint."""

from __future__ import annotations

from uuid import uuid4

from orchestrator.app.core.config import get_t2i_settings
from orchestrator.app.t2i.prompts import (
    resolve_industry_key,
    resolve_negative_prompt,
    resolve_negative_prompt_sources,
)
from orchestrator.app.t2i.router import get_t2i_engine
from orchestrator.app.t2i.schemas import T2IRequest, T2IResult


def generate_image_v1(
    prompt: str,
    negative_prompt: str | None = None,
    engine_preference: str | None = None,
    width: int = 1024,
    height: int = 1024,
    seed: int | None = None,
    num_images: int = 1,
    metadata: dict | None = None,
) -> T2IResult:
    """Generate an image through the configured T2I engine with policy prompts."""
    settings = get_t2i_settings()
    metadata = dict(metadata or {})
    job_id = str(metadata.get("job_id") or uuid4())
    requested_engine = engine_preference or settings.default_engine
    effective_negative_prompt = resolve_negative_prompt(negative_prompt, metadata)
    output_dir = settings.output_dir / job_id
    output_dir.mkdir(parents=True, exist_ok=True)

    engine = get_t2i_engine(requested_engine)
    negative_prompt_sources = resolve_negative_prompt_sources(negative_prompt, metadata)
    resolved_business_type = resolve_industry_key(metadata.get("business_type"))
    request = T2IRequest(
        prompt=prompt,
        negative_prompt=effective_negative_prompt,
        width=width,
        height=height,
        seed=seed,
        num_images=num_images,
        output_dir=str(output_dir),
        metadata={
            **metadata,
            "job_id": job_id,
            "requested_engine": requested_engine,
            "effective_engine": engine.name,
            "effective_negative_prompt": effective_negative_prompt,
            "negative_prompt_sources": negative_prompt_sources,
            "business_type": metadata.get("business_type"),
            "resolved_business_type": resolved_business_type,
            "num_images": num_images,
        },
    )
    result = engine.generate(request)
    result.metadata.update(
        {
            "job_id": job_id,
            "requested_engine": requested_engine,
            "effective_engine": result.engine,
            "effective_negative_prompt": effective_negative_prompt,
            "negative_prompt_sources": negative_prompt_sources,
            "business_type": metadata.get("business_type"),
            "resolved_business_type": resolved_business_type,
            "num_images": num_images,
        }
    )
    return result