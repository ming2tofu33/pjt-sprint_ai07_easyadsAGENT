from typing import Any
from pydantic import BaseModel

class AssetDefinition(BaseModel):
    asset_id: str
    asset_type: str
    variant: str
    supported_components: list[str]
    supported_templates: list[str]
    render_mode: str
    external_asset: bool
    description: str
    fallback_asset_id: str | None = None

ASSET_REGISTRY: dict[str, AssetDefinition] = {
    # Stickers
    "sticker_underline_accent_basic": AssetDefinition(
        asset_id="sticker_underline_accent_basic",
        asset_type="decorative_sticker",
        variant="underline_accent",
        supported_components=["decorative_sticker"],
        supported_templates=["center_stack_basic", "hero_center_basic", "editorial_left_basic", "top_headline_footer_basic"],
        render_mode="pil_shape",
        external_asset=False,
        description="Basic underline accent sticker",
        fallback_asset_id="sticker_circle_badge_basic"
    ),
    "sticker_circle_badge_basic": AssetDefinition(
        asset_id="sticker_circle_badge_basic",
        asset_type="decorative_sticker",
        variant="circle_badge",
        supported_components=["decorative_sticker"],
        supported_templates=["center_stack_basic", "hero_center_basic", "editorial_left_basic", "top_headline_footer_basic"],
        render_mode="pil_shape",
        external_asset=False,
        description="Basic circle badge sticker",
        fallback_asset_id="sticker_starburst_basic"
    ),
    "sticker_starburst_basic": AssetDefinition(
        asset_id="sticker_starburst_basic",
        asset_type="decorative_sticker",
        variant="starburst",
        supported_components=["decorative_sticker"],
        supported_templates=["center_stack_basic", "hero_center_basic", "editorial_left_basic", "top_headline_footer_basic"],
        render_mode="pil_shape",
        external_asset=False,
        description="Basic starburst decorative sticker",
        fallback_asset_id=None
    ),
    
    # Icons
    "icon_check_basic": AssetDefinition(
        asset_id="icon_check_basic",
        asset_type="icon_feature_list",
        variant="check",
        supported_components=["icon_feature_list"],
        supported_templates=["center_stack_basic", "hero_center_basic", "editorial_left_basic", "top_headline_footer_basic"],
        render_mode="pil_shape",
        external_asset=False,
        description="Check icon",
        fallback_asset_id="icon_dot_basic"
    ),
    "icon_star_basic": AssetDefinition(
        asset_id="icon_star_basic",
        asset_type="icon_feature_list",
        variant="star",
        supported_components=["icon_feature_list"],
        supported_templates=["center_stack_basic", "hero_center_basic", "editorial_left_basic", "top_headline_footer_basic"],
        render_mode="pil_shape",
        external_asset=False,
        description="Star icon",
        fallback_asset_id="icon_dot_basic"
    ),
    "icon_heart_basic": AssetDefinition(
        asset_id="icon_heart_basic",
        asset_type="icon_feature_list",
        variant="heart",
        supported_components=["icon_feature_list"],
        supported_templates=["center_stack_basic", "hero_center_basic", "editorial_left_basic", "top_headline_footer_basic"],
        render_mode="pil_shape",
        external_asset=False,
        description="Heart icon",
        fallback_asset_id="icon_dot_basic"
    ),
    "icon_dot_basic": AssetDefinition(
        asset_id="icon_dot_basic",
        asset_type="icon_feature_list",
        variant="dot",
        supported_components=["icon_feature_list"],
        supported_templates=["center_stack_basic", "hero_center_basic", "editorial_left_basic", "top_headline_footer_basic"],
        render_mode="pil_shape",
        external_asset=False,
        description="Dot icon",
        fallback_asset_id=None
    ),
    "icon_number_basic": AssetDefinition(
        asset_id="icon_number_basic",
        asset_type="icon_feature_list",
        variant="number",
        supported_components=["icon_feature_list"],
        supported_templates=["center_stack_basic", "hero_center_basic", "editorial_left_basic", "top_headline_footer_basic"],
        render_mode="pil_text",
        external_asset=False,
        description="Number icon",
        fallback_asset_id="icon_dot_basic"
    ),
}

def get_asset(asset_id: str) -> AssetDefinition | None:
    return ASSET_REGISTRY.get(asset_id)

def get_asset_by_variant(asset_type: str, variant: str) -> AssetDefinition | None:
    for asset in ASSET_REGISTRY.values():
        if asset.asset_type == asset_type and asset.variant == variant:
            return asset
    return None

def _resolve_asset_with_fallback(initial_asset_id: str | None, asset_type: str, variant: str, template_id: str | None, max_depth: int = 2) -> tuple[AssetDefinition | None, dict]:
    diag = {
        "asset_registry_used": True,
        "requested_asset_id": initial_asset_id,
        "selected_asset_id": None,
        "asset_type": asset_type,
        "asset_variant": variant,
        "asset_fallback_used": False,
        "asset_fallback_reason": None,
        "external_asset": False,
        "unsupported_asset": False,
        "asset_policy_reason": None,
        "validation_warnings": []
    }
    
    current_asset_id = initial_asset_id
    
    if not current_asset_id and variant:
        # Try to infer from variant
        inferred = get_asset_by_variant(asset_type, variant)
        if inferred:
            current_asset_id = inferred.asset_id
        else:
            diag["validation_warnings"].append(f"No asset found for variant '{variant}'")
            return None, diag
            
    if not current_asset_id:
        # No asset requested or inferred, return early (backward compatibility path)
        diag["asset_registry_used"] = False
        return None, diag
        
    visited = set()
    depth = 0
    selected_asset = None
    
    while depth <= max_depth:
        asset = get_asset(current_asset_id)
        if not asset:
            diag["asset_fallback_used"] = True
            diag["asset_fallback_reason"] = f"Asset {current_asset_id} not found."
            break
            
        if current_asset_id in visited:
            diag["asset_fallback_used"] = True
            diag["asset_fallback_reason"] = f"Circular dependency detected at {current_asset_id}."
            diag["validation_warnings"].append("Fallback cycle prevented. Breaking out.")
            selected_asset = None
            break
            
        visited.add(current_asset_id)
        
        # Check compatibility
        compat_error = None
        if template_id and template_id not in asset.supported_templates:
            compat_error = f"Not supported by template {template_id}"
        elif asset_type not in asset.supported_components:
            compat_error = f"Not supported for component {asset_type}"
            
        if compat_error:
            if asset.fallback_asset_id:
                diag["asset_fallback_used"] = True
                diag["asset_fallback_reason"] = compat_error
                current_asset_id = asset.fallback_asset_id
                depth += 1
                continue
            else:
                diag["unsupported_asset"] = True
                diag["validation_warnings"].append(compat_error + " (No fallback available)")
                selected_asset = None
                break
        
        # Valid asset found
        selected_asset = asset
        break
        
    if depth > max_depth and not selected_asset:
        diag["asset_fallback_used"] = True
        diag["asset_fallback_reason"] = "Max fallback depth reached."
        
    if selected_asset:
        diag["selected_asset_id"] = selected_asset.asset_id
        diag["asset_variant"] = selected_asset.variant
        diag["external_asset"] = selected_asset.external_asset
        if not diag["asset_fallback_used"]:
            diag["asset_policy_reason"] = "Matched requested asset or variant"
        else:
            diag["asset_policy_reason"] = "Selected via fallback"
            
    return selected_asset, diag

def select_asset(
    component_type: str,
    requested_asset_id: str | None = None,
    variant: str | None = None,
    template_id: str | None = None
) -> tuple[AssetDefinition | None, dict]:
    return _resolve_asset_with_fallback(requested_asset_id, component_type, variant or "", template_id)
