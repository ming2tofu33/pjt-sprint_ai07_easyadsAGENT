"""Render structured image prompts into engine-specific prompt strings."""

from __future__ import annotations

from typing import Any

from orchestrator.app.schemas.llm_marketing import GenerationEngine, ImagePrompt, PromptRenderOutput, RenderProfile
from orchestrator.app.schemas.text_layout import ImagePromptSpec


NO_TEXT_CLAUSE = "no text, no watermark, no logo, no letters, no numbers"


def render_prompt_for_engine(
    image_prompt: ImagePrompt | dict[str, Any],
    engine: GenerationEngine,
    width: int = 1024,
    height: int = 1024,
    render_profile: RenderProfile = "balanced",
    metadata: dict[str, Any] | None = None,
) -> PromptRenderOutput:
    prompt = image_prompt if isinstance(image_prompt, ImagePrompt) else ImagePrompt(**image_prompt)
    metadata = dict(metadata or {})
    prompt_adapter = prompt.metadata.get("prompt_adapter") if isinstance(prompt.metadata, dict) else None
    if isinstance(prompt_adapter, dict):
        adapter_prompt = prompt_adapter.get("prompt")
        adapter_negative_prompt = prompt_adapter.get("negative_prompt")
        if adapter_prompt:
            return PromptRenderOutput(
                engine=engine,
                positive_prompt=adapter_prompt,
                negative_prompt=adapter_negative_prompt or prompt.negative_prompt,
                render_profile=render_profile,
                render_notes=["Using ImagePrompt v3 prompt_adapter output."],
                width=width,
                height=height,
                metadata={**metadata, "render_text_in_image": False, "prompt_adapter_used": True},
            )

    base = ", ".join(
        [
            prompt.subject,
            prompt.style,
            prompt.lighting,
            prompt.composition,
            f"copy space: {prompt.copy_space}",
        ]
    )
    notes: list[str] = []
    negative_prompt = prompt.negative_prompt
    if engine == "mock":
        positive_prompt = f"{prompt.subject}, {prompt.composition}"
        notes.append("Mock renderer keeps prompt short and preserves negative prompt.")
    elif engine == "sd35_large":
        positive_prompt = base
        notes.append("SD3.5 renderer separates positive and negative prompts.")
    elif engine == "flux":
        positive_prompt = f"{base}, {NO_TEXT_CLAUSE}"
        notes.append("FLUX may underweight negative prompts; no-text constraints are repeated in positive prompt.")
    elif engine in {"gpt_image_1", "gpt_image_2"}:
        positive_prompt = (
            "Create a text-free advertising background for later Korean copy overlay. "
            f"Subject: {prompt.subject}. Style: {prompt.style}. Lighting: {prompt.lighting}. "
            f"Composition: {prompt.composition}. Do not create text, logos, labels, or watermarks."
        )
        notes.append("GPT-image renderer uses a creative brief style prompt.")
    else:  # pragma: no cover - protected by Literal typing
        positive_prompt = base

    return PromptRenderOutput(
        engine=engine,
        positive_prompt=positive_prompt,
        negative_prompt=negative_prompt,
        render_profile=render_profile,
        render_notes=notes,
        width=width,
        height=height,
        metadata={**metadata, "render_text_in_image": False},
    )


def render_prompt_spec_for_engine(
    image_prompt_spec: ImagePromptSpec | dict[str, Any],
    engine: GenerationEngine,
    render_profile: RenderProfile = "balanced",
    metadata: dict[str, Any] | None = None,
) -> PromptRenderOutput:
    spec = image_prompt_spec if isinstance(image_prompt_spec, ImagePromptSpec) else ImagePromptSpec(**image_prompt_spec)
    metadata = dict(metadata or {})
    positive_prompt = spec.positive_prompt_en or spec.scene_description
    negative_prompt = spec.negative_prompt_en
    notes = ["TLFP ImagePromptSpec is used as the primary prompt source."]
    if engine == "flux":
        positive_prompt = f"{positive_prompt} no text, no watermark, no logo, no letters, no numbers"
        notes.append("FLUX receives no-text constraints in the positive prompt as well.")
    elif engine in {"gpt_image_1", "gpt_image_2"}:
        positive_prompt = (
            "Create a text-free advertising background for later Korean copy overlay. "
            f"{positive_prompt} Do not create text, labels, logos, or watermarks."
        )
        notes.append("GPT-image receives a creative brief style TLFP prompt.")
    elif engine == "sd35_large":
        notes.append("SD3.5 receives separated positive and negative TLFP prompts.")
    else:
        notes.append("Mock renderer keeps TLFP prompt text unchanged.")
    return PromptRenderOutput(
        engine=engine,
        positive_prompt=positive_prompt,
        negative_prompt=negative_prompt,
        render_profile=render_profile,
        render_notes=notes,
        width=spec.target_width,
        height=spec.target_height,
        metadata={
            **metadata,
            "aspect_ratio": spec.aspect_ratio,
            "reserved_text_areas": [bbox.model_dump() for bbox in spec.reserved_text_areas],
            "render_text_in_image": False,
            "tlfp_enabled": True,
        },
    )
