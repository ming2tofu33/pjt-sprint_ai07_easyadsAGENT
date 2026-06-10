"""Typography pairing presets constrained to bundled font families."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


PairingPresetId = Literal[
    "editorial_serif_sans",
    "soft_beauty",
    "clean_modern",
    "rounded_friendly",
    "bold_event",
    "trustworthy",
    "fallback",
]


class RoleFontChoice(BaseModel):
    family_id: str
    weight: int


class FontPairingPreset(BaseModel):
    preset_id: PairingPresetId
    headline: RoleFontChoice
    body: RoleFontChoice
    cta: RoleFontChoice
    moods: list[str]
    recommended_for: list[str]

    @property
    def family_count(self) -> int:
        return len({self.headline.family_id, self.body.family_id, self.cta.family_id})


PRESETS: dict[str, FontPairingPreset] = {
    "editorial_serif_sans": FontPairingPreset(
        preset_id="editorial_serif_sans",
        headline=RoleFontChoice(family_id="ridi_batang", weight=400),
        body=RoleFontChoice(family_id="pretendard", weight=400),
        cta=RoleFontChoice(family_id="pretendard", weight=500),
        moods=["premium", "editorial", "product"],
        recommended_for=["macaron", "premium_menu", "editorial_product", "menu_discovery"],
    ),
    "soft_beauty": FontPairingPreset(
        preset_id="soft_beauty",
        headline=RoleFontChoice(family_id="maru_buri", weight=700),
        body=RoleFontChoice(family_id="pretendard", weight=400),
        cta=RoleFontChoice(family_id="pretendard", weight=500),
        moods=["soft", "beauty", "premium"],
        recommended_for=["beauty", "nail", "hair", "spa", "skincare"],
    ),
    "clean_modern": FontPairingPreset(
        preset_id="clean_modern",
        headline=RoleFontChoice(family_id="gmarket_sans", weight=700),
        body=RoleFontChoice(family_id="pretendard", weight=400),
        cta=RoleFontChoice(family_id="pretendard", weight=500),
        moods=["clean", "modern"],
        recommended_for=["generic", "service", "modern_brand"],
    ),
    "rounded_friendly": FontPairingPreset(
        preset_id="rounded_friendly",
        headline=RoleFontChoice(family_id="bm_jua", weight=700),
        body=RoleFontChoice(family_id="pretendard", weight=400),
        cta=RoleFontChoice(family_id="pretendard", weight=500),
        moods=["friendly", "cute"],
        recommended_for=["cafe", "dessert", "casual"],
    ),
    "bold_event": FontPairingPreset(
        preset_id="bold_event",
        headline=RoleFontChoice(family_id="bm_dohyeon", weight=700),
        body=RoleFontChoice(family_id="gmarket_sans", weight=500),
        cta=RoleFontChoice(family_id="gmarket_sans", weight=700),
        moods=["bold", "event"],
        recommended_for=["discount_event", "promotion", "flyer"],
    ),
    "trustworthy": FontPairingPreset(
        preset_id="trustworthy",
        headline=RoleFontChoice(family_id="sc_dream", weight=700),
        body=RoleFontChoice(family_id="sc_dream", weight=400),
        cta=RoleFontChoice(family_id="sc_dream", weight=500),
        moods=["trustworthy", "clear"],
        recommended_for=["clinic", "education", "reservation"],
    ),
    "fallback": FontPairingPreset(
        preset_id="fallback",
        headline=RoleFontChoice(family_id="noto_sans_kr", weight=700),
        body=RoleFontChoice(family_id="noto_sans_kr", weight=400),
        cta=RoleFontChoice(family_id="noto_sans_kr", weight=500),
        moods=["neutral"],
        recommended_for=["fallback"],
    ),
}


def get_pairing_preset(preset_id: str | None) -> FontPairingPreset:
    return PRESETS.get(str(preset_id or ""), PRESETS["fallback"])


def list_pairing_presets() -> list[FontPairingPreset]:
    return list(PRESETS.values())
