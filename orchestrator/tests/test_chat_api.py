from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from orchestrator.app.api import chat as chat_api
from orchestrator.app.main import app
from orchestrator.app.t2i.schemas import T2IResult


PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\xcfP"
    b"\x0f\x00\x03\x86\x01\x80Z4}k\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_chat_start_returns_inferred_context_and_copy_candidates():
    client = TestClient(app)

    response = client.post(
        "/v1/marketing/chat/start",
        json={"userInput": "우리 카페 딸기라떼 신메뉴 광고 만들어줘", "adFormat": "instagram_feed"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["jobId"].startswith("chat_")
    assert payload["threadId"].endswith("_thread")
    assert payload["context"] == {
        "businessType": "카페",
        "itemOrService": "딸기라떼",
        "promotionGoal": "신메뉴 출시",
    }
    assert [candidate["id"] for candidate in payload["copyCandidates"]] == ["copy_1", "copy_2"]
    assert payload["recommendedCopyId"] == "copy_1"


def test_chat_start_returns_option_question_when_context_is_missing():
    client = TestClient(app)

    response = client.post(
        "/v1/marketing/chat/start",
        json={"userInput": "광고 만들어줘", "adFormat": "instagram_feed"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["type"] == "option_question"
    assert payload["jobId"].startswith("chat_")
    assert payload["threadId"].endswith("_thread")
    assert payload["question"]["field"] == "business_type"
    assert payload["question"]["question"] == "어떤 업종의 광고인가요?"


def test_chat_start_passes_reference_template_to_graph(monkeypatch):
    captured = {}

    class FakeGraph:
        def invoke(self, state, config):
            captured["state"] = state
            captured["config"] = config
            return {
                "job_id": state["job_id"],
                "thread_id": state["thread_id"],
                "status": "generating_copy_candidates",
                "copy_generation_mode": "suggest_candidates",
                "context": {
                    "business_type": "cafe",
                    "item_or_service": "수박주스",
                    "promotion_goal": "new_launch",
                    "extra": {"ad_format": "instagram_feed"},
                },
                "copy_candidates": [{"id": "copy_1", "headline": "여름엔 수박주스"}],
            }

    monkeypatch.setattr(chat_api, "_GRAPH", FakeGraph())
    client = TestClient(app)

    response = client.post(
        "/v1/marketing/chat/start",
        json={
            "userInput": "우리 카페 수박주스 신메뉴 광고 만들어줘",
            "adFormat": "instagram_feed",
            "selectedReferenceTemplateId": "temp_watermelon_juice_feed",
            "referenceImagePath": "data/uploads/reference_1.png",
        },
    )

    assert response.status_code == 200
    assert captured["state"]["entry_mode"] == "chat_start"
    assert captured["state"]["selected_reference_template_id"] == "temp_watermelon_juice_feed"
    assert captured["state"]["reference_image_path"] == "data/uploads/reference_1.png"
    assert captured["state"]["context"]["extra"]["reference_image_path"] == "data/uploads/reference_1.png"
    assert captured["config"]["configurable"]["thread_id"] == response.json()["threadId"]


def test_photo_start_invokes_graph_with_photo_entry(monkeypatch):
    captured = {}

    class FakeGraph:
        def invoke(self, state, config):
            captured["state"] = state
            captured["config"] = config
            return {
                "job_id": state["job_id"],
                "thread_id": state["thread_id"],
                "status": "generating_copy_candidates",
                "context": {
                    "business_type": "cafe",
                    "item_or_service": "딸기라떼",
                    "promotion_goal": "new_launch",
                    "extra": {"ad_format": "instagram_feed"},
                },
                "copy_candidates": [{"id": "copy_1", "headline": "사진 속 메뉴를 오늘의 신메뉴로"}],
            }

    from orchestrator.app.api import photo as photo_api

    monkeypatch.setattr(photo_api, "_GRAPH", FakeGraph())
    client = TestClient(app)

    response = client.post(
        "/v1/marketing/photo/start",
        json={
            "userInput": "이 사진으로 신메뉴 광고 만들어줘",
            "sourceImagePath": "data/uploads/menu.png",
            "adFormat": "instagram_feed",
            "renderProfile": "premium_api",
            "selectedReferenceTemplateId": "temp_watermelon_juice_feed",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["jobId"].startswith("photo_")
    assert payload["threadId"].endswith("_thread")
    assert payload["context"]["itemOrService"] == "딸기라떼"
    assert payload["copyCandidates"][0]["headline"] == "사진 속 메뉴를 오늘의 신메뉴로"
    assert captured["state"]["entry_mode"] == "photo_start"
    assert captured["state"]["source_image_path"] == "data/uploads/menu.png"
    assert captured["state"]["render_profile"] == "premium_api"
    assert captured["state"]["copy_generation_mode"] == "suggest_candidates"
    assert captured["state"]["selected_reference_template_id"] == "temp_watermelon_juice_feed"
    assert captured["state"]["context"]["extra"]["ad_format"] == "instagram_feed"
    assert captured["state"]["context"]["extra"]["source_image_path"] == "data/uploads/menu.png"
    assert captured["config"]["configurable"]["thread_id"] == payload["threadId"]


def test_photo_start_can_return_option_question(monkeypatch):
    class FakeGraph:
        def invoke(self, state, config):
            return {
                "__interrupt__": [
                    type(
                        "InterruptValue",
                        (),
                        {
                            "value": {
                                "type": "option_question",
                                "job_id": state["job_id"],
                                "thread_id": state["thread_id"],
                                "option_question": {
                                    "field": "business_type",
                                    "question": "어떤 업종의 광고인가요?",
                                    "options": [{"id": 1, "label": "카페/디저트", "value": "cafe"}],
                                },
                            }
                        },
                    )()
                ],
                "job_id": state["job_id"],
                "thread_id": state["thread_id"],
                "status": "waiting_user_selection",
                "context": {"extra": {}},
                "missing_fields": ["business_type"],
            }

    from orchestrator.app.api import photo as photo_api

    monkeypatch.setattr(photo_api, "_GRAPH", FakeGraph())
    client = TestClient(app)

    response = client.post(
        "/v1/marketing/photo/start",
        json={"userInput": "이 사진으로 광고 만들어줘", "sourceImagePath": "data/uploads/menu.png"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["type"] == "option_question"
    assert payload["question"]["field"] == "business_type"
    assert payload["missingFields"] == ["business_type"]


def test_photo_start_option_question_can_resume_via_chat_answer(tmp_path):
    source = tmp_path / "menu.png"
    source.write_bytes(PNG_1X1)
    client = TestClient(app)
    start = client.post(
        "/v1/marketing/photo/start",
        json={
            "userInput": "이 사진으로 할인 광고 만들어줘",
            "sourceImagePath": str(source),
            "adFormat": "instagram_feed",
            "renderProfile": "premium_api",
        },
    ).json()

    response = client.post(
        "/v1/marketing/chat/answer",
        json={
            "jobId": start["jobId"],
            "threadId": start["threadId"],
            "field": start["question"]["field"],
            "value": "cafe",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["type"] == "option_question"
    assert payload["context"]["businessType"] == "카페"
    assert payload["question"]["field"] == "item_or_service"


def test_photo_flow_passes_uploaded_image_to_final_t2i_request(monkeypatch, tmp_path):
    from orchestrator.app.llm.nodes import t2i_generation as t2i_generation_module

    source = tmp_path / "uploaded-menu.png"
    Image.new("RGB", (96, 96), (230, 80, 120)).save(source)
    captured = {}

    def fake_generate_image_v1(
        prompt,
        input_image_paths=None,
        negative_prompt=None,
        engine_preference=None,
        width=1024,
        height=1024,
        seed=None,
        num_images=1,
        output_dir=None,
        metadata=None,
    ):
        captured["prompt"] = prompt
        captured["input_image_paths"] = input_image_paths
        captured["engine_preference"] = engine_preference
        captured["metadata"] = metadata or {}
        output_path = Path(output_dir or tmp_path) / "uploaded-source-used.png"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (width, height), (245, 220, 225)).save(output_path)
        return T2IResult(
            engine="gpt_image_1",
            image_paths=[str(output_path)],
            seed=seed,
            latency_ms=1,
            width=width,
            height=height,
            prompt=prompt,
            negative_prompt=negative_prompt or "",
            metadata={**(metadata or {}), "api_operation": "edit", "input_image_paths": input_image_paths or []},
            error=None,
        )

    monkeypatch.setattr(t2i_generation_module, "generate_image_v1", fake_generate_image_v1)
    client = TestClient(app)

    payload = client.post(
        "/v1/marketing/photo/start",
        json={
            "userInput": "이 사진으로 할인 이벤트 광고 만들어줘",
            "sourceImagePath": str(source),
            "adFormat": "instagram_feed",
            "renderProfile": "premium_api",
        },
    ).json()

    answers = {
        "business_type": "cafe",
        "item_or_service": "new_item",
        "promotion_goal": "discount_event",
    }
    while payload.get("type") == "option_question":
        field = payload["question"]["field"]
        response = client.post(
            "/v1/marketing/chat/answer",
            json={
                "jobId": payload["jobId"],
                "threadId": payload["threadId"],
                "field": field,
                "value": answers[field],
            },
        )
        assert response.status_code == 200
        payload = response.json()

    brief_response = client.post(
        "/v1/marketing/chat/brief",
        json={
            "jobId": payload["jobId"],
            "threadId": payload["threadId"],
            "selectedCopyId": payload["recommendedCopyId"],
            "selectedChannelId": "instagram_feed",
            "selectedTone": "감성적인",
            "customDirection": "",
        },
    )

    assert brief_response.status_code == 200
    assert captured["input_image_paths"] == [str(source)]
    assert captured["engine_preference"] == "gpt_image_1"
    assert captured["metadata"]["source_image_path"] == str(source)
    assert captured["metadata"]["vision_pipeline_enabled"] is True
    assert brief_response.json()["brief"]["finalImagePath"].endswith("final_composite.png")


def test_chat_start_no_copy_returns_brief_ready_response():
    client = TestClient(app)

    response = client.post(
        "/v1/marketing/chat/start",
        json={
            "userInput": "우리 카페 딸기라떼 신메뉴 인스타 피드 이미지만 만들어줘",
            "adFormat": "instagram_feed",
            "renderProfile": "fast",
            "copyGenerationMode": "no_copy",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["type"] == "brief_ready"
    assert payload["copyGenerationMode"] == "no_copy"
    assert payload["brief"]["copy"] == "문구 없이 이미지로만"
    assert payload["brief"]["finalImagePath"]


def test_photo_start_no_copy_returns_brief_ready_response(tmp_path):
    source = tmp_path / "menu.png"
    source.write_bytes(PNG_1X1)
    client = TestClient(app)

    response = client.post(
        "/v1/marketing/photo/start",
        json={
            "userInput": "우리 카페 딸기라떼 신메뉴 인스타 피드 이미지만 만들어줘",
            "sourceImagePath": str(source),
            "adFormat": "instagram_feed",
            "renderProfile": "fast",
            "copyGenerationMode": "no_copy",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["type"] == "brief_ready"
    assert payload["copyGenerationMode"] == "no_copy"
    assert payload["brief"]["copy"] == "문구 없이 이미지로만"
    assert payload["brief"]["finalImagePath"]


def test_chat_start_auto_pilot_returns_brief_ready_response():
    client = TestClient(app)

    response = client.post(
        "/v1/marketing/chat/start",
        json={
            "userInput": "우리 카페 딸기라떼 신메뉴 인스타 피드 광고 만들어줘",
            "adFormat": "instagram_feed",
            "renderProfile": "fast",
            "copyGenerationMode": "auto_pilot",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["type"] == "brief_ready"
    assert payload["copyGenerationMode"] == "auto_pilot"
    assert payload["brief"]["copy"]
    assert payload["brief"]["copy"] != "문구 없이 이미지로만"
    assert payload["brief"]["finalImagePath"]


def test_photo_start_auto_pilot_returns_brief_ready_response(tmp_path):
    source = tmp_path / "menu.png"
    source.write_bytes(PNG_1X1)
    client = TestClient(app)

    response = client.post(
        "/v1/marketing/photo/start",
        json={
            "userInput": "우리 카페 딸기라떼 신메뉴 인스타 피드 광고 만들어줘",
            "sourceImagePath": str(source),
            "adFormat": "instagram_feed",
            "renderProfile": "fast",
            "copyGenerationMode": "auto_pilot",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["type"] == "brief_ready"
    assert payload["copyGenerationMode"] == "auto_pilot"
    assert payload["brief"]["copy"]
    assert payload["brief"]["copy"] != "문구 없이 이미지로만"
    assert payload["brief"]["finalImagePath"]


def test_chat_start_custom_copy_returns_brief_ready_response():
    client = TestClient(app)

    response = client.post(
        "/v1/marketing/chat/start",
        json={
            "userInput": "우리 카페 딸기라떼 신메뉴 인스타 피드 광고 만들어줘",
            "adFormat": "instagram_feed",
            "renderProfile": "fast",
            "copyGenerationMode": "custom_input",
            "userCustomHeadline": "오늘만 딸기라떼 반값",
            "userCustomSubcopy": "오후 2시부터 5시까지",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["type"] == "brief_ready"
    assert payload["copyGenerationMode"] == "custom_input"
    assert payload["brief"]["copy"] == "오늘만 딸기라떼 반값"
    assert payload["brief"]["finalImagePath"]


def test_photo_start_custom_copy_returns_brief_ready_response(tmp_path):
    source = tmp_path / "menu.png"
    source.write_bytes(PNG_1X1)
    client = TestClient(app)

    response = client.post(
        "/v1/marketing/photo/start",
        json={
            "userInput": "우리 카페 딸기라떼 신메뉴 인스타 피드 광고 만들어줘",
            "sourceImagePath": str(source),
            "adFormat": "instagram_feed",
            "renderProfile": "fast",
            "copyGenerationMode": "custom_input",
            "userCustomHeadline": "오늘만 딸기라떼 반값",
            "userCustomSubcopy": "오후 2시부터 5시까지",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["type"] == "brief_ready"
    assert payload["copyGenerationMode"] == "custom_input"
    assert payload["brief"]["copy"] == "오늘만 딸기라떼 반값"
    assert payload["brief"]["finalImagePath"]


def test_chat_answer_resumes_to_next_turn():
    client = TestClient(app)
    start = client.post(
        "/v1/marketing/chat/start",
        json={"userInput": "광고 만들어줘", "adFormat": "instagram_feed"},
    ).json()

    response = client.post(
        "/v1/marketing/chat/answer",
        json={
            "jobId": start["jobId"],
            "threadId": start["threadId"],
            "field": start["question"]["field"],
            "value": "cafe",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["type"] == "option_question"
    assert payload["question"]["field"] == "item_or_service"


def test_chat_answer_uses_display_label_for_item_option_values():
    client = TestClient(app)
    start = client.post(
        "/v1/marketing/chat/start",
        json={"userInput": "아무 광고나 만들어줘", "adFormat": "instagram_feed"},
    ).json()
    business = client.post(
        "/v1/marketing/chat/answer",
        json={
            "jobId": start["jobId"],
            "threadId": start["threadId"],
            "field": start["question"]["field"],
            "value": "restaurant",
        },
    ).json()
    item = client.post(
        "/v1/marketing/chat/answer",
        json={
            "jobId": start["jobId"],
            "threadId": start["threadId"],
            "field": business["question"]["field"],
            "value": "reservation_service",
        },
    ).json()

    response = client.post(
        "/v1/marketing/chat/answer",
        json={
            "jobId": start["jobId"],
            "threadId": start["threadId"],
            "field": item["question"]["field"],
            "value": "reservation_cta",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["type"] == "copy_candidates"
    assert payload["context"]["itemOrService"] == "예약 서비스"
    rendered = " ".join(candidate["headline"] for candidate in payload["copyCandidates"])
    assert "reservation_service" not in rendered
    assert "예약 서비스" in rendered
    assert "한 판" not in rendered
    assert "회식은 역시 예약 서비스" not in rendered


def test_chat_brief_resumes_graph_with_selected_copy():
    client = TestClient(app)
    start = client.post(
        "/v1/marketing/chat/start",
        json={"userInput": "우리 카페 딸기라떼 신메뉴 광고 만들어줘", "adFormat": "instagram_feed"},
    ).json()

    response = client.post(
        "/v1/marketing/chat/brief",
        json={
            "jobId": start["jobId"],
            "threadId": start["threadId"],
            "selectedCopyId": "copy_1",
            "selectedChannelId": "instagram-story",
            "selectedTone": "상큼한",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "done"
    assert payload["brief"]["item"] == "딸기라떼"
    assert payload["brief"]["channel"] == "인스타 스토리 (9:16)"
    assert payload["brief"]["tone"] == "상큼한 분위기"
    assert payload["brief"]["imageDirection"] == "상큼한 분위기를 살려 딸기라떼 중심의 깔끔한 광고 배경과 문구 여백을 구성해요."
    assert payload["brief"]["copy"]
    assert payload["brief"]["finalImagePath"]


def test_chat_brief_resumes_graph_with_frontend_choices(monkeypatch):
    captured = {}

    class FakeGraph:
        def invoke(self, command, config):
            captured["resume"] = command.resume
            captured["config"] = config
            return {
                "job_id": "job_1",
                "thread_id": "thread_1",
                "status": "done",
                "context": {
                    "business_type": "cafe",
                    "item_or_service": "딸기라떼",
                    "promotion_goal": "new_launch",
                    "brand_tone": "깔끔한",
                    "extra": {
                        "selected_channel_id": "poster",
                        "selected_tone": "깔끔한",
                        "custom_direction": "제품을 크게",
                    },
                },
                "current_brief": {
                    "selected_channel_id": "poster",
                    "selected_tone": "깔끔한",
                    "custom_direction": "제품을 크게",
                },
                "marketing_copy": {"headline": "선택한 문구"},
                "image_prompt_spec": {"scene_description": "제품을 크게"},
                "final_image_path": "data/outputs/job_1/final_composite.png",
            }

    monkeypatch.setattr(chat_api, "_GRAPH", FakeGraph())
    client = TestClient(app)

    response = client.post(
        "/v1/marketing/chat/brief",
        json={
            "jobId": "job_1",
            "threadId": "thread_1",
            "selectedCopyId": "copy_2",
            "selectedChannelId": "poster",
            "selectedTone": "깔끔한",
            "customDirection": "제품을 크게",
        },
    )

    assert response.status_code == 200
    assert captured["config"]["configurable"]["thread_id"] == "thread_1"
    assert captured["resume"] == {
        "selected_copy_id": "copy_2",
        "selected_channel_id": "poster",
        "selected_ad_format": "poster",
        "selected_tone": "깔끔한",
        "custom_direction": "제품을 크게",
    }
    payload = response.json()
    assert payload["brief"]["tone"] == "깔끔한 분위기"
    assert payload["brief"]["channel"] == "포스터 (4:5)"
    assert payload["brief"]["imageDirection"] == "제품을 크게"


def test_chat_brief_hides_internal_image_prompt_from_user_summary(monkeypatch):
    class FakeGraph:
        def invoke(self, command, config):
            return {
                "job_id": "job_1",
                "thread_id": "thread_1",
                "status": "done",
                "context": {
                    "business_type": "restaurant",
                    "item_or_service": "예약 서비스",
                    "promotion_goal": "reservation_cta",
                    "brand_tone": "고급스러운",
                    "extra": {},
                },
                "current_brief": {
                    "selected_channel_id": "instagram-feed",
                    "selected_tone": "고급스러운",
                },
                "marketing_copy": {"headline": "방문 전, 예약 서비스로 편하게"},
                "image_prompt_spec": {"scene_description": "clean commercial advertising background for 예약 서비스"},
                "final_image_path": "data/outputs/job_1/final_composite.png",
            }

    monkeypatch.setattr(chat_api, "_GRAPH", FakeGraph())
    client = TestClient(app)

    response = client.post(
        "/v1/marketing/chat/brief",
        json={
            "jobId": "job_1",
            "threadId": "thread_1",
            "selectedCopyId": "copy_1",
            "selectedChannelId": "instagram-feed",
            "selectedTone": "고급스러운",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["brief"]["tone"] == "고급스러운 분위기"
    assert payload["brief"]["imageDirection"] == "고급스러운 분위기를 살려 예약 서비스 안내가 잘 보이도록 깔끔한 배경과 읽기 쉬운 여백을 구성해요."
    assert "clean commercial" not in payload["brief"]["imageDirection"]


def test_chat_start_accepts_selected_reference_template_id(monkeypatch):
    captured = {}

    class FakeGraph:
        def invoke(self, state, config):
            captured["state"] = state
            return {
                "job_id": state["job_id"],
                "thread_id": state["thread_id"],
                "status": "generating_copy_candidates",
                "context": {"business_type": "cafe", "item_or_service": "latte", "promotion_goal": "new_launch", "extra": {}},
                "copy_candidates": [{"id": "copy_1", "headline": "Latte"}],
            }

    monkeypatch.setattr(chat_api, "_GRAPH", FakeGraph())
    client = TestClient(app)

    response = client.post(
        "/v1/marketing/chat/start",
        json={
            "userInput": "Create a cafe ad",
            "selectedReferenceTemplateId": "seed_cafe_strawberry_feed_001",
            "copyGenerationMode": "auto_pilot",
        },
    )

    assert response.status_code == 200
    assert captured["state"]["selected_reference_template_id"] == "seed_cafe_strawberry_feed_001"
    assert captured["state"]["copy_generation_mode"] == "auto_pilot"
    assert captured["state"]["context"]["extra"]["selected_reference_template_id"] == "seed_cafe_strawberry_feed_001"


def test_photo_start_accepts_selected_reference_template_id(monkeypatch):
    captured = {}

    class FakeGraph:
        def invoke(self, state, config):
            captured["state"] = state
            return {
                "job_id": state["job_id"],
                "thread_id": state["thread_id"],
                "status": "generating_copy_candidates",
                "context": {"business_type": "cafe", "item_or_service": "latte", "promotion_goal": "new_launch", "extra": {}},
                "copy_candidates": [{"id": "copy_1", "headline": "Latte"}],
            }

    from orchestrator.app.api import photo as photo_api

    monkeypatch.setattr(photo_api, "_GRAPH", FakeGraph())
    client = TestClient(app)

    response = client.post(
        "/v1/marketing/photo/start",
        json={
            "userInput": "Create a photo ad",
            "sourceImagePath": "data/uploads/menu.png",
            "selectedReferenceTemplateId": "seed_cafe_strawberry_feed_001",
            "copyGenerationMode": "auto_pilot",
        },
    )

    assert response.status_code == 200
    assert captured["state"]["selected_reference_template_id"] == "seed_cafe_strawberry_feed_001"
    assert captured["state"]["copy_generation_mode"] == "auto_pilot"
    assert captured["state"]["context"]["extra"]["selected_reference_template_id"] == "seed_cafe_strawberry_feed_001"
