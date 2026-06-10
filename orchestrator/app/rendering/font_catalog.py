"""Core bundled font catalog for typography renderer v2."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel


FontCategory = Literal["serif", "sans", "rounded", "display"]
FontScript = Literal["hangul", "latin", "hanja", "digits", "punctuation"]


class FontFaceSpec(BaseModel):
    font_id: str
    family_id: str
    display_name: str
    relative_path: str
    weight: int
    style: Literal["normal"] = "normal"
    scripts: list[FontScript]
    category: FontCategory
    moods: list[str]
    bundled: bool = True
    recommended_roles: list[str] = []


PROJECT_ROOT = Path(__file__).resolve().parents[3]
FONT_DIR = PROJECT_ROOT / "assets" / "fonts"
CORE_FONT_FILE_NAMES = {
    "RIDIBatang.otf",
    "MaruBuri-Regular.ttf",
    "MaruBuri-Bold.ttf",
    "Pretendard-Regular.otf",
    "Pretendard-Medium.otf",
    "Pretendard-Bold.otf",
    "SUIT-Regular.ttf",
    "SUIT-Medium.ttf",
    "SUIT-Bold.ttf",
    "Hahmlet-Medium.ttf",
    "Hahmlet-SemiBold.ttf",
    "Hahmlet-Bold.ttf",
    "NotoSansCJKkr-Regular.otf",
    "NotoSansCJKkr-Bold.otf",
    "NotoSerifCJKkr-Regular.otf",
    "NotoSerifCJKkr-SemiBold.otf",
    "CormorantGaramond-Regular.otf",
    "CormorantGaramond-Medium.otf",
    "CormorantGaramond-SemiBold.otf",
    "GmarketSansTTFMedium.ttf",
    "GmarketSansTTFBold.ttf",
    "BMJUA_ttf.ttf",
    "BMDOHYEON_ttf.ttf",
}

CORE_FONT_FAMILIES = {
    "ridi_batang": {"roles": ["korean_headline", "brand_label"], "scripts": ["hangul", "latin", "digits", "punctuation"], "moods": ["premium", "editorial", "warm"]},
    "maru_buri": {"roles": ["korean_headline", "korean_body"], "scripts": ["hangul", "latin", "digits", "punctuation"], "moods": ["soft", "beauty", "premium", "editorial"]},
    "pretendard": {"roles": ["body", "cta", "label", "price"], "scripts": ["hangul", "latin", "digits", "punctuation"], "moods": ["modern", "legible", "neutral"]},
    "suit": {"roles": ["body", "cta", "price", "label"], "scripts": ["hangul", "latin", "digits", "punctuation"], "moods": ["modern", "clean", "ui"]},
    "hahmlet": {"roles": ["korean_display_headline"], "scripts": ["hangul", "latin", "digits", "punctuation"], "moods": ["editorial", "expressive", "classic"]},
    "noto_sans_cjk_kr": {"roles": ["hanja_fallback", "body_fallback", "disclaimer"], "scripts": ["hangul", "latin", "hanja", "digits", "punctuation"], "moods": ["neutral", "legible", "fallback"]},
    "noto_serif_cjk_kr": {"roles": ["hanja_fallback", "premium_hanja", "serif_fallback"], "scripts": ["hangul", "latin", "hanja", "digits", "punctuation"], "moods": ["premium", "traditional", "editorial"]},
    "cormorant_garamond": {"roles": ["english_display_headline", "english_brand_label"], "scripts": ["latin", "digits", "punctuation"], "moods": ["luxury", "editorial", "fashion", "dessert"]},
    "gmarket_sans": {"roles": ["modern_headline", "event_headline"], "scripts": ["hangul", "latin", "digits", "punctuation"], "moods": ["clean", "modern", "bold"]},
    "bm_jua": {"roles": ["friendly_headline", "casual_cta"], "scripts": ["hangul", "latin", "digits", "punctuation"], "moods": ["friendly", "cute", "casual"]},
    "bm_dohyeon": {"roles": ["event_headline", "impact_badge"], "scripts": ["hangul", "latin", "digits", "punctuation"], "moods": ["bold", "event", "impact"]},
}


def _face(font_id: str, family_id: str, name: str, file_name: str, weight: int, category: FontCategory) -> FontFaceSpec:
    meta = CORE_FONT_FAMILIES[family_id]
    return FontFaceSpec(
        font_id=font_id,
        family_id=family_id,
        display_name=name,
        relative_path=f"assets/fonts/{file_name}",
        weight=weight,
        category=category,
        scripts=list(meta["scripts"]),
        moods=list(meta["moods"]),
        recommended_roles=list(meta["roles"]),
    )


_FACES: tuple[FontFaceSpec, ...] = (
    _face("ridi_batang_regular", "ridi_batang", "RIDI Batang", "RIDIBatang.otf", 400, "serif"),
    _face("maru_buri_regular", "maru_buri", "Maru Buri Regular", "MaruBuri-Regular.ttf", 400, "serif"),
    _face("maru_buri_bold", "maru_buri", "Maru Buri Bold", "MaruBuri-Bold.ttf", 700, "serif"),
    _face("pretendard_regular", "pretendard", "Pretendard Regular", "Pretendard-Regular.otf", 400, "sans"),
    _face("pretendard_medium", "pretendard", "Pretendard Medium", "Pretendard-Medium.otf", 500, "sans"),
    _face("pretendard_bold", "pretendard", "Pretendard Bold", "Pretendard-Bold.otf", 700, "sans"),
    _face("suit_regular", "suit", "SUIT Regular", "SUIT-Regular.ttf", 400, "sans"),
    _face("suit_medium", "suit", "SUIT Medium", "SUIT-Medium.ttf", 500, "sans"),
    _face("suit_bold", "suit", "SUIT Bold", "SUIT-Bold.ttf", 700, "sans"),
    _face("hahmlet_medium", "hahmlet", "Hahmlet Medium", "Hahmlet-Medium.ttf", 500, "serif"),
    _face("hahmlet_semibold", "hahmlet", "Hahmlet SemiBold", "Hahmlet-SemiBold.ttf", 600, "serif"),
    _face("hahmlet_bold", "hahmlet", "Hahmlet Bold", "Hahmlet-Bold.ttf", 700, "serif"),
    _face("noto_sans_cjk_kr_regular", "noto_sans_cjk_kr", "Noto Sans CJK KR Regular", "NotoSansCJKkr-Regular.otf", 400, "sans"),
    _face("noto_sans_cjk_kr_bold", "noto_sans_cjk_kr", "Noto Sans CJK KR Bold", "NotoSansCJKkr-Bold.otf", 700, "sans"),
    _face("noto_serif_cjk_kr_regular", "noto_serif_cjk_kr", "Noto Serif CJK KR Regular", "NotoSerifCJKkr-Regular.otf", 400, "serif"),
    _face("noto_serif_cjk_kr_semibold", "noto_serif_cjk_kr", "Noto Serif CJK KR SemiBold", "NotoSerifCJKkr-SemiBold.otf", 600, "serif"),
    _face("cormorant_garamond_regular", "cormorant_garamond", "Cormorant Garamond Regular", "CormorantGaramond-Regular.otf", 400, "serif"),
    _face("cormorant_garamond_medium", "cormorant_garamond", "Cormorant Garamond Medium", "CormorantGaramond-Medium.otf", 500, "serif"),
    _face("cormorant_garamond_semibold", "cormorant_garamond", "Cormorant Garamond SemiBold", "CormorantGaramond-SemiBold.otf", 600, "serif"),
    _face("gmarket_sans_medium", "gmarket_sans", "Gmarket Sans Medium", "GmarketSansTTFMedium.ttf", 500, "sans"),
    _face("gmarket_sans_bold", "gmarket_sans", "Gmarket Sans Bold", "GmarketSansTTFBold.ttf", 700, "sans"),
    _face("bm_jua_regular", "bm_jua", "BM Jua", "BMJUA_ttf.ttf", 700, "rounded"),
    _face("bm_dohyeon_regular", "bm_dohyeon", "BM DoHyeon", "BMDOHYEON_ttf.ttf", 700, "display"),
)

_ALIASES = {
    "RIDIBatang": "ridi_batang",
    "RIDI Batang": "ridi_batang",
    "MaruBuri": "maru_buri",
    "Pretendard": "pretendard",
    "SUIT": "suit",
    "Hahmlet": "hahmlet",
    "NotoSansCJKkr": "noto_sans_cjk_kr",
    "Noto Serif CJK KR": "noto_serif_cjk_kr",
    "Cormorant Garamond": "cormorant_garamond",
    "GmarketSans": "gmarket_sans",
    "BMDOHYEON": "bm_dohyeon",
    "BMJUA": "bm_jua",
}


def normalize_family_id(value: str | None) -> str:
    raw = str(value or "pretendard").strip()
    return _ALIASES.get(raw, raw.lower().replace("-", "_").replace(" ", "_"))


def list_font_faces() -> list[FontFaceSpec]:
    return list(_FACES)


def list_font_families() -> list[str]:
    return sorted({face.family_id for face in _FACES})


def list_extra_font_files() -> list[str]:
    if not FONT_DIR.exists():
        return []
    return sorted(path.name for path in FONT_DIR.iterdir() if path.is_file() and path.name not in CORE_FONT_FILE_NAMES)


def catalog_policy_summary() -> dict[str, object]:
    return {
        "active_core_font_count": len(_FACES),
        "active_core_file_count": len(CORE_FONT_FILE_NAMES),
        "extra_font_files_detected": len(list_extra_font_files()),
        "extra_font_policy": "ignored_by_catalog",
    }


@lru_cache(maxsize=64)
def get_font_face(font_id: str) -> FontFaceSpec | None:
    return next((face for face in _FACES if face.font_id == font_id), None)


def family_faces(family_id: str) -> list[FontFaceSpec]:
    normalized = normalize_family_id(family_id)
    return sorted([face for face in _FACES if face.family_id == normalized], key=lambda face: face.weight)


def nearest_available_weight(family_id: str, requested_weight: int) -> int:
    faces = family_faces(family_id)
    if not faces:
        raise ValueError(f"unknown font family: {family_id}")
    return min((face.weight for face in faces), key=lambda weight: (abs(weight - requested_weight), weight))


def resolve_font_face(family_id: str, weight: int) -> FontFaceSpec:
    normalized = normalize_family_id(family_id)
    resolved_weight = nearest_available_weight(normalized, weight)
    for face in family_faces(normalized):
        if face.weight == resolved_weight:
            return face
    raise ValueError(f"font face not found: {family_id} {weight}")


def font_path_for_face(face: FontFaceSpec) -> Path:
    return PROJECT_ROOT / face.relative_path


def font_catalog_for_llm() -> list[dict[str, object]]:
    families: list[dict[str, object]] = []
    for family_id in list_font_families():
        faces = family_faces(family_id)
        if not faces:
            continue
        families.append(
            {
                "family_id": family_id,
                "category": faces[0].category,
                "scripts": sorted({script for face in faces for script in face.scripts}),
                "supported_weights": [face.weight for face in faces],
                "moods": sorted({mood for face in faces for mood in face.moods}),
                "roles": sorted({role for face in faces for role in face.recommended_roles}),
            }
        )
    return families
