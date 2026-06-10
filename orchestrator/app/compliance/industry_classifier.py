"""business_type → compliance domain 매핑."""

from __future__ import annotations

BUSINESS_TYPE_TO_DOMAIN: dict[str, list[str]] = {
    "cafe":                  ["food", "general_ad"],
    "restaurant":            ["food", "general_ad"],
    "restaurant_bbq":        ["food", "general_ad"],
    "restaurant_japanese":   ["food", "general_ad"],
    "restaurant_korean":     ["food", "general_ad"],
    "fitness":               ["general_ad"],
    "pilates":               ["general_ad"],
    "yoga":                  ["general_ad"],
    "beauty_skincare":       ["cosmetic", "general_ad"],
    "beauty_hair":           ["cosmetic", "general_ad"],
    "beauty_nail":           ["cosmetic", "general_ad"],
    "beauty_spa":            ["cosmetic", "general_ad"],
    "hospital":              ["medical", "general_ad"],
    "dental":                ["medical", "general_ad"],
    "plastic_surgery":       ["medical", "general_ad"],
    "oriental_medicine":     ["medical", "general_ad"],
    "health_supplement":     ["health_functional_food", "food", "general_ad"],
}

_FALLBACK = ["general_ad"]


class IndustryClassifier:
    def get_domains(self, business_type: str | None) -> list[str]:
        if not business_type:
            return _FALLBACK
        return BUSINESS_TYPE_TO_DOMAIN.get(business_type, _FALLBACK)
