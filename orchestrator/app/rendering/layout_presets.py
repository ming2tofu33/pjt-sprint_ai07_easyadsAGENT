"""Layout Presets Builder for Phase 1.7 Layout Quality Tuning."""

from typing import Any
from orchestrator.app.schemas.poster_layout import PosterComponent


def build_center_stack(canvas_w: int, canvas_h: int, content: dict, colors: dict) -> list[PosterComponent]:
    components = []
    margin = 0.08
    safe_w = 1.0 - margin * 2
    
    primary_color = colors.get("primary", "#FFFFFF")
    secondary_color = colors.get("secondary", "#E0E0E0")
    
    cursor_y = margin
    
    # Calculate total height to center the stack
    # We will approximate heights: headline ~20%, subcopy ~15%, footer ~8%
    has_hl = bool(content.get("headline"))
    has_sub = bool(content.get("subcopy"))
    has_ft = bool(content.get("footer"))
    
    has_features = bool(content.get("features"))
    
    total_h = 0
    if has_hl: total_h += 0.25
    if has_sub: total_h += 0.15
    if has_features: total_h += 0.20
    if has_ft: total_h += 0.10
    
    # Vertically center the stack
    cursor_y = (1.0 - total_h) / 2.0
    cursor_y = max(margin, cursor_y) # Don't violate top margin
    
    if content.get("speech_bubble"):
        components.append(PosterComponent(
            type="speech_bubble",
            bbox={"x": margin, "y": cursor_y, "w": safe_w, "h": 0.15},
            content=content["speech_bubble"],
            style={"font_size": int(min(canvas_w, canvas_h) * 0.04), "background_color": primary_color, "text_color": "#111827"},
            z_index=30
        ))
        cursor_y += 0.17

    if has_hl:
        components.append(PosterComponent(
            type="headline_block",
            bbox={"x": margin, "y": cursor_y, "w": safe_w, "h": 0.25},
            content={"lines": [content["headline"]]},
            style={"font_size": int(min(canvas_w, canvas_h) * 0.12), "text_color": primary_color},
            z_index=20
        ))
        cursor_y += 0.27
        
    if has_sub:
        components.append(PosterComponent(
            type="subcopy_block",
            bbox={"x": margin, "y": cursor_y, "w": safe_w, "h": 0.15},
            content=content["subcopy"],
            style={"font_size": int(min(canvas_w, canvas_h) * 0.04), "text_color": secondary_color},
            z_index=20
        ))
        cursor_y += 0.17
        
    if has_features:
        components.append(PosterComponent(
            type="icon_feature_list",
            bbox={"x": margin, "y": cursor_y, "w": safe_w, "h": 0.20},
            content=content["features"],
            style={"font_size": int(min(canvas_w, canvas_h) * 0.035), "text_color": secondary_color, "icon_color": primary_color, "background_color": "#11182780"},
            z_index=20
        ))
        cursor_y += 0.22
        
    if has_ft:
        components.append(PosterComponent(
            type="footer_panel",
            bbox={"x": margin, "y": cursor_y, "w": safe_w, "h": 0.08},
            content=content["footer"],
            style={"font_size": int(min(canvas_w, canvas_h) * 0.025), "text_color": primary_color, "background_color": "#11182780"},
            z_index=10
        ))
        
    return components


def build_top_headline_footer(canvas_w: int, canvas_h: int, content: dict, colors: dict) -> list[PosterComponent]:
    components = []
    margin = 0.08
    safe_w = 1.0 - margin * 2
    
    primary_color = colors.get("primary", "#FFFFFF")
    secondary_color = colors.get("secondary", "#E0E0E0")
    
    cursor_y = margin
    
    if content.get("speech_bubble"):
        components.append(PosterComponent(
            type="speech_bubble",
            bbox={"x": margin, "y": cursor_y, "w": 0.4, "h": 0.1},
            content=content["speech_bubble"],
            style={"font_size": int(min(canvas_w, canvas_h) * 0.035), "background_color": primary_color, "text_color": "#111827"},
            z_index=30
        ))
        cursor_y += 0.12

    if content.get("headline"):
        components.append(PosterComponent(
            type="headline_block",
            bbox={"x": margin, "y": cursor_y, "w": safe_w, "h": 0.2},
            content={"lines": [content["headline"]]},
            style={"font_size": int(min(canvas_w, canvas_h) * 0.10), "text_color": primary_color},
            z_index=20
        ))
        cursor_y += 0.22
        
    if content.get("subcopy"):
        components.append(PosterComponent(
            type="subcopy_block",
            bbox={"x": margin, "y": cursor_y, "w": safe_w, "h": 0.15},
            content=content["subcopy"],
            style={"font_size": int(min(canvas_w, canvas_h) * 0.035), "text_color": secondary_color},
            z_index=20
        ))
        cursor_y += 0.18
        
    if content.get("memo_card"):
        components.append(PosterComponent(
            type="memo_card",
            bbox={"x": margin, "y": cursor_y, "w": safe_w, "h": 0.15},
            content=content["memo_card"],
            style={"font_size": int(min(canvas_w, canvas_h) * 0.04), "background_color": "#FEF3C7", "text_color": "#92400E"},
            z_index=25
        ))
        cursor_y += 0.18
        
    if content.get("footer"):
        # Anchor footer to bottom with 5% margin
        fh = 0.08
        components.append(PosterComponent(
            type="footer_panel",
            bbox={"x": margin, "y": 1.0 - 0.05 - fh, "w": safe_w, "h": fh},
            content=content["footer"],
            style={"font_size": int(min(canvas_w, canvas_h) * 0.02), "text_color": primary_color, "background_color": "#11182780"},
            z_index=10
        ))
        
    return components


def build_editorial_left(canvas_w: int, canvas_h: int, content: dict, colors: dict) -> list[PosterComponent]:
    components = []
    margin = 0.08
    
    primary_color = colors.get("primary", "#FFFFFF")
    secondary_color = colors.get("secondary", "#E0E0E0")
    
    aspect_ratio = canvas_w / canvas_h
    
    # Calculate content width dynamically
    if aspect_ratio > 1.2:  # Wide
        content_w = 0.4
    elif aspect_ratio < 0.8: # Portrait
        content_w = 0.8
    else: # Square
        content_w = 0.5
        
    cursor_y = margin + 0.05
    
    if content.get("speech_bubble"):
        components.append(PosterComponent(
            type="speech_bubble",
            bbox={"x": margin, "y": cursor_y, "w": content_w * 0.8, "h": 0.08},
            content=content["speech_bubble"],
            style={"font_size": int(min(canvas_w, canvas_h) * 0.035), "background_color": primary_color, "text_color": "#111827"},
            z_index=30
        ))
        cursor_y += 0.10

    if content.get("headline"):
        components.append(PosterComponent(
            type="headline_block",
            bbox={"x": margin, "y": cursor_y, "w": content_w, "h": 0.25},
            content={"lines": [content["headline"]]},
            style={"font_size": int(min(canvas_w, canvas_h) * 0.09), "text_color": primary_color},
            z_index=20
        ))
        cursor_y += 0.26
        
    if content.get("subcopy"):
        components.append(PosterComponent(
            type="subcopy_block",
            bbox={"x": margin, "y": cursor_y, "w": content_w, "h": 0.12},
            content=content["subcopy"],
            style={"font_size": int(min(canvas_w, canvas_h) * 0.035), "text_color": secondary_color},
            z_index=20
        ))
        cursor_y += 0.14
        
    if content.get("features"):
        components.append(PosterComponent(
            type="icon_feature_list",
            bbox={"x": margin, "y": cursor_y, "w": content_w, "h": 0.2},
            content=content["features"],
            style={"font_size": int(min(canvas_w, canvas_h) * 0.030), "text_color": secondary_color, "icon_color": primary_color, "background_color": "#11182780"},
            z_index=20
        ))
        cursor_y += 0.22
        
    if content.get("footer"):
        components.append(PosterComponent(
            type="footer_panel",
            bbox={"x": margin, "y": cursor_y, "w": content_w, "h": 0.07},
            content=content["footer"],
            style={"font_size": int(min(canvas_w, canvas_h) * 0.02), "text_color": primary_color, "background_color": "#11182780"},
            z_index=10
        ))
        
    return components


def build_hero_center(canvas_w: int, canvas_h: int, content: dict, colors: dict) -> list[PosterComponent]:
    components = []
    margin = 0.08
    safe_w = 1.0 - margin * 2
    
    primary_color = colors.get("primary", "#FFFFFF")
    secondary_color = colors.get("secondary", "#E0E0E0")
    
    cursor_y = 0.35 # Fixed massive center
    
    if content.get("headline"):
        components.append(PosterComponent(
            type="headline_block",
            bbox={"x": margin, "y": cursor_y, "w": safe_w, "h": 0.3},
            content={"lines": [content["headline"]]},
            style={"font_size": int(min(canvas_w, canvas_h) * 0.15), "text_color": primary_color}, # Massive font
            z_index=20
        ))
        cursor_y += 0.32
        
    if content.get("speech_bubble"):
        components.append(PosterComponent(
            type="speech_bubble",
            bbox={"x": 0.5 - 0.2, "y": 0.35 - 0.12, "w": 0.4, "h": 0.1},
            content=content["speech_bubble"],
            style={"font_size": int(min(canvas_w, canvas_h) * 0.035), "background_color": primary_color, "text_color": "#111827"},
            z_index=30
        ))

    if content.get("subcopy"):
        components.append(PosterComponent(
            type="subcopy_block",
            bbox={"x": 0.2, "y": cursor_y, "w": 0.6, "h": 0.15},
            content=content["subcopy"],
            style={"font_size": int(min(canvas_w, canvas_h) * 0.035), "text_color": secondary_color},
            z_index=20
        ))
        
    if content.get("footer"):
        fh = 0.06
        components.append(PosterComponent(
            type="footer_panel",
            bbox={"x": 0.2, "y": 1.0 - 0.05 - fh, "w": 0.6, "h": fh},
            content=content["footer"],
            style={"font_size": int(min(canvas_w, canvas_h) * 0.02), "text_color": primary_color, "background_color": "#11182780"},
            z_index=10
        ))
        
    return components


LAYOUT_PRESETS = {
    "center_stack": build_center_stack,
    "top_headline_footer": build_top_headline_footer,
    "editorial_left": build_editorial_left,
    "hero_center": build_hero_center
}

def generate_layout(preset_name: str, canvas_w: int, canvas_h: int, content: dict, colors: dict) -> list[PosterComponent]:
    builder = LAYOUT_PRESETS.get(preset_name, build_center_stack)
    return builder(canvas_w, canvas_h, content, colors)
