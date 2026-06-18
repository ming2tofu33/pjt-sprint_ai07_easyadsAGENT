from __future__ import annotations

import pytest

from orchestrator.app.llm.intake_item_normalization import normalize_item_or_service_candidate


@pytest.mark.parametrize(
    ("candidate", "source_text", "expected", "removed"),
    [
        (
            "직화삼겹김치찌개 이미지",
            "직화삼겹김치찌개 이미지로 한식당 광고 만들어줘",
            "직화삼겹김치찌개",
            ("이미지",),
        ),
        (
            "망고 라떼 광고 이미지",
            "망고 라떼 광고 이미지 만들어줘",
            "망고 라떼",
            ("광고 이미지",),
        ),
        (
            "프리미엄 여름 포스터 이미지",
            "프리미엄 여름 포스터 이미지로 광고 제작해줘",
            "프리미엄 여름",
            ("포스터 이미지",),
        ),
        (
            "강남 직장인 왕초보 비즈니스 영어 회화반 모집 배너",
            "강남 직장인 왕초보 비즈니스 영어 회화반 모집 배너 제작해줘",
            "강남 직장인 왕초보 비즈니스 영어 회화반",
            ("모집 배너",),
        ),
    ],
)
def test_removes_only_trailing_creative_artifacts(candidate, source_text, expected, removed):
    result = normalize_item_or_service_candidate(
        candidate,
        source_text=source_text,
        candidate_source="explicit_product_mention",
        ad_format="poster",
    )

    assert result.normalized_value == expected
    assert result.removed_fragments == removed
    assert result.reason_codes == ("removed_trailing_creative_artifact",)
    assert result.changed is True


@pytest.mark.parametrize(
    "candidate",
    [
        "이미지 컨설팅 서비스",
        "퍼스널 이미지 메이킹",
        "상품 사진 촬영 서비스",
        "증명사진 서비스",
        "포스터 디자인 서비스",
        "사진관 신규 오픈",
        "AI 이미지 생성 솔루션",
    ],
)
def test_preserves_artifact_words_when_they_are_part_of_the_service_identity(candidate):
    result = normalize_item_or_service_candidate(
        candidate,
        source_text=f"{candidate} 광고",
        candidate_source="deterministic_hint",
        ad_format="banner",
    )

    assert result.normalized_value == candidate
    assert result.removed_fragments == ()
    assert result.changed is False


def test_removes_artifact_connector_before_venue_context():
    result = normalize_item_or_service_candidate(
        "직화삼겹김치찌개 이미지로 한식당",
        source_text="직화삼겹김치찌개 이미지로 한식당 광고 만들어줘",
        candidate_source="explicit_product_mention",
        ad_format="poster",
    )

    assert result.normalized_value == "직화삼겹김치찌개"
    assert result.removed_fragments == ("이미지",)
    assert result.reason_codes == ("removed_creative_artifact_connector",)


def test_preserves_long_semantic_product_phrase_without_truncation():
    candidate = "제주 흑돼지 직화 삼겹 김치찌개 광고 만들어줘"
    result = normalize_item_or_service_candidate(
        candidate,
        source_text=candidate,
        candidate_source="structured_llm",
        ad_format="poster",
    )

    assert result.normalized_value == "제주 흑돼지 직화 삼겹 김치찌개"
    assert result.removed_fragments == ("광고 만들어줘",)


def test_confirmed_user_value_is_not_silently_normalized():
    result = normalize_item_or_service_candidate(
        "망고 라떼 광고 이미지",
        source_text="망고 라떼 광고 이미지",
        candidate_source="confirmed_context",
        ad_format="poster",
    )

    assert result.normalized_value == "망고 라떼 광고 이미지"
    assert result.changed is False
    assert result.reason_codes == ("confirmed_value_contains_artifact_term",)
