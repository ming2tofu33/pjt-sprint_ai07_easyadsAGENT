"""Plan image generation prompts from TLFP reserved text areas."""

from __future__ import annotations

from orchestrator.app.graph.state import MarketingState, context_to_model
from orchestrator.app.llm.node_runner import run_structured_node
from orchestrator.app.schemas.llm_marketing import ImagePrompt
from orchestrator.app.schemas.text_layout import ImagePromptSpec, NormalizedBBox, TextLayoutSpec
from orchestrator.app.t2i.prompts import COMMON_NEGATIVE_PROMPT


TEXT_NEGATIVE = (
    "text, letters, typography, words, captions, subtitles, alphabets, numbers, "
    "korean characters, hangul, watermark, logo, signature, cluttered background "
    "in reserved areas, busy pattern in negative space"
)


def image_prompt_planner_node(state: MarketingState) -> dict[str, object]:
    deterministic = lambda: build_deterministic_image_prompt_spec(state)
    spec_output, llm_metadata = run_structured_node(
        state,
        node_name="image_prompt_planner",
        output_schema=ImagePromptSpec,
        prompt=build_image_prompt_planner_prompt(state),
        fallback_fn=deterministic,
        risk_level="medium",
        confidence=0.5,
        latency_budget="standard",
        metadata={"prompt_summary": "image prompt planning"},
    )
    spec = enforce_image_prompt_safety(state, spec_output if isinstance(spec_output, ImagePromptSpec) else deterministic())
    image_prompt = build_legacy_image_prompt(state, spec)
    return {
        "image_prompt_spec": spec.model_dump(),
        "image_prompt": image_prompt.model_dump(),
        "current_brief": {
            **state.get("current_brief", {}),
            "image_prompt_spec_ready": True,
            "render_text_in_image": False,
        },
        "model_selections": state.get("model_selections", []),
        "llm_call_results": state.get("llm_call_results", []),
        "status": "optimizing_prompt",
    }


def build_deterministic_image_prompt_spec(state: MarketingState) -> ImagePromptSpec:
    context = context_to_model(state.get("context"))
    ad_format_spec = state.get("ad_format_spec") or {}
    reference_style_profile = state.get("reference_style_profile") or {}
    product_preserve_spec = state.get("product_preserve_spec") or {}
    text_layout = TextLayoutSpec(**(state.get("text_layout_spec") or {}))
    subject = context.item_or_service or "advertising subject"
    reserved_text = " and ".join(bbox_to_natural_language(bbox) for bbox in text_layout.reserved_text_areas)
    scene = f"clean commercial advertising background for {subject}"
    composition = build_composition(reserved_text)
    style_hint = reference_style_profile.get("ad_style_prompt")
    product_hint = build_product_preserve_hint(product_preserve_spec)
    extra_hints = " ".join(hint for hint in [style_hint, product_hint] if hint)
    positive = (
        f"Create a {scene}. {composition} Do not place the main subject inside the reserved text zones. "
        "The image will receive Korean text overlay later."
    )
    if extra_hints:
        positive = f"{positive} Use this additional visual guidance: {extra_hints}"
    negative = f"{TEXT_NEGATIVE}, {COMMON_NEGATIVE_PROMPT}"
    spec = ImagePromptSpec(
        scene_description=scene,
        product_subject=subject,
        color_palette=reference_style_profile.get("color_palette") or [],
        composition=composition,
        lighting=lighting_for_business(context.business_type),
        reserved_text_areas=text_layout.reserved_text_areas,
        positive_prompt_en=positive,
        negative_prompt_en=negative,
        target_width=int(ad_format_spec.get("width") or text_layout.canvas_width),
        target_height=int(ad_format_spec.get("height") or text_layout.canvas_height),
        aspect_ratio=str(ad_format_spec.get("aspect_ratio") or "1:1"),
        metadata={
            "render_text_in_image": False,
            "tlfp_enabled": True,
            "source_node": "image_prompt_planner",
            "reference_style_profile": reference_style_profile or None,
            "product_preserve_spec": product_preserve_spec or None,
            "vision_pipeline_enabled": bool(reference_style_profile or product_preserve_spec),
        },
    )
    return spec


def build_legacy_image_prompt(state: MarketingState, spec: ImagePromptSpec) -> ImagePrompt:
    subject = spec.product_subject
    image_prompt = ImagePrompt(
        subject=subject,
        style="clean commercial advertising background",
        lighting=spec.lighting,
        composition=spec.composition,
        copy_space=infer_copy_space_from_reserved_areas(spec.reserved_text_areas),
        negative_prompt=spec.negative_prompt_en or TEXT_NEGATIVE,
        scene=spec.scene_description,
        avoid_text=True,
        metadata={"render_text_in_image": False, "tlfp_enabled": True},
    )
    return image_prompt


def enforce_image_prompt_safety(state: MarketingState, spec: ImagePromptSpec) -> ImagePromptSpec:
    ad_format_spec = state.get("ad_format_spec") or {}
    text_layout = TextLayoutSpec(**(state.get("text_layout_spec") or {}))
    negative = spec.negative_prompt_en or ""
    required_terms = ["text", "letters", "numbers", "hangul", "watermark", "logo"]
    missing_terms = [term for term in required_terms if term not in negative.lower()]
    if missing_terms:
        negative = f"{negative}, {TEXT_NEGATIVE}".strip(", ")
    return spec.model_copy(
        update={
            "reserved_text_areas": text_layout.reserved_text_areas,
            "must_not_include_text": True,
            "negative_prompt_en": negative,
            "target_width": int(ad_format_spec.get("width") or text_layout.canvas_width),
            "target_height": int(ad_format_spec.get("height") or text_layout.canvas_height),
            "metadata": {**spec.metadata, "render_text_in_image": False, "tlfp_enabled": True, "safety_enforced": True},
        }
    )


def build_image_prompt_planner_prompt(state: MarketingState) -> str:
    context = context_to_model(state.get("context"))
    text_layout = state.get("text_layout_spec") or {}
    style = state.get("text_style_spec") or {}
    reference_style_profile = state.get("reference_style_profile") or {}
    product_preserve_spec = state.get("product_preserve_spec") or {}
    return (
        "Create a structured ImagePromptSpec for a text-free advertising background. "
        f"subject={context.item_or_service}, business_type={context.business_type}, brand_tone={context.brand_tone}. "
        f"reserved_text_areas={text_layout.get('reserved_text_areas', [])}, style_profile={style.get('profile')}. "
        f"reference_style_stub={reference_style_profile.get('ad_style_prompt')}, product_preserve_stub={product_preserve_spec.get('product_bbox')}. "
        "Keep all text areas clean; do not include text, letters, numbers, Hangul, logos, or watermarks."
    )


def bbox_to_natural_language(bbox: NormalizedBBox) -> str:
    center_x = bbox.x + bbox.w / 2
    center_y = bbox.y + bbox.h / 2
    vertical = "upper" if center_y < 0.33 else "middle" if center_y < 0.66 else "lower"
    horizontal = "left" if center_x < 0.33 else "center" if center_x < 0.66 else "right"
    size = "small" if bbox.area_ratio() < 0.08 else "medium" if bbox.area_ratio() < 0.18 else "large"
    return f"a {size} clean empty area in the {vertical} {horizontal} region"


def infer_copy_space_from_reserved_areas(reserved_areas: list[NormalizedBBox]) -> str:
    if not reserved_areas:
        return "none"
    first = reserved_areas[0]
    center_x = first.x + first.w / 2
    center_y = first.y + first.h / 2
    if center_y < 0.33:
        if center_x < 0.33:
            return "top_left"
        if center_x > 0.66:
            return "top_right"
        return "top"
    if center_y > 0.66:
        if center_x < 0.33:
            return "bottom_left"
        if center_x > 0.66:
            return "bottom_right"
        return "bottom"
    if center_x < 0.33:
        return "left"
    if center_x > 0.66:
        return "right"
    return "center"


def build_composition(reserved_text: str) -> str:
    if not reserved_text:
        return "Use a clean product-focused composition with no text and no typography."
    return (
        f"Reserve {reserved_text} as uncluttered negative space for Korean text overlay in post-processing. "
        "Keep those regions calm, simple, and free of visual clutter."
    )


def build_product_preserve_hint(product_preserve_spec: dict[str, object]) -> str | None:
    bbox = product_preserve_spec.get("product_bbox") if product_preserve_spec else None
    if not isinstance(bbox, dict):
        return None
    return f"Keep the main product visually centered around the source product bbox hint {bbox}; this is a non-segmentation stub."


def lighting_for_business(business_type: str | None) -> str:
    if business_type == "restaurant":
        return "warm commercial lighting with appetizing highlights"
    if business_type == "cafe":
        return "soft daylight with cozy warm accents"
    return "clean commercial lighting"
