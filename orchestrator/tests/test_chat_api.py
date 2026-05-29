from fastapi.testclient import TestClient

from orchestrator.app.main import app


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
    assert payload["brief"]["copy"]
    assert payload["brief"]["finalImagePath"]
