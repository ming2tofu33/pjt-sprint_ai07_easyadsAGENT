"""Plan image generation prompts from TLFP reserved text areas."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from orchestrator.app.llm.metadata_builders import build_image_prompt_planner_metadata, metadata_contract_to_prompt_json
from orchestrator.app.llm.node_runner import run_structured_node
from orchestrator.app.llm.visual_templates import select_visual_template
from orchestrator.app.schemas.llm_marketing import ImagePrompt, MarketingContext
from orchestrator.app.schemas.text_layout import ImagePromptSpec, NormalizedBBox, TextLayoutSpec
from orchestrator.app.t2i.prompts import COMMON_NEGATIVE_PROMPT
from orchestrator.app.llm.scene_planner import build_scene_plan, build_prompt_quality_policy
from orchestrator.app.llm.prompt_adapters import render_engine_prompt
from orchestrator.app.llm.visual_presets import select_visual_preset
from orchestrator.app.llm.nodes.prompt_critic import critique_prompt_draft
from orchestrator.app.llm.prompt_rewrite_resolver import resolve_prompt_rewrite

if TYPE_CHECKING:
    from orchestrator.app.graph.state import MarketingState


TEXT_NEGATIVE = (
    "text, letters, typography, words, captions, subtitles, alphabets, numbers, "
    "korean characters, hangul, watermark, logo, signature, cluttered background "
    "in reserved areas, busy pattern in negative space"
)


def image_prompt_planner_node(state: "MarketingState") -> dict[str, object]:
    spec = build_image_prompt_spec_with_critic(state)
    spec = enforce_image_prompt_safety(state, spec)
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


def build_image_prompt_spec_with_critic(state: MarketingState) -> ImagePromptSpec:
    context = context_to_model(state.get("context"))
    ad_format_spec = state.get("ad_format_spec") or {}
    reference_style_profile = state.get("reference_style_profile") or {}
    product_preserve_spec = state.get("product_preserve_spec") or {}
    selected_reference_template = state.get("selected_reference_template") or {}
    reference_template_selection = state.get("reference_template_selection") or {}
    template_style_hint = reference_template_selection.get("style_profile_hint") or {}
    text_layout = TextLayoutSpec(**(state.get("text_layout_spec") or {}))
    subject = context.item_or_service or "advertising subject"
    visual_direction = selected_visual_direction(state)
    selected_tone = selected_tone_label(state)
    style_profile = (state.get("text_style_spec") or {}).get("profile")
    visual_template = select_visual_template(context.business_type, ad_format_spec.get("ad_format"), style_profile or selected_tone, selected_reference_template)
    reserved_text = " and ".join(bbox_to_natural_language(bbox) for bbox in text_layout.reserved_text_areas)
    scene = f"clean commercial advertising background for {subject}; {visual_template.background_style}"
    if visual_direction:
        scene = f"{scene}; follow this user visual direction: {visual_direction}"
    composition = f"{visual_template.composition}. {build_composition(reserved_text)} Main subject zone: {visual_template.main_subject_zone}."
    style_hint = reference_style_profile.get("ad_style_prompt")
    template_hint = build_reference_template_hint(selected_reference_template, template_style_hint)
    product_hint = build_product_preserve_hint(product_preserve_spec)
    user_tone_hint = f"Reflect this user-selected mood/tone: {selected_tone}." if selected_tone else None
    user_direction_hint = f"Prioritize this user-provided visual direction: {visual_direction}." if visual_direction else None
    extra_hints = " ".join(hint for hint in [style_hint, template_hint, product_hint, user_tone_hint, user_direction_hint] if hint)
    positive = (
        f"Create a {scene}. {composition} "
        "Create a clean advertising background. "
        "Reserve clean negative space for Korean text overlay in post-processing. "
        "Keep reserved text areas uncluttered and low contrast. "
        "Place the main subject away from reserved text areas. "
        "Do not place the main subject inside the reserved text zones. "
        "The image will receive Korean text overlay later. "
        f"Use visual template {visual_template.template_id}: {', '.join(visual_template.prompt_phrases)}."
    )
    if extra_hints:
        positive = f"{positive} Use this additional visual guidance: {extra_hints}"
    negative = f"{TEXT_NEGATIVE}, {', '.join(visual_template.negative_prompt_additions)}, {COMMON_NEGATIVE_PROMPT}"

    # ImagePrompt v3: ScenePlan / QualityPolicy / PromptAdapter 빌드
    context_dict = state.get("context") or {}
    if hasattr(context_dict, "model_dump"):
        context_dict = context_dict.model_dump()
    user_input = (
        state.get("user_input")
        or context_dict.get("user_input")
        or (state.get("current_brief") or {}).get("user_input")
        or ""
    )
    scene_plan = build_scene_plan(
        user_input=user_input,
        business_type=context.business_type,
        ad_format=ad_format_spec.get("ad_format"),
        selected_reference_template=selected_reference_template,
        reference_template_selection=reference_template_selection,
        metadata={
            "business_type": context.business_type,
            "item_or_service": context.item_or_service,
            "target_persona": context.target_persona,
            "promotion_goal": context.promotion_goal,
        }
    )
    preset = select_visual_preset(
        business_type=scene_plan.business_type,
        ad_format=scene_plan.ad_format,
        selected_reference_template=selected_reference_template
    )
    preset_id = preset["preset_id"]
    policy = build_prompt_quality_policy(preset)
    engine = state.get("engine") or "gpt_image_2"
    adapter_output = render_engine_prompt(engine, scene_plan, policy, preset_id=preset_id)
    adapter_positive_prompt = adapter_output.prompt
    if extra_hints:
        adapter_positive_prompt = f"{adapter_positive_prompt} Additional visual/reference guidance: {extra_hints}"

    adapter_negative_prompt = adapter_output.negative_prompt or negative
    prompt_context = build_prompt_critic_context(
        state=state,
        context=context,
        ad_format_spec=ad_format_spec,
        scene_plan=scene_plan,
        policy=policy,
        preset_id=preset_id,
        selected_reference_template=selected_reference_template,
        reference_template_selection=reference_template_selection,
    )
    critic_output, critic_metadata = critique_prompt_draft(
        state,
        prompt_draft=adapter_positive_prompt,
        target_engine=adapter_output.engine,
        prompt_context=prompt_context,
    )
    rewrite_resolution = resolve_prompt_rewrite(
        adapter_positive_prompt,
        critic_output,
        prompt_context,
        quality_policy=policy,
    )
    adapter_positive_prompt = rewrite_resolution.prompt
    issue_codes = [issue.code for issue in critic_output.issues] if critic_output else []
    prompt_critic_metadata = {
        "enabled": bool(critic_metadata.get("enabled", True)),
        "attempted": bool(critic_metadata.get("llm_attempted") or critic_metadata.get("attempted")),
        "success": bool(critic_output),
        "provider": critic_metadata.get("provider"),
        "selected_model_class": critic_metadata.get("selected_model_class"),
        "quality_score": critic_output.quality_score if critic_output else None,
        "issue_codes": issue_codes,
        "rewrite_applied": rewrite_resolution.rewrite_applied,
        "rejected_change_codes": rewrite_resolution.rejected_change_codes,
        "fallback_used": bool(critic_metadata.get("fallback_used") or rewrite_resolution.fallback_used),
        "fallback_reason": critic_metadata.get("fallback_reason") or rewrite_resolution.fallback_reason,
    }
    adapter_output = adapter_output.model_copy(
        update={
            "prompt": adapter_positive_prompt,
            "metadata": {**adapter_output.metadata, "prompt_critic": prompt_critic_metadata},
        }
    )

    spec = ImagePromptSpec(
        scene_description=scene,
        product_subject=subject,
        color_palette=reference_style_profile.get("color_palette") or template_style_hint.get("color_palette") or visual_template.color_palette_hint,
        composition=composition,
        lighting=visual_template.lighting or lighting_for_business(context.business_type),
        reserved_text_areas=text_layout.reserved_text_areas,
        positive_prompt_en=adapter_positive_prompt,
        negative_prompt_en=adapter_negative_prompt,
        target_width=int(ad_format_spec.get("width") or text_layout.canvas_width),
        target_height=int(ad_format_spec.get("height") or text_layout.canvas_height),
        aspect_ratio=str(ad_format_spec.get("aspect_ratio") or "1:1"),
        metadata={
            "render_text_in_image": False,
            "tlfp_enabled": True,
            "source_node": "image_prompt_planner",
            "reference_style_profile": reference_style_profile or None,
            "selected_reference_template": selected_reference_template or None,
            "reference_template_selection": reference_template_selection or None,
            "product_preserve_spec": product_preserve_spec or None,
            "selected_channel_id": (state.get("current_brief") or {}).get("selected_channel_id") or context.extra.get("selected_channel_id"),
            "selected_tone": selected_tone,
            "custom_direction": visual_direction,
            "visual_template_id": visual_template.template_id,
            "visual_template": {
                "main_subject_zone": visual_template.main_subject_zone,
                "reserved_text_area_policy": visual_template.reserved_text_area_policy,
                "background_style": visual_template.background_style,
                "color_palette_hint": visual_template.color_palette_hint,
            },
            "vision_pipeline_enabled": bool(reference_style_profile or product_preserve_spec or selected_reference_template),
            "image_prompt_version": "v3",
            "scene_plan": scene_plan.model_dump(mode="json"),
            "prompt_quality_policy": policy.model_dump(mode="json"),
            "prompt_adapter": adapter_output.model_dump(mode="json"),
            "prompt_critic": prompt_critic_metadata,
            "business_visual_preset_id": preset_id,
            "beauty_subtype": scene_plan.business_type if scene_plan.business_type.startswith("beauty_") else None,
        },
    )
    return spec


def build_legacy_image_prompt(state: MarketingState, spec: ImagePromptSpec) -> ImagePrompt:
    subject = spec.product_subject
    v3_meta = {}
    for key in ["image_prompt_version", "scene_plan", "prompt_quality_policy", "prompt_adapter", "business_visual_preset_id", "beauty_subtype"]:
        if key in spec.metadata:
            v3_meta[key] = spec.metadata[key]

    image_prompt = ImagePrompt(
        subject=subject,
        style="clean commercial advertising background",
        lighting=spec.lighting,
        composition=spec.composition,
        copy_space=infer_copy_space_from_reserved_areas(spec.reserved_text_areas),
        negative_prompt=spec.negative_prompt_en or TEXT_NEGATIVE,
        scene=spec.scene_description,
        avoid_text=True,
        metadata={"render_text_in_image": False, "tlfp_enabled": True, **v3_meta},
    )
    return image_prompt


def build_prompt_critic_context(
    *,
    state: MarketingState,
    context: MarketingContext,
    ad_format_spec: dict[str, Any],
    scene_plan: Any,
    policy: Any,
    preset_id: str,
    selected_reference_template: dict[str, Any],
    reference_template_selection: dict[str, Any],
) -> dict[str, Any]:
    return {
        "business_type": context.business_type,
        "business_subtype": scene_plan.business_type,
        "item_or_service": context.item_or_service,
        "primary_subject": scene_plan.primary_subject,
        "ad_format": ad_format_spec.get("ad_format") or scene_plan.ad_format,
        "promotion_goal": context.promotion_goal,
        "visual_style": selected_tone_label(state),
        "scene_plan": {
            "business_type": scene_plan.business_type,
            "primary_subject": scene_plan.primary_subject,
            "composition_archetype": scene_plan.composition_archetype,
            "reserved_copy_area": scene_plan.reserved_copy_area,
            "fake_text_risk_level": scene_plan.fake_text_risk_level,
        },
        "prompt_quality_policy": {
            "no_text_policy": policy.no_text_policy,
            "safe_area_policy": policy.safe_area_policy,
            "fake_text_negative_terms_count": len(policy.fake_text_negative_terms),
        },
        "business_visual_preset_id": preset_id,
        "selected_reference_template_id": selected_reference_template.get("template_id") or state.get("selected_reference_template_id"),
        "reference_alignment": reference_template_selection.get("style_profile_hint") or None,
        "copy_safe_area_required": True,
        "render_text_in_image": False,
    }


def selected_visual_direction(state: MarketingState) -> str | None:
    context = context_to_model(state.get("context"))
    current_brief = state.get("current_brief") or {}
    return clean_optional_text(current_brief.get("custom_direction") or context.extra.get("custom_direction") or state.get("custom_direction"))


def selected_tone_label(state: MarketingState) -> str | None:
    context = context_to_model(state.get("context"))
    current_brief = state.get("current_brief") or {}
    return clean_optional_text(current_brief.get("selected_tone") or context.extra.get("selected_tone") or state.get("selected_tone") or context.brand_tone)


def clean_optional_text(value: object | None) -> str | None:
    if value is None:
        return None
    stripped = str(value).strip()
    return stripped or None


def enforce_image_prompt_safety(state: MarketingState, spec: ImagePromptSpec) -> ImagePromptSpec:
    ad_format_spec = state.get("ad_format_spec") or {}
    text_layout = TextLayoutSpec(**(state.get("text_layout_spec") or {}))
    negative = spec.negative_prompt_en or ""
    required_terms = ["text", "letters", "numbers", "hangul", "korean characters", "watermark", "logo", "typography", "caption", "signage"]
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


def build_image_prompt_planner_prompt(state: MarketingState, metadata_contract: dict[str, object] | None = None) -> str:
    context = context_to_model(state.get("context"))
    text_layout = state.get("text_layout_spec") or {}
    style = state.get("text_style_spec") or {}
    reference_style_profile = state.get("reference_style_profile") or {}
    product_preserve_spec = state.get("product_preserve_spec") or {}
    selected_reference_template = state.get("selected_reference_template") or {}
    visual_direction = selected_visual_direction(state)
    selected_tone = selected_tone_label(state)
    metadata_contract = metadata_contract or build_image_prompt_planner_metadata(state)
    return (
        "Create a structured ImagePromptSpec for a text-free advertising background. "
        f"subject={context.item_or_service}, business_type={context.business_type}, brand_tone={context.brand_tone}. "
        f"user_selected_tone={selected_tone}, user_visual_direction={visual_direction}. "
        f"reserved_text_areas={text_layout.get('reserved_text_areas', [])}, style_profile={style.get('profile')}. "
        f"reference_style_stub={reference_style_profile.get('ad_style_prompt')}, "
        f"reference_template={selected_reference_template.get('title')}, product_preserve_stub={product_preserve_spec.get('product_bbox')}. "
        f"metadata_contract={metadata_contract_to_prompt_json(metadata_contract)}. "
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
    return (
        "Use the uploaded source image as the product reference. Preserve the main product's visual identity, "
        f"shape, color, and approximate position around normalized bbox {bbox}; create a polished advertising "
        "scene around it while keeping the reserved text areas clean."
    )


def build_reference_template_hint(template: dict[str, object], style_hint: dict[str, object]) -> str | None:
    if not template and not style_hint:
        return None
    title = template.get("title") or "selected reference template"
    keywords = style_hint.get("style_keywords") or template.get("style_keywords") or []
    palette = style_hint.get("color_palette") or template.get("color_palette") or []
    layout = style_hint.get("layout_hint") or template.get("layout_hint")
    background = style_hint.get("background_style") or template.get("background_style")
    return f"Use reference template '{title}' as metadata-only style guidance: keywords={keywords}, palette={palette}, layout={layout}, background={background}."


def lighting_for_business(business_type: str | None) -> str:
    if business_type == "restaurant":
        return "warm commercial lighting with appetizing highlights"
    if business_type == "cafe":
        return "soft daylight with cozy warm accents"
    return "clean commercial lighting"


def context_to_model(context: dict[str, Any] | MarketingContext | None) -> MarketingContext:
    if isinstance(context, MarketingContext):
        return context
    return MarketingContext(**(context or {}))
