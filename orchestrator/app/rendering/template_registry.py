from typing import Any
from pydantic import BaseModel, Field

class TemplateDefinition(BaseModel):
    template_id: str
    preset_name: str
    supported_aspect_ratios: list[str]
    supported_components: list[str]
    optional_components: list[str] = Field(default_factory=list)
    default_component_order: list[str]
    description: str
    fallback_template_id: str

REGISTRY: dict[str, TemplateDefinition] = {
    "center_stack_basic": TemplateDefinition(
        template_id="center_stack_basic",
        preset_name="center_stack",
        supported_aspect_ratios=["1:1", "4:5", "9:16"],
        supported_components=["headline_block", "subcopy_block", "footer_panel"],
        optional_components=["decorative_sticker", "memo_card", "speech_bubble", "icon_feature_list"],
        default_component_order=["headline_block", "subcopy_block", "footer_panel"],
        description="Center stacked layout for clear backgrounds",
        fallback_template_id="center_stack_basic"
    ),
    "top_headline_footer_basic": TemplateDefinition(
        template_id="top_headline_footer_basic",
        preset_name="top_headline_footer",
        supported_aspect_ratios=["1:1", "4:5", "9:16"],
        supported_components=["headline_block", "subcopy_block", "footer_panel"],
        optional_components=["decorative_sticker", "memo_card", "speech_bubble", "icon_feature_list"],
        default_component_order=["headline_block", "subcopy_block", "footer_panel"],
        description="Top headline with bottom footer for bottom-heavy subjects",
        fallback_template_id="center_stack_basic"
    ),
    "editorial_left_basic": TemplateDefinition(
        template_id="editorial_left_basic",
        preset_name="editorial_left",
        supported_aspect_ratios=["1:1", "4:5", "9:16"],
        supported_components=["headline_block", "subcopy_block", "footer_panel"],
        optional_components=["decorative_sticker", "memo_card", "speech_bubble", "icon_feature_list"],
        default_component_order=["headline_block", "subcopy_block", "footer_panel"],
        description="Left-aligned editorial text for right-positioned subjects",
        fallback_template_id="center_stack_basic"
    ),
    "hero_center_basic": TemplateDefinition(
        template_id="hero_center_basic",
        preset_name="hero_center",
        supported_aspect_ratios=["1:1", "4:5", "9:16"],
        supported_components=["headline_block", "subcopy_block", "footer_panel"],
        optional_components=["decorative_sticker", "memo_card", "speech_bubble", "icon_feature_list"],
        default_component_order=["headline_block", "subcopy_block", "footer_panel"],
        description="Hero text in center for strong background subjects",
        fallback_template_id="center_stack_basic"
    )
}

def _check_template_compatibility(template: TemplateDefinition, aspect_ratio: str, components: list[str]) -> tuple[bool, list[str]]:
    unsupported = []
    
    # 1. Aspect ratio check
    if aspect_ratio != "unknown" and aspect_ratio not in template.supported_aspect_ratios:
        return False, ["aspect_ratio mismatch"]
        
    # 2. Components check
    allowed_comps = set(template.supported_components + template.optional_components)
    for c in components:
        role = c.get("type", "").replace("_block", "").replace("_panel", "")
        # role validation using raw type logic or mapped role
        raw_type = c.get("type", "")
        if raw_type not in allowed_comps:
            unsupported.append(raw_type)
            
    # For Phase 6, we allow optional components. But if there's an unsupported core component, we flag it.
    if unsupported:
        return False, unsupported
        
    return True, []

def get_template(template_id: str) -> TemplateDefinition | None:
    return REGISTRY.get(template_id)

def select_template(
    image_analysis: dict,
    planner_policy: dict,
    requested_template_id: str | None = None,
    components_to_render: list[dict[str, Any]] | None = None,
    aspect_ratio: str = "unknown"
) -> tuple[TemplateDefinition, dict]:
    """
    Selects the best template based on requested ID, image analysis, and policy.
    Returns the TemplateDefinition and diagnostics dict.
    """
    components = components_to_render or []
    
    diag = {
        "template_registry_used": True,
        "requested_template_id": requested_template_id,
        "selected_template_id": None,
        "selected_preset_name": None,
        "template_fallback_used": False,
        "template_fallback_reason": None,
        "supported_components": [],
        "optional_components": [],
        "unsupported_components": [],
        "template_policy_reason": None
    }
    
    selected = None
    
    # 1. Try requested_template_id
    if requested_template_id:
        tmpl = get_template(requested_template_id)
        if tmpl:
            is_compat, unsupp = _check_template_compatibility(tmpl, aspect_ratio, components)
            if is_compat:
                selected = tmpl
                diag["template_policy_reason"] = "Matched requested template"
            else:
                diag["template_fallback_used"] = True
                diag["template_fallback_reason"] = f"Requested template incompatible. Unsupported: {unsupp}"
                diag["unsupported_components"] = unsupp
        else:
            diag["template_fallback_used"] = True
            diag["template_fallback_reason"] = "Requested template not found in registry"
            
    # 2. Fallback to image-aware policy if not selected yet
    if not selected:
        # Determine preset name from planner_policy or image_analysis
        subject_position = image_analysis.get("subject_position", "center")
        safe_zone = image_analysis.get("safe_zone", "center")
        
        # Policy logic (from Phase 5.3) mapped to templates
        target_template_id = "center_stack_basic"
        
        if subject_position == "right" and safe_zone == "left":
            target_template_id = "editorial_left_basic"
        elif subject_position == "bottom" and safe_zone == "top":
            target_template_id = "top_headline_footer_basic"
        elif subject_position == "center":
            target_template_id = "hero_center_basic"
            
        tmpl = get_template(target_template_id)
        if tmpl:
            is_compat, unsupp = _check_template_compatibility(tmpl, aspect_ratio, components)
            if is_compat:
                selected = tmpl
                if not diag["template_policy_reason"]:
                    diag["template_policy_reason"] = f"Image-aware policy selected {target_template_id}"
            else:
                diag["template_fallback_used"] = True
                diag["template_fallback_reason"] = f"Policy template incompatible. Unsupported: {unsupp}"
                diag["unsupported_components"] = unsupp
        
    # 3. Final Fallback to center_stack_basic
    if not selected:
        selected = get_template("center_stack_basic")
        if not diag["template_policy_reason"]:
            diag["template_policy_reason"] = "Ultimate fallback applied"
            
    # Populate diagnostics
    if selected:
        diag["selected_template_id"] = selected.template_id
        diag["selected_preset_name"] = selected.preset_name
        diag["supported_components"] = selected.supported_components
        diag["optional_components"] = selected.optional_components
        
    return selected, diag
