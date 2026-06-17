"""Consolidated chat threads tests.

Merged from:
- orchestrator/tests/test_chat_api.py
- orchestrator/tests/test_chat_state_snapshot_service.py
- orchestrator/tests/test_chat_state_snapshots_repository.py
- orchestrator/tests/test_chat_thread_service.py
- orchestrator/tests/test_chat_threads_repository.py
"""

from __future__ import annotations



# ===== from test_chat_api.py =====
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from orchestrator.app.api import chat as chat_api
from orchestrator.app.main import app
from orchestrator.app.t2i.schemas import T2IResult
from orchestrator.tests.factories.chat_threads import make_chat_thread_row
from orchestrator.tests.helpers.chat_threads import PNG_1X1
from orchestrator.tests.helpers.images import write_test_png


def test_chat_start_returns_inferred_context_and_copy_candidates():
    client = TestClient(app)

    response = client.post(
        "/v1/marketing/chat/start",
        json={"userInput": "\uc6b0\ub9ac \uce74\ud398 \ub538\uae30\ub77c\ub5bc \uc2e0\uba54\ub274 \uad11\uace0 \ub9cc\ub4e4\uc5b4\uc918", "adFormat": "instagram_feed"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["jobId"].startswith("chat_")
    assert payload["threadId"].endswith("_thread")
    assert payload["context"] == {
        "businessType": "cafe",
        "itemOrService": "\ub538\uae30\ub77c\ub5bc",
        "promotionGoal": None,
        "advertisedSubject": "\uc6b0\ub9ac \uce74\ud398 \ub538\uae30\ub77c\ub5bc",
        "advertisedSubjectType": "product",
        "campaignIntent": "new_menu_launch",
    }
    assert [candidate["id"] for candidate in payload["copyCandidates"]] == ["copy_1", "copy_2"]
    assert payload["recommendedCopyId"] in {"copy_1", "copy_2"}
    assert payload["copyCandidateOrigin"] == "rule_based"


def test_chat_start_returns_option_question_when_context_is_missing():
    client = TestClient(app)

    response = client.post(
        "/v1/marketing/chat/start",
        json={"userInput": "광고 만들어줘", "adFormat": "instagram_feed"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["type"] in {"option_question", "copy_candidates"}
    assert payload["jobId"].startswith("chat_")
    assert payload["threadId"].endswith("_thread")
    assert payload["question"]["field"] == "business_type"
    assert payload["question"]["question"] == "어떤 업종의 광고인가요?"


def test_brief_from_result_uses_advertised_subject_and_campaign_intent_label_fallback():
    brief = chat_api._brief_from_result(
        {
            "context": {"business_type": "store", "extra": {"ad_format": "banner"}},
            "current_brief": {
                "advertised_subject": "프리미엄 뷰티샵",
                "campaign_intent": "store_opening",
                "selected_channel_id": "banner",
            },
            "copy_generation_mode": "no_copy",
        },
        selected_channel_id="banner",
    )

    assert brief.item == "프리미엄 뷰티샵"
    assert brief.purpose == "신규 오픈 홍보"


def test_chat_start_option_question_uses_request_ad_format_as_selected_channel_fallback(monkeypatch):
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
                                    "options": [{"id": 1, "label": "카페", "value": "cafe"}],
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

    monkeypatch.setattr(chat_api, "get_marketing_graph", lambda: FakeGraph())
    client = TestClient(app)

    response = client.post(
        "/v1/marketing/chat/start",
        json={"userInput": "광고 만들어줘", "adFormat": "banner"},
    )

    assert response.status_code == 200
    assert response.json()["selectedChannelId"] == "banner"


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

    fake_graph = FakeGraph()
    monkeypatch.setattr(chat_api, "get_marketing_graph", lambda: fake_graph)
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

    fake_graph = FakeGraph()
    monkeypatch.setattr(photo_api, "get_marketing_graph", lambda: fake_graph)
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


def test_photo_start_passes_selected_image_engine_to_graph(monkeypatch):
    captured = {}

    class FakeGraph:
        def invoke(self, state, config):
            captured["state"] = state
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
                "copy_candidates": [{"id": "copy_1", "headline": "사진 속 메뉴를 고품질 광고로"}],
            }

    from orchestrator.app.api import photo as photo_api

    fake_graph = FakeGraph()
    monkeypatch.setattr(photo_api, "get_marketing_graph", lambda: fake_graph)
    client = TestClient(app)

    response = client.post(
        "/v1/marketing/photo/start",
        json={
            "userInput": "이 사진으로 고품질 광고 만들어줘",
            "sourceImagePath": "data/uploads/menu.png",
            "adFormat": "instagram_feed",
            "imageGenerationEngine": "gpt_image_2",
            "requestedEngine": "gpt_image_2",
            "t2iEngine": "gpt_image_2",
        },
    )

    assert response.status_code == 200
    assert captured["state"]["engine"] == "gpt_image_2"
    assert captured["state"]["image_generation_engine"] == "gpt_image_2"
    assert captured["state"]["requested_engine"] == "gpt_image_2"
    assert captured["state"]["t2i_engine"] == "gpt_image_2"
    assert captured["state"]["context"]["extra"]["requested_engine"] == "gpt_image_2"


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

    fake_graph = FakeGraph()
    monkeypatch.setattr(photo_api, "get_marketing_graph", lambda: fake_graph)
    client = TestClient(app)

    response = client.post(
        "/v1/marketing/photo/start",
        json={"userInput": "이 사진으로 광고 만들어줘", "sourceImagePath": "data/uploads/menu.png"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["type"] in {"option_question", "copy_candidates"}
    assert payload["question"]["field"] == "business_type"
    assert payload["missingFields"] == ["business_type"]


def test_photo_start_option_question_uses_request_ad_format_as_selected_channel_fallback(monkeypatch):
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
                                    "options": [{"id": 1, "label": "카페", "value": "cafe"}],
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

    monkeypatch.setattr(photo_api, "get_marketing_graph", lambda: FakeGraph())
    client = TestClient(app)

    response = client.post(
        "/v1/marketing/photo/start",
        json={"userInput": "사진으로 광고 만들어줘", "sourceImagePath": "data/uploads/menu.png", "adFormat": "banner"},
    )

    assert response.status_code == 200
    assert response.json()["selectedChannelId"] == "banner"


def test_photo_start_option_question_can_resume_via_chat_answer(tmp_path):
    source = tmp_path / "menu.png"
    write_test_png(source, color=(230, 80, 120))
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
    assert payload["type"] in {"option_question", "copy_candidates"}
    assert payload["context"]["businessType"] == "cafe"
    if payload["type"] == "option_question":
        assert payload["question"]["field"] == "item_or_service"


def test_photo_flow_passes_uploaded_image_to_final_t2i_request(monkeypatch, tmp_path):
    from orchestrator.app.llm.nodes import t2i_generation as t2i_generation_module

    source = tmp_path / "uploaded-menu.png"
    write_test_png(source, color=(230, 80, 120))
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
        write_test_png(output_path, size=(width, height), color=(245, 220, 225))
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
    brief_payload = brief_response.json()["brief"]
    assert brief_payload["copy"]
    assert brief_payload["finalImagePath"].endswith("final_composite.png")


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
    assert payload["selectedChannelId"] == "instagram-feed"
    assert payload["brief"]["selectedChannelId"] == "instagram-feed"
    assert payload["brief"]["copy"] == "문구 없이 이미지로만"
    assert payload["brief"]["finalImagePath"].endswith(".png")


def test_photo_start_no_copy_returns_brief_ready_response(tmp_path):
    source = tmp_path / "menu.png"
    write_test_png(source, color=(230, 80, 120))
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
    assert payload["selectedChannelId"] == "instagram-feed"
    assert payload["brief"]["selectedChannelId"] == "instagram-feed"
    assert payload["brief"]["copy"] == "문구 없이 이미지로만"
    assert payload["brief"]["finalImagePath"].endswith(".png")


def test_chat_start_brief_ready_preserves_banner_selected_channel(monkeypatch):
    class FakeGraph:
        def invoke(self, state, config):
            return {
                "job_id": state["job_id"],
                "thread_id": state["thread_id"],
                "status": "done",
                "copy_generation_mode": "no_copy",
                "context": {
                    "business_type": "store",
                    "item_or_service": "signature_item",
                    "promotion_goal": "new_launch",
                    "extra": {"ad_format": "banner"},
                },
                "current_brief": {"selected_channel_id": "banner"},
                "final_image_path": "data/outputs/job_banner/final_composite.png",
            }

    monkeypatch.setattr(chat_api, "get_marketing_graph", lambda: FakeGraph())
    client = TestClient(app)

    response = client.post(
        "/v1/marketing/chat/start",
        json={"userInput": "배너 광고 만들어줘", "adFormat": "banner", "copyGenerationMode": "no_copy"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["selectedChannelId"] == "banner"
    assert payload["brief"]["selectedChannelId"] == "banner"


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
    assert payload["brief"]["finalImagePath"].endswith(".png")


def test_photo_start_auto_pilot_returns_brief_ready_response(tmp_path):
    source = tmp_path / "menu.png"
    write_test_png(source, color=(230, 80, 120))
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
    assert payload["brief"]["finalImagePath"].endswith(".png")


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
    assert payload["brief"]["copy"] == "오늘만 딸기라떼 반값\n오후 2시부터 5시까지"
    assert payload["brief"]["finalImagePath"].endswith(".png")


def test_photo_start_custom_copy_returns_brief_ready_response(tmp_path):
    source = tmp_path / "menu.png"
    write_test_png(source, color=(230, 80, 120))
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
    assert payload["brief"]["copy"] == "오늘만 딸기라떼 반값\n오후 2시부터 5시까지"
    assert payload["brief"]["finalImagePath"].endswith(".png")


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


def test_chat_start_copy_candidates_use_request_ad_format_as_selected_channel_fallback(monkeypatch):
    class FakeGraph:
        def invoke(self, state, config):
            return {
                "job_id": state["job_id"],
                "thread_id": state["thread_id"],
                "status": "generating_copy_candidates",
                "context": {
                    "business_type": "cafe",
                    "item_or_service": "latte",
                    "promotion_goal": "new_launch",
                    "extra": {},
                },
                "copy_candidates": [{"id": "copy_1", "headline": "배너 문구"}],
            }

    monkeypatch.setattr(chat_api, "get_marketing_graph", lambda: FakeGraph())
    client = TestClient(app)

    response = client.post(
        "/v1/marketing/chat/start",
        json={"userInput": "배너 광고", "adFormat": "banner"},
    )

    assert response.status_code == 200
    assert response.json()["selectedChannelId"] == "banner"


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

    if item["type"] == "option_question":
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
    else:
        payload = item
    assert payload["type"] == "copy_candidates"
    assert payload["context"]["itemOrService"] != "reservation_service"
    rendered = " ".join(candidate["headline"] for candidate in payload["copyCandidates"])
    assert "reservation_service" not in rendered
    assert rendered
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
    assert payload["brief"]["finalImagePath"].endswith(".png")


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

    fake_graph = FakeGraph()
    monkeypatch.setattr(chat_api, "get_marketing_graph", lambda: fake_graph)
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
def test_chat_brief_normalizes_selected_channel_id_from_ad_format(monkeypatch):
    captured = {}

    class FakeGraph:
        def invoke(self, command, config):
            captured["resume"] = command.resume
            return {
                "job_id": "job_1",
                "thread_id": "thread_1",
                "status": "done",
                "context": {
                    "business_type": "cafe",
                    "item_or_service": "latte",
                    "promotion_goal": "new_launch",
                    "extra": {"ad_format": "instagram_story"},
                },
                "current_brief": {
                    "selected_channel_id": "instagram-story",
                    "selected_tone": "fresh",
                },
                "marketing_copy": {"headline": "라떼 광고"},
                "final_image_path": "data/outputs/job_1/final_composite.png",
            }

    monkeypatch.setattr(chat_api, "get_marketing_graph", lambda: FakeGraph())
    client = TestClient(app)

    response = client.post(
        "/v1/marketing/chat/brief",
        json={
            "jobId": "job_1",
            "threadId": "thread_1",
            "selectedCopyId": "copy_1",
            "selectedChannelId": "instagram_story",
            "selectedTone": "fresh",
        },
    )

    assert response.status_code == 200
    assert captured["resume"]["selected_channel_id"] == "instagram-story"
    assert captured["resume"]["selected_ad_format"] == "instagram_story"
    payload = response.json()
    assert payload["selectedChannelId"] == "instagram-story"
    assert payload["brief"]["selectedChannelId"] == "instagram-story"


def test_chat_brief_does_not_force_instagram_feed_when_selected_channel_is_missing(monkeypatch):
    captured = {}

    class FakeGraph:
        def invoke(self, command, config):
            captured["resume"] = command.resume
            return {
                "job_id": "job_1",
                "thread_id": "thread_1",
                "status": "done",
                "context": {
                    "business_type": "cafe",
                    "item_or_service": "latte",
                    "promotion_goal": "new_launch",
                    "extra": {"ad_format": "banner"},
                },
                "current_brief": {
                    "selected_channel_id": "banner",
                    "selected_tone": "fresh",
                },
                "marketing_copy": {"headline": "배너 광고"},
                "final_image_path": "data/outputs/job_1/final_composite.png",
            }

    monkeypatch.setattr(chat_api, "get_marketing_graph", lambda: FakeGraph())
    client = TestClient(app)

    response = client.post(
        "/v1/marketing/chat/brief",
        json={
            "jobId": "job_1",
            "threadId": "thread_1",
            "selectedCopyId": "copy_1",
            "selectedTone": "fresh",
        },
    )

    assert response.status_code == 200
    assert "selected_channel_id" not in captured["resume"]
    assert "selected_ad_format" not in captured["resume"]
    payload = response.json()
    assert payload["selectedChannelId"] == "banner"
    assert payload["brief"]["selectedChannelId"] == "banner"


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

    fake_graph = FakeGraph()
    monkeypatch.setattr(chat_api, "get_marketing_graph", lambda: fake_graph)
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

    fake_graph = FakeGraph()
    monkeypatch.setattr(chat_api, "get_marketing_graph", lambda: fake_graph)
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

    fake_graph = FakeGraph()
    monkeypatch.setattr(photo_api, "get_marketing_graph", lambda: fake_graph)
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


# ===== from test_chat_state_snapshot_service.py =====
from datetime import datetime, timezone

from orchestrator.app.chat_threads import state_service


def test_snapshot_response_accepts_database_datetime_created_at():
    snapshot = state_service._to_response(
        {
            "snapshot_id": "snapshot_1",
            "thread_id": "thread_1",
            "snapshot_version": 1,
            "schema_version": 1,
            "snapshot_kind": "input",
            "state_payload": {"user_input": "hello"},
            "changed_fields": ["user_input"],
            "reference_template_snapshot": {},
            "brand_kit_snapshot": {},
            "metadata": {},
            "created_at": datetime(2026, 6, 6, tzinfo=timezone.utc),
        }
    )

    assert snapshot.created_at == "2026-06-06T00:00:00+00:00"


def test_memory_snapshot_service():
    state_service.reset_chat_state_snapshot_store_for_tests()

    # Mock get_chat_thread
    from orchestrator.app.chat_threads import service as chat_service

    class MockThread:
        thread_id = "t1"

    original_get_chat_thread = chat_service.get_chat_thread
    chat_service.get_chat_thread = lambda *args, **kwargs: MockThread()

    try:
        snap1 = state_service.save_thread_state_snapshot(
            public_thread_id="t1",
            workspace_id="w1",
            snapshot_kind="input",
            state_payload={"user_input": "hello"},
            changed_fields=["user_input"],
        )
        assert snap1.snapshot_version == 1
        assert snap1.state_payload["user_input"] == "hello"

        snap2 = state_service.save_thread_state_snapshot(
            public_thread_id="t1",
            workspace_id="w1",
            snapshot_kind="job_completed",
            state_payload={"final_brief": {"a": 1}},
            changed_fields=["final_brief"],
        )
        assert snap2.snapshot_version == 2

        latest = state_service.get_latest_thread_state_snapshot("t1", "w1")
        assert latest.snapshot_version == 2
        assert latest.state_payload["final_brief"] == {"a": 1}

        lst, total = state_service.list_thread_state_snapshots("t1", "w1")
        assert total == 2
        assert len(lst) == 2
    finally:
        chat_service.get_chat_thread = original_get_chat_thread


def test_snapshot_serialization_keeps_ui_visible_generation_state():
    from orchestrator.app.chat_threads.state_snapshot import serialize_marketing_state_snapshot

    snapshot = serialize_marketing_state_snapshot(
        {
            "job_id": "job_ui_state",
            "thread_id": "thread_ui_state",
            "user_input": "카페 신메뉴 광고 만들어줘",
            "copy_candidates": [{"id": "copy_1", "headline": "오늘만 신메뉴"}],
            "copy_candidate_origin": "llm",
            "selected_copy_id": "copy_1",
            "progress_state": {"progress_percent": 65, "current_stage": "modal_running", "message": "이미지를 만들고 있어요."},
            "ocr_gate_decision": "manual_review",
            "ocr_gate_status": "fail",
            "ocr_gate_retry_feedback": ["문구 위치를 다시 확인해주세요."],
            "quality_gate_decision": "warn",
            "quality_gate_status": "manual_review",
            "result_payload": {
                "status": "done",
                "final_image_url": "https://assets.example.com/final.png",
                "qualityDecision": "manual_review",
                "requiresManualReview": True,
                "qualityRejected": False,
            },
            "raw_provider_response": {"api_key": "sk-hidden"},
        }
    )

    assert snapshot["copy_candidate_origin"] == "llm"
    assert snapshot["selected_copy_id"] == "copy_1"
    assert snapshot["progress_state"]["current_stage"] == "modal_running"
    assert snapshot["ocr_gate_decision"] == "manual_review"
    assert snapshot["ocr_gate_retry_feedback"] == ["문구 위치를 다시 확인해주세요."]
    assert snapshot["quality_gate_decision"] == "warn"
    assert snapshot["result_payload"]["requiresManualReview"] is True
    assert "raw_provider_response" not in snapshot
    assert "sk-hidden" not in str(snapshot)


# ===== from test_chat_state_snapshots_repository.py =====
from orchestrator.app.db.repositories import chat_state_snapshots as repo
import pytest

def test_chat_state_snapshot_repo_requires_connection():
    with pytest.raises(Exception):
        repo.create_chat_state_snapshot(
            public_snapshot_id="s",
            public_thread_id="t",
            workspace_id="w",
            snapshot_kind="k",
            state_payload={},
            changed_fields=[],
            connection=None  # will fail db_transaction without object connection?
            # Actually db_transaction creates a new connection if none provided, but we assume it throws runtime error if no DB configured or raises Postgres backend error.
        )


# ===== from test_chat_thread_service.py =====
import ast
from pathlib import Path
from contextlib import contextmanager

import pytest

from orchestrator.app.api.schemas.chat_threads import ChatMessageCreateRequest, ChatThreadCreateRequest, ChatThreadUpdateRequest
from orchestrator.app.chat_threads.errors import ChatThreadHasActiveJobError, ChatThreadLimitReachedError
from orchestrator.app.chat_threads.service import (
    append_chat_message,
    archive_chat_thread,
    create_chat_thread,
    get_chat_thread,
    list_chat_messages,
    list_chat_threads,
    clear_thread_active_job,
    reset_chat_thread_store_for_tests,
    restore_chat_thread,
    set_thread_active_job,
    set_thread_final_output,
    update_chat_thread,
)


@pytest.fixture(autouse=True)
def memory_backend(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "memory")
    reset_chat_thread_store_for_tests()
    yield
    reset_chat_thread_store_for_tests()


def test_memory_thread_owner_scope_and_pagination_total(monkeypatch):
    # Raise the per-workspace cap so this pagination scenario can seed >3 threads.
    monkeypatch.setattr(
        "orchestrator.app.chat_threads.service.db_settings.get_max_threads_per_workspace",
        lambda: 99,
    )
    for index in range(5):
        create_chat_thread(ChatThreadCreateRequest(user_id="user_a", title=f"A {index}"))
    create_chat_thread(ChatThreadCreateRequest(user_id="user_b", title="B"))

    threads, total = list_chat_threads(user_id="user_a", limit=2, offset=0)

    assert total == 5
    assert len(threads) == 2
    assert all(get_chat_thread(thread.thread_id, user_id="user_b") is None for thread in threads)


def test_memory_thread_list_can_skip_exact_total(monkeypatch):
    monkeypatch.setattr(
        "orchestrator.app.chat_threads.service.db_settings.get_max_threads_per_workspace",
        lambda: 99,
    )
    for index in range(5):
        create_chat_thread(ChatThreadCreateRequest(user_id="user_a", title=f"A {index}"))

    threads, total = list_chat_threads(user_id="user_a", limit=2, offset=0, include_total=False)

    assert len(threads) == 2
    assert total == 2


def test_memory_thread_limit_blocks_fourth_thread():
    # Default cap is 3 non-archived threads per owner in the memory backend.
    for index in range(3):
        create_chat_thread(ChatThreadCreateRequest(user_id="user_a", title=f"A {index}"))

    with pytest.raises(ChatThreadLimitReachedError) as exc_info:
        create_chat_thread(ChatThreadCreateRequest(user_id="user_a", title="overflow"))
    assert exc_info.value.error_code == "thread_limit_reached"

    # A different owner is unaffected.
    other = create_chat_thread(ChatThreadCreateRequest(user_id="user_b", title="B"))
    assert other.thread_id


def test_guest_thread_limit_uses_guest_owner_id():
    for index in range(3):
        create_chat_thread(ChatThreadCreateRequest(user_id="guest_uuid_1", title=f"Guest {index}"))

    with pytest.raises(ChatThreadLimitReachedError):
        create_chat_thread(ChatThreadCreateRequest(user_id="guest_uuid_1", title="Guest overflow"))

    other_guest = create_chat_thread(ChatThreadCreateRequest(user_id="guest_uuid_2", title="Other guest"))
    assert other_guest.thread_id


def test_memory_thread_limit_frees_slot_after_archive():
    threads = [
        create_chat_thread(ChatThreadCreateRequest(user_id="user_a", title=f"A {i}"))
        for i in range(3)
    ]
    archive_chat_thread(threads[0].thread_id, user_id="user_a")

    # Archiving the first thread frees a slot, so a new thread can be created.
    fresh = create_chat_thread(ChatThreadCreateRequest(user_id="user_a", title="fresh"))
    assert fresh.thread_id


def test_restore_chat_thread_reopens_archived_thread():
    created = create_chat_thread(ChatThreadCreateRequest(user_id="restore_user", title="복원 테스트"))
    archived = archive_chat_thread(created.thread_id, user_id="restore_user", force=True)

    restored = restore_chat_thread(archived.thread_id, user_id="restore_user")

    assert restored is not None
    assert restored.thread_id == created.thread_id
    assert restored.archived_at is None
    assert restored.status == "draft"


def test_restore_chat_thread_keeps_active_limit():
    threads = [
        create_chat_thread(ChatThreadCreateRequest(user_id="restore_limit_user", title=f"A {index}"))
        for index in range(3)
    ]
    archived = archive_chat_thread(threads[0].thread_id, user_id="restore_limit_user", force=True)
    create_chat_thread(ChatThreadCreateRequest(user_id="restore_limit_user", title="replacement"))

    with pytest.raises(ChatThreadLimitReachedError):
        restore_chat_thread(archived.thread_id, user_id="restore_limit_user")


def test_restore_chat_thread_route_reopens_archived_thread():
    client = TestClient(app)
    created = client.post(
        "/api/v1/chat-threads",
        json={"title": "복원 라우트 테스트", "userId": "restore-route-user", "accountType": "guest"},
    ).json()["thread"]
    archive = client.post(
        f"/api/v1/chat-threads/{created['thread_id']}/archive?userId=restore-route-user&accountType=guest",
        json={"force": True},
    )
    assert archive.status_code == 200

    response = client.post(
        f"/api/v1/chat-threads/{created['thread_id']}/restore?userId=restore-route-user&accountType=guest",
        json={},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["thread"]["thread_id"] == created["thread_id"]
    assert payload["thread"]["archived_at"] is None
    assert payload["thread"]["status"] == "draft"


def test_final_brief_and_message_payload_are_sanitized():
    thread = create_chat_thread(
        ChatThreadCreateRequest(
            user_id="user_a",
            final_brief={"safe": "visible", "apiKey": "sk-secret", "nested": {"rawLlmResponse": "blocked"}},
        )
    )
    assert thread.final_brief == {"safe": "visible", "nested": {}}

    msg = append_chat_message(
        thread.thread_id,
        ChatMessageCreateRequest(role="user", content="hello", payload={"safe": "visible", "hfToken": "hf-secret"}),
        user_id="user_a",
    )

    assert msg.payload == {"safe": "visible"}
    assert msg.created_by == "user_a"


def test_active_thread_cannot_be_archived():
    thread = create_chat_thread(ChatThreadCreateRequest(user_id="user_a", title="Active"))
    set_thread_active_job(thread.thread_id, "job_uuid", "job_public")

    with pytest.raises(ChatThreadHasActiveJobError):
        archive_chat_thread(thread.thread_id, user_id="user_a")


def test_active_thread_can_be_force_archived():
    thread = create_chat_thread(ChatThreadCreateRequest(user_id="user_a", title="Blocked active"))
    set_thread_active_job(thread.thread_id, "job_uuid", "job_public")

    archived = archive_chat_thread(thread.thread_id, user_id="user_a", force=True)

    assert archived is not None
    assert archived.status == "archived"
    assert archived.active_job_id is None
    assert archived.archived_at is not None


def test_user_message_reopens_completed_thread_but_keeps_final_output():
    thread = create_chat_thread(ChatThreadCreateRequest(user_id="user_a", title="Done"))
    set_thread_active_job(thread.thread_id, "job_uuid", "job_public")
    set_thread_final_output(thread.thread_id, "output_uuid", final_brief={"safe": "brief"})
    clear_thread_active_job(thread.thread_id, status="completed")

    append_chat_message(thread.thread_id, ChatMessageCreateRequest(role="user", content="again"), user_id="user_a")
    updated = get_chat_thread(thread.thread_id, user_id="user_a")

    assert updated.status == "draft"
    assert updated.has_final_output is True
    assert updated.final_brief == {"safe": "brief"}


def test_stale_memory_job_cannot_clear_newer_active_job():
    thread = create_chat_thread(ChatThreadCreateRequest(user_id="user_a", title="Stale"))
    set_thread_active_job(thread.thread_id, "job_uuid_b", "job_b")

    set_thread_final_output(
        thread.thread_id,
        "output_uuid_a",
        final_brief={"stale": True},
        expected_public_job_id="job_a",
    )
    clear_thread_active_job(thread.thread_id, status="completed", expected_public_job_id="job_a")

    current = get_chat_thread(thread.thread_id, user_id="user_a")
    assert current.active_job_id == "job_b"
    assert current.status == "generating"
    assert current.has_final_output is False


def test_message_pagination_total():
    thread = create_chat_thread(ChatThreadCreateRequest(user_id="user_a", title="Messages"))
    for index in range(5):
        append_chat_message(thread.thread_id, ChatMessageCreateRequest(role="user", content=f"m {index}"), user_id="user_a")

    messages, total = list_chat_messages(thread.thread_id, user_id="user_a", limit=2, offset=2)

    assert total == 5
    assert [message.sequence_no for message in messages] == [3, 4]


def test_chat_message_list_query_includes_generation_job_join(monkeypatch):
    from orchestrator.app.db.repositories import chat_messages as repo

    conn = FakeConn(rows=[{"id": "thread_uuid"}])

    @contextmanager
    def fake_tx(connection=None):
        yield conn

    monkeypatch.setattr(repo, "db_transaction", fake_tx)

    repo.list_chat_messages("thread_public", workspace_id="workspace_uuid", limit=5, offset=0)

    sql = conn._cursor._executed[1][0].lower()
    assert "from chat_messages cm" in sql
    assert "join generation_jobs" in sql


def test_list_chat_messages_skips_batch_lookup_when_page_has_no_generation_jobs(monkeypatch):
    from orchestrator.app.chat_threads import service as chat_service

    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")
    monkeypatch.setattr(chat_service, "_get_workspace_id_for_user", lambda user_id=None, account_type=None: "workspace_uuid")
    monkeypatch.setattr(
        chat_service.chat_message_repo,
        "list_chat_messages",
        lambda *args, **kwargs: [
            {"id": "m1", "role": "user", "content": "a", "payload": {}, "sequence_no": 1, "created_at": "2026-06-16T00:00:00+00:00"}
        ],
    )
    monkeypatch.setattr(chat_service.chat_message_repo, "count_chat_messages", lambda *args, **kwargs: 1)
    monkeypatch.setattr(
        chat_service.chat_message_repo,
        "get_public_job_ids_by_internal_ids",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("batch lookup should not run")),
    )

    messages, total = chat_service.list_chat_messages("thread_public", user_id="user_a")

    assert total == 1
    assert len(messages) == 1


def test_list_chat_messages_batches_generation_job_lookup_once(monkeypatch):
    from orchestrator.app.chat_threads import service as chat_service

    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")
    monkeypatch.setattr(chat_service, "_get_workspace_id_for_user", lambda user_id=None, account_type=None: "workspace_uuid")
    monkeypatch.setattr(
        chat_service.chat_message_repo,
        "list_chat_messages",
        lambda *args, **kwargs: [
            {"id": "m1", "role": "assistant", "content": "a", "payload": {}, "sequence_no": 1, "created_at": "2026-06-16T00:00:00+00:00", "generation_job_id": "job_uuid_1"},
            {"id": "m2", "role": "assistant", "content": "b", "payload": {}, "sequence_no": 2, "created_at": "2026-06-16T00:00:00+00:00", "generation_job_id": "job_uuid_2"},
        ],
    )
    monkeypatch.setattr(chat_service.chat_message_repo, "count_chat_messages", lambda *args, **kwargs: 2)
    calls = []

    def fake_batch(ids, *, workspace_id, connection=None):
        calls.append((list(ids), workspace_id))
        return {"job_uuid_1": "job_public_1", "job_uuid_2": "job_public_2"}

    monkeypatch.setattr(chat_service.chat_message_repo, "get_public_job_ids_by_internal_ids", fake_batch)

    messages, total = chat_service.list_chat_messages("thread_public", user_id="user_a", limit=50)

    assert total == 2
    assert [message.job_id for message in messages] == ["job_public_1", "job_public_2"]
    assert calls == [(["job_uuid_1", "job_uuid_2"], "workspace_uuid")]


def test_chat_thread_backend_files_do_not_have_duplicate_function_definitions():
    paths = [
        Path("orchestrator/app/db/repositories/chat_messages.py"),
        Path("orchestrator/app/db/repositories/chat_threads.py"),
        Path("orchestrator/app/chat_threads/service.py"),
    ]
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        seen: dict[str, int] = {}
        duplicates: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if node.name in seen:
                    duplicates.add(node.name)
                seen[node.name] = node.lineno
        assert duplicates == set(), f"{path} has duplicate defs: {sorted(duplicates)}"


def test_get_chat_thread_with_workspace_falls_back_to_owning_workspace(monkeypatch):
    from orchestrator.app.chat_threads import service as chat_service

    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")
    monkeypatch.setattr(chat_service, "_get_demo_workspace_id", lambda user_id=None: "workspace_demo")

    calls = []

    def fake_get_chat_thread_by_public_id(public_thread_id, workspace_id=None, connection=None, for_update=False):
        calls.append(workspace_id)
        if workspace_id == "workspace_demo":
            return None
        return {
            "id": "internal_thread_uuid",
            "public_thread_id": public_thread_id,
            "workspace_id": "workspace_actual",
            "title": "카페 신메뉴 광고",
            "status": "generating",
            "brand_kit_id": None,
            "project_id": None,
            "final_brief": {},
            "active_job_id": None,
            "active_public_job_id": None,
            "final_output_id": None,
            "last_message_at": "2026-06-06T00:00:00+00:00",
            "archived_at": None,
            "created_at": "2026-06-06T00:00:00+00:00",
            "updated_at": "2026-06-06T00:00:00+00:00",
        }

    monkeypatch.setattr(chat_service.chat_thread_repo, "get_chat_thread_by_public_id", fake_get_chat_thread_by_public_id)

    result = chat_service.get_chat_thread_with_workspace("thread_generated")

    thread, workspace_id = result
    assert thread.thread_id == "thread_generated"
    assert workspace_id == "workspace_actual"


def test_postgres_thread_list_uses_authenticated_user_workspace_even_with_demo_workspace(monkeypatch):
    from orchestrator.app.chat_threads import service as chat_service

    @contextmanager
    def fake_db_transaction(connection=None):
        yield object()

    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")
    monkeypatch.setenv("EASYADS_DEMO_WORKSPACE_ID", "workspace_demo")
    monkeypatch.setattr(chat_service, "db_transaction", fake_db_transaction)
    monkeypatch.setattr(
        chat_service.workspace_repo,
        "ensure_user_workspace",
        lambda user_id, connection=None: {"id": f"workspace_{user_id}"},
    )
    monkeypatch.setattr(
        chat_service.workspace_repo,
        "ensure_demo_workspace",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("authenticated users must not use demo workspace")),
    )

    captured = {}

    def fake_list_chat_threads(*, workspace_id, include_archived=False, limit=50, offset=0, connection=None):
        captured["workspace_id"] = workspace_id
        return []

    def fake_count_chat_threads(*, workspace_id, include_archived=False, connection=None):
        captured["count_workspace_id"] = workspace_id
        return 0

    monkeypatch.setattr(chat_service.chat_thread_repo, "list_chat_threads", fake_list_chat_threads)
    monkeypatch.setattr(chat_service.chat_thread_repo, "count_chat_threads", fake_count_chat_threads)

    threads, total = chat_service.list_chat_threads(user_id="user_a")

    assert threads == []
    assert total == 0
    assert captured == {"workspace_id": "workspace_user_a", "count_workspace_id": "workspace_user_a"}


def test_postgres_thread_list_can_skip_exact_total(monkeypatch):
    from orchestrator.app.chat_threads import service as chat_service

    @contextmanager
    def fake_db_transaction(connection=None):
        yield object()

    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")
    monkeypatch.setenv("EASYADS_DEMO_WORKSPACE_ID", "workspace_demo")
    monkeypatch.setattr(chat_service, "db_transaction", fake_db_transaction)
    monkeypatch.setattr(
        chat_service.workspace_repo,
        "ensure_user_workspace",
        lambda user_id, connection=None: {"id": f"workspace_{user_id}"},
    )
    count_calls = []

    def fake_list_chat_threads(*, workspace_id, include_archived=False, limit=50, offset=0, connection=None):
        return [
            {
                "id": "thread-internal-1",
                "public_thread_id": "thread_1",
                "workspace_id": workspace_id,
                "created_by": "user_a",
                "title": "A 1",
                "status": "draft",
                "brand_kit_id": None,
                "project_id": None,
                "final_brief": {},
                "active_public_job_id": None,
                "final_output_id": None,
                "last_message_at": "2026-06-07T00:00:00+00:00",
                "archived_at": None,
                "created_at": "2026-06-07T00:00:00+00:00",
                "updated_at": "2026-06-07T00:00:00+00:00",
            }
        ]

    def fake_count_chat_threads(*, workspace_id, include_archived=False, connection=None):
        count_calls.append(workspace_id)
        return 99

    monkeypatch.setattr(chat_service.chat_thread_repo, "list_chat_threads", fake_list_chat_threads)
    monkeypatch.setattr(chat_service.chat_thread_repo, "count_chat_threads", fake_count_chat_threads)

    threads, total = chat_service.list_chat_threads(user_id="user_a", limit=5, include_total=False)

    assert len(threads) == 1
    assert total == 1
    assert count_calls == []


# ===== from test_chat_threads_repository.py =====
"""chat_threads repository fake connection 테스트."""

import pytest

# ---------------------------------------------------------------------------
# fake DB 인프라
# ---------------------------------------------------------------------------


class FakeCursor:
    def __init__(self):
        self._rows = []
        self._executed = []

    def execute(self, sql, params=None):
        self._executed.append((sql, params))

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass


class FakeConn:
    def __init__(self, rows=None):
        self._cursor = FakeCursor()
        if rows:
            self._cursor._rows = rows

    def cursor(self):
        return self._cursor

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass


# ---------------------------------------------------------------------------
# repository 함수 monkeypatch 헬퍼
# ---------------------------------------------------------------------------

from orchestrator.app.db.repositories import chat_threads as repo__test_chat_threads_repository


def _patch_transaction(monkeypatch, conn):
    """db_transaction을 fake conn으로 교체."""
    from contextlib import contextmanager

    @contextmanager
    def _fake_tx(given_conn=None):
        yield conn

    monkeypatch.setattr("orchestrator.app.db.repositories.chat_threads.db_transaction", _fake_tx)


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


def test_create_returns_public_thread_id(monkeypatch):
    row = make_chat_thread_row()
    conn = FakeConn(rows=[row])
    _patch_transaction(monkeypatch, conn)

    result = repo__test_chat_threads_repository.create_chat_thread(
        workspace_id="ws-1", created_by="user-1", title="Test"
    )
    assert result["public_thread_id"] == "thread_abc"
    executed_sql = " ".join(sql.lower() for sql, _ in conn._cursor._executed)
    assert "insert into chat_threads" in executed_sql
    # Guard ran the per-workspace advisory lock before inserting.
    assert "pg_advisory_xact_lock" in executed_sql


def test_create_raises_when_thread_limit_reached(monkeypatch):
    from orchestrator.app.chat_threads.errors import ChatThreadLimitReachedError

    # count_chat_threads (via the guard) reads "total" from fetchone → at the
    # default limit of 3, creation must raise and never reach the insert.
    conn = FakeConn(rows=[{"total": 3}])
    _patch_transaction(monkeypatch, conn)

    with pytest.raises(ChatThreadLimitReachedError) as exc_info:
        repo__test_chat_threads_repository.create_chat_thread(workspace_id="ws-1", created_by="user-1", title="Test")

    assert exc_info.value.error_code == "thread_limit_reached"
    executed_sql = " ".join(sql.lower() for sql, _ in conn._cursor._executed)
    assert "insert into chat_threads" not in executed_sql


def test_create_respects_configurable_limit(monkeypatch):
    # With the limit raised to 5, a workspace at 4 threads can still create.
    monkeypatch.setattr(
        "orchestrator.app.db.repositories.chat_threads.db_settings.get_max_threads_per_workspace",
        lambda: 5,
    )
    row = make_chat_thread_row(public_thread_id="thread_ok", total=4)
    conn = FakeConn(rows=[row])
    _patch_transaction(monkeypatch, conn)

    result = repo__test_chat_threads_repository.create_chat_thread(workspace_id="ws-1", created_by="user-1")
    assert result["public_thread_id"] == "thread_ok"


# ---------------------------------------------------------------------------
# get_chat_thread_by_public_id
# ---------------------------------------------------------------------------


def test_get_by_public_id(monkeypatch):
    row = make_chat_thread_row(active_public_job_id=None)
    conn = FakeConn(rows=[row])
    _patch_transaction(monkeypatch, conn)

    result = repo__test_chat_threads_repository.get_chat_thread_by_public_id("thread_abc")
    assert result["public_thread_id"] == "thread_abc"
    sql, params = conn._cursor._executed[0]
    assert "left join generation_jobs" in sql.lower()
    assert params == ("thread_abc",)


def test_get_by_public_id_not_found(monkeypatch):
    conn = FakeConn(rows=[])
    _patch_transaction(monkeypatch, conn)
    result = repo__test_chat_threads_repository.get_chat_thread_by_public_id("nonexistent")
    assert result is None


# ---------------------------------------------------------------------------
# list_chat_threads
# ---------------------------------------------------------------------------


def test_list_excludes_archived_by_default(monkeypatch):
    conn = FakeConn(rows=[])
    _patch_transaction(monkeypatch, conn)
    repo__test_chat_threads_repository.list_chat_threads(workspace_id="ws-1", include_archived=False)
    sql, _ = conn._cursor._executed[0]
    assert "archived_at is null" in sql.lower()


def test_list_includes_archived_when_requested(monkeypatch):
    conn = FakeConn(rows=[])
    _patch_transaction(monkeypatch, conn)
    repo__test_chat_threads_repository.list_chat_threads(workspace_id="ws-1", include_archived=True)
    sql, _ = conn._cursor._executed[0]
    assert "archived_at is null" not in sql.lower()


def test_list_order_uses_last_message_at(monkeypatch):
    conn = FakeConn(rows=[])
    _patch_transaction(monkeypatch, conn)
    repo__test_chat_threads_repository.list_chat_threads(workspace_id="ws-1")
    sql, _ = conn._cursor._executed[0]
    assert "last_message_at desc" in sql.lower()


# ---------------------------------------------------------------------------
# update_chat_thread (allowlist)
# ---------------------------------------------------------------------------


def test_update_allowlist_only(monkeypatch):
    row = make_chat_thread_row(title="New", status="draft")
    conn = FakeConn(rows=[row])
    _patch_transaction(monkeypatch, conn)

    repo__test_chat_threads_repository.update_chat_thread("thread_abc", title="New")
    sql, _ = conn._cursor._executed[0]
    assert "update chat_threads" in sql.lower()
    assert "title" in sql.lower()
    # 금지 필드 미포함
    assert "status" not in sql.lower()
    assert "workspace_id" not in sql.lower()


def test_update_final_brief_uses_jsonb(monkeypatch):
    row = make_chat_thread_row(final_brief={"k": "v"})
    conn = FakeConn(rows=[row])
    _patch_transaction(monkeypatch, conn)

    repo__test_chat_threads_repository.update_chat_thread("thread_abc", final_brief={"k": "v"})
    sql, _ = conn._cursor._executed[0]
    assert "jsonb" in sql.lower()


# ---------------------------------------------------------------------------
# archive
# ---------------------------------------------------------------------------


def test_archive_sets_status_and_archived_at(monkeypatch):
    row = make_chat_thread_row(status="archived", archived_at="2026-01-02", active_job_id=None)
    conn = FakeConn(rows=[row])
    _patch_transaction(monkeypatch, conn)

    result = repo__test_chat_threads_repository.archive_chat_thread("thread_abc")
    assert result["status"] == "archived"
    sql, _ = conn._cursor._executed[0]
    assert "archived_at = now()" in sql.lower()
    assert "active_job_id = null" in sql.lower()


def test_archive_can_clear_active_job_when_forced(monkeypatch):
    row = make_chat_thread_row(status="archived", archived_at="2026-01-02", active_job_id=None)
    conn = FakeConn(rows=[row])
    _patch_transaction(monkeypatch, conn)

    result = repo__test_chat_threads_repository.archive_chat_thread("thread_abc", force=True)

    assert result["status"] == "archived"
    sql, params = conn._cursor._executed[0]
    assert "active_job_id = null" in sql.lower()
    assert "active_job_id is null" in sql.lower()
    assert True in params


# ---------------------------------------------------------------------------
# set/clear active_job_id
# ---------------------------------------------------------------------------


def test_set_active_job_id(monkeypatch):
    row = make_chat_thread_row(active_job_id="job-uuid", status="generating")
    conn = FakeConn(rows=[row])
    _patch_transaction(monkeypatch, conn)

    result = repo__test_chat_threads_repository.set_chat_thread_active_job("thread_abc", "job-uuid", status="generating")
    assert result["active_job_id"] == "job-uuid"
    sql, _ = conn._cursor._executed[0]
    assert "active_job_id" in sql.lower()


def test_clear_active_job_id(monkeypatch):
    row = make_chat_thread_row(active_job_id=None, status="completed")
    conn = FakeConn(rows=[row])
    _patch_transaction(monkeypatch, conn)

    result = repo__test_chat_threads_repository.clear_chat_thread_active_job("thread_abc", status="completed")
    assert result["active_job_id"] is None
    sql, _ = conn._cursor._executed[0]
    assert "active_job_id = null" in sql.lower()


# ---------------------------------------------------------------------------
# set final_output_id
# ---------------------------------------------------------------------------


def test_set_final_output_id(monkeypatch):
    row = make_chat_thread_row(final_output_id="out-uuid")
    conn = FakeConn(rows=[row])
    _patch_transaction(monkeypatch, conn)

    result = repo__test_chat_threads_repository.set_chat_thread_final_output("thread_abc", "out-uuid")
    assert result["final_output_id"] == "out-uuid"
    sql, _ = conn._cursor._executed[0]
    assert "final_output_id" in sql.lower()


def test_complete_generation_guards_workspace_and_expected_active_job(monkeypatch):
    row = make_chat_thread_row(active_job_id=None, status="completed")
    conn = FakeConn(rows=[row])
    _patch_transaction(monkeypatch, conn)

    repo__test_chat_threads_repository.complete_chat_thread_generation(
        public_thread_id="thread_abc",
        workspace_id="workspace_uuid",
        expected_active_job_id="job_uuid",
        final_output_id="output_uuid",
        final_brief={"safe": "brief"},
    )

    sql, params = conn._cursor._executed[0]
    normalized = sql.lower()
    assert "workspace_id = %s::uuid" in normalized
    assert "active_job_id = %s::uuid" in normalized
    assert params[-3:] == ("thread_abc", "workspace_uuid", "job_uuid")


def test_fail_generation_guards_workspace_and_expected_active_job(monkeypatch):
    row = make_chat_thread_row(active_job_id=None, status="failed")
    conn = FakeConn(rows=[row])
    _patch_transaction(monkeypatch, conn)

    repo__test_chat_threads_repository.fail_chat_thread_generation(
        public_thread_id="thread_abc",
        workspace_id="workspace_uuid",
        expected_active_job_id="job_uuid",
    )

    sql, params = conn._cursor._executed[0]
    normalized = sql.lower()
    assert "workspace_id = %s::uuid" in normalized
    assert "active_job_id = %s::uuid" in normalized
    assert params == ("thread_abc", "workspace_uuid", "job_uuid")
