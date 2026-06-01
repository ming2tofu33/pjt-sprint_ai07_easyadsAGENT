"""Shared helpers for guarded T2I execution lanes."""

from __future__ import annotations


TEXT_FREE_PROMPT_SUFFIX = (
    "Do not include any text, letters, numbers, Hangul, Korean characters, logos, "
    "watermarks, captions, signage, or typography. Leave clean negative space for "
    "Korean text overlay in post-processing."
)

TEXT_FREE_NEGATIVE_PROMPT = "text, letters, numbers, Hangul, Korean characters, logo, watermark, typography, caption, signage"


def build_generation_job_prompt(user_input: str) -> str:
    return f"Create a clean advertising background for the following request:\n{user_input.strip()}\n\n{TEXT_FREE_PROMPT_SUFFIX}"


def prompt_summary(prompt: str, negative_prompt: str, engine: str) -> dict[str, object]:
    return {
        "engine": engine,
        "prompt_preview": " ".join(prompt.split())[:180],
        "negative_prompt_terms": [term.strip() for term in negative_prompt.split(",") if term.strip()],
        "render_text_in_image": False,
        "must_not_include_text": True,
    }
