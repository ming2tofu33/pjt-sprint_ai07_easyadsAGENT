from orchestrator.app.llm.nodes.native_generation_review import native_generation_review_node


def test_native_generation_review_accepts_exact_texts():
    update = native_generation_review_node(
        {
            "native_creative_prompt_package": {"exact_allowed_texts": ["고급진 된장찌개", "진한 구수함 한 그릇"]},
            "native_generation_result": {"detected_texts": ["고급진 된장찌개", "진한 구수함 한 그릇"]},
        }
    )

    assert update["native_generation_review"]["decision"] == "accept"


def test_native_generation_review_rejects_unexpected_text():
    update = native_generation_review_node(
        {
            "native_creative_prompt_package": {"exact_allowed_texts": ["고급진 된장찌개"]},
            "native_generation_result": {"detected_texts": ["고급진 된장찌개", "Learn More"]},
        }
    )

    assert update["native_generation_review"]["decision"] == "reject"
