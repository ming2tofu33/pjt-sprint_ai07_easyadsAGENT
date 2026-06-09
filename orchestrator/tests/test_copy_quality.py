from orchestrator.app.llm.copy_quality import apply_copy_quality_policy, normalize_cta, sanitize_copy_text, score_copy_quality, shorten_headline
from orchestrator.app.schemas.llm_marketing import MarketingCopy


def test_copy_quality_scores_without_destructive_rewrite():
    copy = MarketingCopy(headline="대박 신메뉴!! 지금 바로", subcopy="  최고의 혜택입니다!!  ", cta="지금 바로 확인하기")
    fixed = apply_copy_quality_policy(copy)

    assert "대박" in fixed.headline
    assert "!!" not in fixed.subcopy
    assert fixed.cta == "지금 바로 확인하기"
    assert fixed.metadata["copy_quality"]["score"] < 1
    assert fixed.metadata["copy_quality"]["applied_fixes"] == []


def test_copy_quality_helpers():
    assert sanitize_copy_text("오늘   좋아요!!") == "오늘 좋아요!"
    assert len(shorten_headline("놓치지 마세요 신메뉴 혜택 안내", max_chars=12)) <= 12
    assert normalize_cta("매장으로 자세히 문의하기") == "매장으로 자세히 문의하기"
    assert score_copy_quality({"headline": "대박 혜택!!"})["warnings"]
