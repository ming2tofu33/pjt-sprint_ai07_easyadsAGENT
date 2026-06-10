from pathlib import Path

from orchestrator.app.rendering.font_catalog import font_catalog_for_llm, font_path_for_face, list_font_faces, list_font_families


def test_font_catalog_lists_bundled_fonts_without_raw_paths():
    faces = list_font_faces()
    assert len(faces) >= 18
    assert "ridi_batang" in list_font_families()
    for face in faces:
        assert font_path_for_face(face).exists()

    summary = font_catalog_for_llm()
    assert summary
    assert all("assets/fonts" not in str(item) for item in summary)
    assert all("supported_weights" in item for item in summary)


def test_font_catalog_uses_expected_family_ids():
    families = set(list_font_families())
    assert {"bm_dohyeon", "bm_jua", "gmarket_sans", "maru_buri", "noto_sans_kr", "pretendard", "ridi_batang", "sc_dream"} <= families
