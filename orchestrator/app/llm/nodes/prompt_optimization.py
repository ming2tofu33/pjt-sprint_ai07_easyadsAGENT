"""Prompt optimization node for text-free ad background generation."""

from __future__ import annotations

from typing import Any

from orchestrator.app.graph.state import MarketingState, context_to_model
from orchestrator.app.schemas.llm_marketing import ImagePrompt, PromptOptimizationOutput, UserReadableImageGuide
from orchestrator.app.t2i.prompts import resolve_negative_prompt


BUSINESS_STYLE = {
    "restaurant": "professional commercial food photography, appetizing, realistic",
    "cafe": "cozy cafe commercial photography, clean dessert styling",
    "beauty_salon": "polished beauty salon advertising background, elegant and clean",
    "fitness": "energetic fitness advertising background, clean studio lighting",
    "flower_shop": "fresh floral commercial photography, soft elegant mood",
}

BUSINESS_LIGHTING = {
    "restaurant": "warm commercial lighting with natural highlights",
    "cafe": "soft daylight with cozy warm accents",
    "beauty_salon": "clean softbox lighting with gentle highlights",
    "fitness": "bright studio lighting with crisp contrast",
    "flower_shop": "soft natural light with fresh color balance",
}


def prompt_optimization_node(state: MarketingState) -> dict[str, Any]:
    context = context_to_model(state.get("context"))
    layout_spec = state.get("layout_spec") or {}
    marketing_copy = state.get("marketing_copy") or {}
    copy_space = layout_spec.get("copy_space", "bottom")
    subject = context.item_or_service or "advertising subject"
    business_type = context.business_type or "store"
    style = build_style(business_type, context.brand_tone)
    lighting = BUSINESS_LIGHTING.get(business_type, "clean commercial lighting")
    composition = f"text-free advertising background with clear {copy_space} copy space for later Korean overlay"
    negative_prompt = resolve_negative_prompt(
        "hallucinated text, fake logo, unreadable letters, fake watermark",
        {"business_type": business_type},
    )
    image_prompt = ImagePrompt(
        subject=subject,
        style=style,
        lighting=lighting,
        composition=composition,
        copy_space=copy_space,
        negative_prompt=negative_prompt,
        scene=f"{subject} commercial advertising background",
        avoid_text=True,
        metadata={
            "render_text_in_image": False,
            "must_avoid": ["hallucinated text", "fake logo", "unreadable letters"],
            "headline_for_overlay": marketing_copy.get("headline"),
            "source_node": "prompt_optimization",
        },
    )
    guide = UserReadableImageGuide(
        summary=f"{subject}을 중심으로, 광고 문구를 나중에 얹을 수 있는 텍스트 없는 배경을 생성합니다.",
        subject_ko=subject,
        mood_ko=style,
        composition_ko=f"{copy_space} 영역을 문구 합성 공간으로 비워둡니다.",
        copy_space_ko=str(copy_space),
        style_keywords=[business_type, "text_free", "commercial"],
        copy_space=copy_space,
        warnings=["이미지 안에는 글자, 로고, 워터마크를 만들지 않습니다."],
    )
    output = PromptOptimizationOutput(
        image_prompt=image_prompt,
        user_readable_image_guide=guide,
        negative_prompt=negative_prompt,
        rationale="Rule-based v1 prompt optimization; no LLM call was made.",
    )
    return {
        "image_prompt": image_prompt.model_dump(),
        "user_readable_image_guide": guide.model_dump(),
        "prompt_optimization_output": output.model_dump(),
        "status": "optimizing_prompt",
    }


def build_style(business_type: str, brand_tone: str | None) -> str:
    base = BUSINESS_STYLE.get(business_type, "clean commercial advertising background")
    if brand_tone:
        return f"{base}, {brand_tone} brand tone"
    return base
