from orchestrator.app.llm.copy_quality import apply_copy_quality_policy, normalize_cta, sanitize_copy_text, score_copy_quality, shorten_headline
from orchestrator.app.schemas.llm_marketing import MarketingCopy


def test_copy_quality_trims_exclamations_and_phrases():
    copy = MarketingCopy(headline="대박 역대급 신메뉴!!! 지금 바로", subcopy="  최고의  혜택입니다!!!  ", cta="지금 바로 확인하기")
    fixed = apply_copy_quality_policy(copy)

    assert "대박" not in fixed.headline
    assert "!!" not in fixed.subcopy
    assert len(fixed.headline) <= 18
    assert fixed.cta == "자세히 보기"
    assert fixed.metadata["copy_quality"]["score"] < 1


def test_copy_quality_helpers():
    assert sanitize_copy_text("오늘   좋아요!!!") == "오늘 좋아요!"
    assert len(shorten_headline("놓치지 마세요 역대급 혜택 안내", max_chars=12)) <= 12
    assert normalize_cta("매장으로 자세히 문의하기") == "매장으로 자세히 문의하기"
    assert score_copy_quality({"headline": "대박 혜택!!"})["warnings"]
