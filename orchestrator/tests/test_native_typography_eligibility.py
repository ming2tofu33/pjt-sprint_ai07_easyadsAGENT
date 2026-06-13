from orchestrator.app.llm.native_copy_policy import decide_native_typography_eligibility
from orchestrator.tests.test_native_copy_policy import _brief


def test_eligibility_blocks_three_text_blocks():
    brief = _brief(closing_copy="오늘의 식탁에 구수함을", allowed_texts=["고급진 된장찌개", "진한 구수함 한 그릇", "오늘의 식탁에 구수함을"])

    decision = decide_native_typography_eligibility(brief)

    assert decision.eligible is False
    assert decision.recommended_lane == "manual_review"
