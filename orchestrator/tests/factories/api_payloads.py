def marketing_chat_start_payload(*, user_input: str = "移댄럹 愿묎퀬") -> dict[str, str]:
    return {"userInput": user_input}


def marketing_photo_start_payload(
    *,
    user_input: str = "移댄럹 愿묎퀬",
    source_image_path: str = "data/uploads/sample.png",
) -> dict[str, str]:
    return {"userInput": user_input, "sourceImagePath": source_image_path}


def generation_job_create_payload(**overrides) -> dict[str, object]:
    payload: dict[str, object] = {
        "user_input": "Create a cafe launch ad",
        "user_id": "user_1",
        "brand_kit_id": "bk_1",
        "selected_reference_template_id": "seed_cafe_strawberry_feed_001",
        "run_mode": "queued_only",
    }
    payload.update(overrides)
    return payload
