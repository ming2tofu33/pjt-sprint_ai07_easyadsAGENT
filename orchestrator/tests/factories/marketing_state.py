from copy import deepcopy


def make_marketing_request(*, mode: str = "auto_pilot", job_id: str = "job_test", **overrides) -> dict:
    request = {
        "user_input": "ready",
        "job_id": job_id,
        "thread_id": job_id,
        "copy_generation_mode": mode,
        "context": {
            "business_type": "restaurant",
            "item_or_service": "삼겹살",
            "promotion_goal": "reservation_cta",
            "extra": {"ad_format": "instagram_feed"},
        },
    }
    request.update(overrides)
    return deepcopy(request)
