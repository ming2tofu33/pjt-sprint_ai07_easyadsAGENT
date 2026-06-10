"""Bundled Korean font catalog for deterministic rendering."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel


FontCategory = Literal["serif", "sans", "rounded", "display"]
FontScript = Literal["hangul", "latin", "digits", "punctuation"]


class FontFaceSpec(BaseModel):
    font_id: str
    family_id: str
    display_name: str
    relative_path: str
    weight: int
    style: Literal["normal"] = "normal"
    scripts: list[FontScript] = ["hangul", "latin", "digits", "punctuation"]
    category: FontCategory
    moods: list[str]
    bundled: bool = True
    recommended_roles: list[str] = []


PROJECT_ROOT = Path(__file__).resolve().parents[3]
FONT_DIR = PROJECT_ROOT / "assets" / "fonts"


_FACES: tuple[FontFaceSpec, ...] = (
    FontFaceSpec(font_id="bm_dohyeon_regular", family_id="bm_dohyeon", display_name="BM DoHyeon", relative_path="assets/fonts/BMDOHYEON_ttf.ttf", weight=700, category="display", moods=["bold", "event", "impact"], recommended_roles=["headline", "badge"]),
    FontFaceSpec(font_id="bm_jua_regular", family_id="bm_jua", display_name="BM Jua", relative_path="assets/fonts/BMJUA_ttf.ttf", weight=700, category="rounded", moods=["friendly", "cute", "casual"], recommended_roles=["headline", "cta"]),
    FontFaceSpec(font_id="gmarket_sans_light", family_id="gmarket_sans", display_name="Gmarket Sans Light", relative_path="assets/fonts/GmarketSansTTFLight.ttf", weight=300, category="sans", moods=["clean", "modern"], recommended_roles=["body", "disclaimer"]),
    FontFaceSpec(font_id="gmarket_sans_medium", family_id="gmarket_sans", display_name="Gmarket Sans Medium", relative_path="assets/fonts/GmarketSansTTFMedium.ttf", weight=500, category="sans", moods=["clean", "modern"], recommended_roles=["headline", "body", "cta"]),
    FontFaceSpec(font_id="gmarket_sans_bold", family_id="gmarket_sans", display_name="Gmarket Sans Bold", relative_path="assets/fonts/GmarketSansTTFBold.ttf", weight=700, category="sans", moods=["clean", "bold", "event"], recommended_roles=["headline"]),
    FontFaceSpec(font_id="maru_buri_light", family_id="maru_buri", display_name="Maru Buri Light", relative_path="assets/fonts/MaruBuri-Light.ttf", weight=300, category="serif", moods=["premium", "soft", "editorial"], recommended_roles=["body"]),
    FontFaceSpec(font_id="maru_buri_regular", family_id="maru_buri", display_name="Maru Buri Regular", relative_path="assets/fonts/MaruBuri-Regular.ttf", weight=400, category="serif", moods=["premium", "soft", "editorial"], recommended_roles=["body"]),
    FontFaceSpec(font_id="maru_buri_bold", family_id="maru_buri", display_name="Maru Buri Bold", relative_path="assets/fonts/MaruBuri-Bold.ttf", weight=700, category="serif", moods=["premium", "beauty", "editorial"], recommended_roles=["headline"]),
    FontFaceSpec(font_id="noto_sans_kr_regular", family_id="noto_sans_kr", display_name="Noto Sans KR Regular", relative_path="assets/fonts/NotoSansKR-Regular.ttf", weight=400, category="sans", moods=["neutral", "legible"], recommended_roles=["body", "disclaimer"]),
    FontFaceSpec(font_id="noto_sans_kr_medium", family_id="noto_sans_kr", display_name="Noto Sans KR Medium", relative_path="assets/fonts/NotoSansKR-Medium.ttf", weight=500, category="sans", moods=["neutral", "legible"], recommended_roles=["body", "cta"]),
    FontFaceSpec(font_id="noto_sans_kr_bold", family_id="noto_sans_kr", display_name="Noto Sans KR Bold", relative_path="assets/fonts/NotoSansKR-Bold.ttf", weight=700, category="sans", moods=["neutral", "bold"], recommended_roles=["headline"]),
    FontFaceSpec(font_id="pretendard_regular", family_id="pretendard", display_name="Pretendard Regular", relative_path="assets/fonts/Pretendard-Regular.otf", weight=400, category="sans", moods=["modern", "legible", "premium"], recommended_roles=["body", "disclaimer"]),
    FontFaceSpec(font_id="pretendard_medium", family_id="pretendard", display_name="Pretendard Medium", relative_path="assets/fonts/Pretendard-Medium.otf", weight=500, category="sans", moods=["modern", "legible", "premium"], recommended_roles=["body", "cta"]),
    FontFaceSpec(font_id="pretendard_bold", family_id="pretendard", display_name="Pretendard Bold", relative_path="assets/fonts/Pretendard-Bold.otf", weight=700, category="sans", moods=["modern", "bold"], recommended_roles=["headline"]),
    FontFaceSpec(font_id="ridi_batang_regular", family_id="ridi_batang", display_name="RIDI Batang", relative_path="assets/fonts/RIDIBatang.otf", weight=400, category="serif", moods=["premium", "editorial", "warm"], recommended_roles=["headline", "brand_label"]),
    FontFaceSpec(font_id="sc_dream_regular", family_id="sc_dream", display_name="S-Core Dream Regular", relative_path="assets/fonts/SCDream_Regular.otf", weight=400, category="sans", moods=["trustworthy", "clean"], recommended_roles=["body"]),
    FontFaceSpec(font_id="sc_dream_medium", family_id="sc_dream", display_name="S-Core Dream Medium", relative_path="assets/fonts/SCDream_Medium.otf", weight=500, category="sans", moods=["trustworthy", "clean"], recommended_roles=["body", "cta"]),
    FontFaceSpec(font_id="sc_dream_bold", family_id="sc_dream", display_name="S-Core Dream Bold", relative_path="assets/fonts/SCDream_Bold.otf", weight=700, category="sans", moods=["trustworthy", "bold"], recommended_roles=["headline"]),
)

_ALIASES = {
    "RIDIBatang": "ridi_batang",
    "RIDI Batang": "ridi_batang",
    "MaruBuri": "maru_buri",
    "Pretendard": "pretendard",
    "NotoSansKR": "noto_sans_kr",
    "Noto Sans KR": "noto_sans_kr",
    "GmarketSans": "gmarket_sans",
    "SCDream": "sc_dream",
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
                "font_ids": [face.font_id for face in faces],
                "supported_weights": [face.weight for face in faces],
                "moods": sorted({mood for face in faces for mood in face.moods}),
                "recommended_roles": sorted({role for face in faces for role in face.recommended_roles}),
            }
        )
    return families
