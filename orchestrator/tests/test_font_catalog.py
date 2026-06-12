from orchestrator.app.rendering.font_catalog import catalog_policy_summary, font_catalog_for_llm, font_path_for_face, list_extra_font_files, list_font_faces, list_font_families


def test_font_catalog_lists_bundled_fonts_without_raw_paths():
    faces = list_font_faces()
    assert len(faces) >= 18
    assert "ridi_batang" in list_font_families()
    for face in faces:
        assert font_path_for_face(face).exists()

    summary = font_catalog_for_llm()
    assert summary
    assert all("assets/fonts" not in str(item) for item in summary)
    assert all("NotoSansKR" not in str(item) for item in summary)
    assert all("supported_weights" in item for item in summary)


def test_font_catalog_uses_expected_family_ids():
    families = set(list_font_families())
    assert {
        "bm_dohyeon",
        "bm_jua",
        "cormorant_garamond",
        "gmarket_sans",
        "hahmlet",
        "maru_buri",
        "noto_sans_cjk_kr",
        "noto_serif_cjk_kr",
        "pretendard",
        "ridi_batang",
        "suit",
    } == families


def test_font_catalog_ignores_extra_fonts_without_failing():
    policy = catalog_policy_summary()
    assert policy["active_core_font_count"] == 23
    assert policy["extra_font_policy"] == "ignored_by_catalog"
    assert isinstance(list_extra_font_files(), list)
