from __future__ import annotations

from typing import Any


VISUAL_PRESETS = {
    "cafe_dessert_soft_premium": {
        "preset_id": "cafe_dessert_soft_premium",
        "business_type": "cafe",
        "composition_archetype": "subject_right_copy_left",
        "reserved_copy_area": "left",
        "primary_subject_template": "a premium cafe drink or dessert product hero on the right side",
        "secondary_props": ["fresh ingredients", "delicate pastel saucer", "soft napkin"],
        "desired_mood": ["pastel pink", "cream", "soft premium", "warm", "emotional"],
        "palette_hints": ["pastel pink", "cream", "soft white"],
        "lighting_hints": ["warm natural daylight", "soft cozy warm accents"],
        "surface_hints": ["clean marble tabletop", "wooden surface"],
        "forbidden_visual_elements": ["busy cafe signage", "menu boards", "price tags", "written text", "brand logos"],
        "positive_safe_area_terms": ["clean empty table space", "uncluttered soft background", "blank negative space"],
        "negative_terms": ["text", "letters", "signage", "menu board", "price tag", "logo", "watermark"],
    },
    "restaurant_bbq_warm_grill": {
        "preset_id": "restaurant_bbq_warm_grill",
        "business_type": "restaurant_bbq",
        "composition_archetype": "subject_right_copy_left",
        "reserved_copy_area": "left",
        "primary_subject_template": "freshly grilled meat hero on a sizzle grill placed on the right side",
        "secondary_props": ["side dishes", "subtle grill grates", "hot charcoal embers"],
        "desired_mood": ["premium restaurant mood", "warm grill highlights", "appetizing contrast", "bold"],
        "palette_hints": ["dark warm tones", "charcoal black", "ember orange", "golden brown"],
        "lighting_hints": ["dramatic warm spotlights", "glowing grill embers"],
        "surface_hints": ["dark stone table", "wooden grill table"],
        "forbidden_visual_elements": ["crowded tables", "cheap flyer graphics", "fake menu labels", "price tags", "written text"],
        "positive_safe_area_terms": ["dark clean negative space on the left", "out-of-focus empty table area"],
        "negative_terms": ["text", "menu label", "price tag", "cheap flyer graphics", "crowded table", "watermark"],
    },
    "beauty_skincare_clean_premium": {
        "preset_id": "beauty_skincare_clean_premium",
        "business_type": "beauty_skincare",
        "composition_archetype": "subject_right_copy_left",
        "reserved_copy_area": "left",
        "primary_subject_template": "premium skincare product bottle with soft glowing texture on the right",
        "secondary_props": ["water droplets", "smooth stones", "subtle botanical leaves"],
        "desired_mood": ["clean premium", "radiant", "gentle", "pure"],
        "palette_hints": ["soft white", "light beige", "pale pastel pink"],
        "lighting_hints": ["soft diffused studio lighting", "bright glowing highlight"],
        "surface_hints": ["reflective glass plate", "clean white marble surface"],
        "forbidden_visual_elements": ["overly dominant human face", "busy salon signage", "written brand names", "printed labels"],
        "positive_safe_area_terms": ["bright soft empty area with low texture", "blank pastel negative space"],
        "negative_terms": ["dominant face", "text", "signage", "brand labels", "printed labels", "logo"],
    },
    "beauty_hair_salon_clean": {
        "preset_id": "beauty_hair_salon_clean",
        "business_type": "beauty_hair",
        "composition_archetype": "generic_clean_ad_background",
        "reserved_copy_area": "left",
        "primary_subject_template": "a clean premium hair styling station with styling chair, large mirror, and styling tools",
        "secondary_props": ["hair styling tools in soft focus", "clean white vanity counter"],
        "desired_mood": ["premium hair salon interior", "bright", "clean", "minimal elegant"],
        "palette_hints": ["warm white", "gold accents", "pale beige"],
        "lighting_hints": ["bright modern salon lighting", "clean natural daylight"],
        "surface_hints": ["clean polished vanity tabletop", "reflective mirror surface"],
        "forbidden_visual_elements": ["close-up human face", "mirror text", "salon price list signage", "branding logos"],
        "positive_safe_area_terms": ["clean out-of-focus background wall", "empty floor or counter negative space"],
        "negative_terms": ["human face", "text", "signage", "price list", "mirror text", "logo"],
    },
    "beauty_nail_clean_detail": {
        "preset_id": "beauty_nail_clean_detail",
        "business_type": "beauty_nail",
        "composition_archetype": "subject_right_copy_left",
        "reserved_copy_area": "left",
        "primary_subject_template": "exquisitely detailed manicured hands showing elegant nail art on the right",
        "secondary_props": ["premium nail polish bottles", "soft satin fabric"],
        "desired_mood": ["elegant nail art detail", "pastel premium", "clean", "cute"],
        "palette_hints": ["soft pastel pink", "rose gold", "milky white"],
        "lighting_hints": ["bright soft ring light", "even diffused studio lighting"],
        "surface_hints": ["soft fabric surface", "clean glass plate"],
        "forbidden_visual_elements": ["salon banners", "full body shots", "text logos", "printed nail polish labels"],
        "positive_safe_area_terms": ["clean pastel table surface on the left", "uncluttered soft negative space"],
        "negative_terms": ["text", "banners", "printed labels", "logos", "watermark"],
    },
    "beauty_spa_soft_wellness": {
        "preset_id": "beauty_spa_soft_wellness",
        "business_type": "beauty_spa",
        "composition_archetype": "subject_right_copy_left",
        "reserved_copy_area": "left",
        "primary_subject_template": "serene spa massage setup with rolled white towels, aroma oil dropper bottle, and burning incense on the right",
        "secondary_props": ["frangipani flowers", "smooth basalt hot stones", "bamboo accents"],
        "desired_mood": ["soft wellness", "healing", "calm", "serene"],
        "palette_hints": ["warm earth tones", "soft olive green", "pure white"],
        "lighting_hints": ["cozy warm candlelight", "soft natural light through bamboo blinds"],
        "surface_hints": ["wooden massage table", "dark slate tray"],
        "forbidden_visual_elements": ["explicit human nudity", "crowded spa counters", "readable brand logos", "printed text signage"],
        "positive_safe_area_terms": ["calm empty space on the left", "softly lit negative space"],
        "negative_terms": ["nudity", "text", "logos", "signage", "cluttered counter", "watermark"],
    },
    "generic_clean_ad_background": {
        "preset_id": "generic_clean_ad_background",
        "business_type": "generic",
        "composition_archetype": "generic_clean_ad_background",
        "reserved_copy_area": "left",
        "primary_subject_template": "simple clean advertising background subject",
        "secondary_props": [],
        "desired_mood": ["clean", "neutral", "premium"],
        "palette_hints": ["#F5F5F5", "#FFFFFF", "#D1D5DB"],
        "lighting_hints": ["clean commercial lighting"],
        "surface_hints": ["neutral background surface"],
        "forbidden_visual_elements": ["visual clutter", "signage", "written text"],
        "positive_safe_area_terms": ["clear reserved text area", "blank negative space"],
        "negative_terms": ["text", "letters", "signage", "logo", "watermark"],
    },
}


def get_visual_presets() -> dict[str, dict[str, Any]]:
    return VISUAL_PRESETS


def select_visual_preset(
    business_type: str | None,
    ad_format: str | None = None,
    selected_reference_template: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Select appropriate visual preset based on business type and templates."""
    bt = (business_type or "").lower()
    
    # Check selected reference template first for hints if present
    ref_preset_id = (selected_reference_template or {}).get("preset_id") or (selected_reference_template or {}).get("visual_template_id")
    if ref_preset_id and ref_preset_id in VISUAL_PRESETS:
        return VISUAL_PRESETS[ref_preset_id]
        
    # Heuristics based on business_type string
    if bt == "cafe" or "cafe" in bt or "dessert" in bt or "bakery" in bt:
        return VISUAL_PRESETS["cafe_dessert_soft_premium"]
    elif "bbq" in bt or "restaurant" in bt or "korean_food" in bt or "meat" in bt:
        return VISUAL_PRESETS["restaurant_bbq_warm_grill"]
    elif bt == "beauty_skincare" or "skincare" in bt or "skin" in bt:
        return VISUAL_PRESETS["beauty_skincare_clean_premium"]
    elif bt == "beauty_hair" or "hair" in bt or "salon" in bt:
        return VISUAL_PRESETS["beauty_hair_salon_clean"]
    elif bt == "beauty_nail" or "nail" in bt:
        return VISUAL_PRESETS["beauty_nail_clean_detail"]
    elif bt == "beauty_spa" or "spa" in bt or "massage" in bt:
        return VISUAL_PRESETS["beauty_spa_soft_wellness"]
    elif "beauty" in bt:
        # Default fallback for beauty
        return VISUAL_PRESETS["beauty_skincare_clean_premium"]
        
    return VISUAL_PRESETS["generic_clean_ad_background"]
