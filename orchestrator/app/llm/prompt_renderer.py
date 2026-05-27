"""Render structured image prompts into engine-specific prompt strings."""

from __future__ import annotations

from typing import Any

from orchestrator.app.schemas.llm_marketing import GenerationEngine, ImagePrompt, PromptRenderOutput, RenderProfile


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
    elif engine == "gpt_image_2":
        positive_prompt = (
            "Create a text-free advertising background for later Korean copy overlay. "
            f"Subject: {prompt.subject}. Style: {prompt.style}. Lighting: {prompt.lighting}. "
            f"Composition: {prompt.composition}. Do not create text, logos, labels, or watermarks."
        )
        notes.append("GPT-image-2 renderer uses a creative brief style prompt.")
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
