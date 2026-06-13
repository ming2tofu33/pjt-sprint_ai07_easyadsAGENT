def make_archive_item_response_payload(**overrides) -> dict[str, object]:
    payload = {
        "ad_id": "archive_pub_1",
        "job_id": "job_pub_1",
        "output_id": "out_pub_1",
        "thread_id": "thread_pub_1",
        "title": "테스트 광고",
        "image_url": "https://cdn.example.com/image.png",
        "status": "saved",
        "source": "generated",
    }
    payload.update(overrides)
    return payload
