"""Consolidated api routers tests.

Merged from:
- orchestrator/tests/test_api_app_entrypoint.py
- orchestrator/tests/test_api_archive_router.py
- orchestrator/tests/test_api_assets_router.py
- orchestrator/tests/test_api_brand_kits_router.py
- orchestrator/tests/test_api_chat_threads.py
- orchestrator/tests/test_api_contract_brand_kits.py
- orchestrator/tests/test_api_contract_common.py
- orchestrator/tests/test_api_contract_generation_jobs.py
- orchestrator/tests/test_api_contract_misc.py
- orchestrator/tests/test_api_contract_references.py
- orchestrator/tests/test_api_generation_jobs_router.py
- orchestrator/tests/test_api_generation_jobs_workspace_scope.py
- orchestrator/tests/test_api_generation_outputs_router.py
- orchestrator/tests/test_api_references_router.py
- orchestrator/tests/test_api_usage_summary.py
"""

from __future__ import annotations



# ===== from test_api_app_entrypoint.py =====
from fastapi.testclient import TestClient

from orchestrator.app.api.app import create_app
from orchestrator.app.main import app as main_app
from orchestrator.tests.factories.api_payloads import generation_job_create_payload
from orchestrator.tests.helpers.api_clients import create_app_client


def test_create_app_registers_legacy_and_new_routes():
    schema = create_app().openapi()

    assert "/health" in schema["paths"]
    assert "/v1/marketing/chat/start" in schema["paths"]
    assert "/api/v1/references" in schema["paths"]
    assert "/api/v1/brand-kits/current" in schema["paths"]
    assert "/api/v1/generation-jobs" in schema["paths"]
    assert "/api/v1/archive/items" in schema["paths"]


def test_main_app_exposes_unified_routes():
    schema = main_app.openapi()

    assert "/health" in schema["paths"]
    assert "/v1/marketing/chat/start" in schema["paths"]
    assert "/api/v1/references" in schema["paths"]
    assert "/api/v1/brand-kits/current" in schema["paths"]
    assert "/api/v1/generation-jobs" in schema["paths"]
    assert "/api/v1/archive/items" in schema["paths"]


def test_health_route_still_works_from_main_app():
    response = TestClient(main_app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# ===== from test_api_archive_router.py =====
from fastapi.testclient import TestClient

from orchestrator.app.api.app import create_app
from orchestrator.app.api.routers import archive as archive_router
from orchestrator.app.api.schemas.archive import ArchiveItemResponse


def client() -> TestClient:
    return create_app_client()


def test_openapi_registers_archive_routes():
    schema = create_app().openapi()

    assert "/api/v1/archive/items" in schema["paths"]
    assert "/api/v1/archive/items/{archive_item_id}" in schema["paths"]


def test_archive_save_returns_503_when_persistence_is_disabled(monkeypatch):
    monkeypatch.delenv("EASYADS_DB_BACKEND", raising=False)

    response = client().post(
        "/api/v1/archive/items",
        json={"title": "봄을 닮은 한 잔", "public_job_id": "job_1", "image_url": "/api/generated-assets?path=x"},
    )

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["success"] is False
    assert detail["error_code"] == "archive_storage_unavailable"


def test_archive_save_list_update_and_delete_routes(monkeypatch):
    item = ArchiveItemResponse(
        ad_id="archive_1",
        job_id="job_1",
        title="봄을 닮은 한 잔",
        image_url="/api/generated-assets?path=data%2Foutputs%2Fjob_1%2Ffinal.png",
        status="saved",
        source="generated",
    )
    captured = {}

    def fake_create_archive_item(request):
        captured["request"] = request
        return item

    monkeypatch.setattr(archive_router, "create_archive_item", fake_create_archive_item)
    monkeypatch.setattr(archive_router, "list_archive_items", lambda workspace_id=None, user_id=None, limit=50, offset=0: ([item], 1))
    monkeypatch.setattr(archive_router, "update_archive_item", lambda archive_item_id, request: item.model_copy(update={"status": request.status}))
    monkeypatch.setattr(archive_router, "delete_archive_item", lambda archive_item_id, workspace_id=None, user_id=None: item)

    http = client()
    created = http.post(
        "/api/v1/archive/items",
        json={
            "title": "봄을 닮은 한 잔",
            "public_job_id": "job_1",
            "image_url": "/api/generated-assets?path=data%2Foutputs%2Fjob_1%2Ffinal.png",
            "ad_format": "1:1",
            "platform": "인스타 피드",
            "source": "generated",
            "metadata": {"tags": ["카페"]},
        },
    )
    listed = http.get("/api/v1/archive/items", params={"limit": 20})
    updated = http.patch("/api/v1/archive/items/archive_1", json={"status": "favorite"})
    deleted = http.delete("/api/v1/archive/items/archive_1")

    assert created.status_code == 201
    assert created.json()["item"]["ad_id"] == "archive_1"
    assert captured["request"].public_job_id == "job_1"
    assert listed.status_code == 200
    assert listed.json()["pagination"]["total"] == 1
    assert updated.status_code == 200
    assert updated.json()["item"]["status"] == "favorite"
    assert deleted.status_code == 200
    assert deleted.json()["item"]["job_id"] == "job_1"


def test_archive_list_update_and_delete_pass_user_id(monkeypatch):
    item = ArchiveItemResponse(
        ad_id="archive_1",
        job_id="job_1",
        title="봄을 닮은 한 잔",
        status="saved",
        source="generated",
    )
    captured = {}

    def fake_list_archive_items(workspace_id=None, user_id=None, limit=50, offset=0):
        captured["list_user_id"] = user_id
        return [item], 1

    def fake_update_archive_item(archive_item_id, request):
        captured["update_user_id"] = request.user_id
        return item.model_copy(update={"status": request.status})

    def fake_delete_archive_item(archive_item_id, workspace_id=None, user_id=None):
        captured["delete_user_id"] = user_id
        return item

    monkeypatch.setattr(archive_router, "list_archive_items", fake_list_archive_items)
    monkeypatch.setattr(archive_router, "update_archive_item", fake_update_archive_item)
    monkeypatch.setattr(archive_router, "delete_archive_item", fake_delete_archive_item)

    http = client()
    listed = http.get("/api/v1/archive/items", params={"user_id": "user_uuid_1"})
    updated = http.patch("/api/v1/archive/items/archive_1", json={"status": "favorite", "user_id": "user_uuid_1"})
    deleted = http.delete("/api/v1/archive/items/archive_1", params={"user_id": "user_uuid_1"})

    assert listed.status_code == 200
    assert updated.status_code == 200
    assert deleted.status_code == 200
    assert captured == {"list_user_id": "user_uuid_1", "update_user_id": "user_uuid_1", "delete_user_id": "user_uuid_1"}


# ===== from test_api_assets_router.py =====
import pytest
from fastapi.testclient import TestClient
from orchestrator.app.main import app

client__test_api_assets_router = TestClient(app)

VALID_ASSET_ID = "asset_" + "a" * 32

def test_presign_asset_api(monkeypatch):
    monkeypatch.setattr("orchestrator.app.storage.settings.require_r2_ready", lambda: None)
    monkeypatch.setattr("orchestrator.app.storage.settings.get_r2_bucket", lambda: "b")
    monkeypatch.setattr("orchestrator.app.assets.service._resolve_workspace_id", lambda x, **kw: "ws1")
    monkeypatch.setattr("orchestrator.app.db.settings.get_demo_user_id", lambda: "user1")
    monkeypatch.setattr("orchestrator.app.assets.service.db_transaction", lambda *a, **kw: __import__("contextlib").nullcontext())

    class MockRepo:
        def create_asset(self, *args, **kwargs):
            return {"id": "asset-uuid"}

    monkeypatch.setattr("orchestrator.app.assets.service.asset_repo", MockRepo())
    monkeypatch.setattr("orchestrator.app.assets.service.build_upload_object_key", lambda **k: "key")
    monkeypatch.setattr("orchestrator.app.assets.service.create_r2_client", lambda: None)
    monkeypatch.setattr("orchestrator.app.assets.service.create_presigned_put_url", lambda *a, **k: "http://url")

    resp = client__test_api_assets_router.post(
        "/api/v1/assets/uploads/presign",
        params={"user_id": "user1"},
        json={
            "kind": "source",
            "filename": "test.jpg",
            "mimeType": "image/jpeg",
            "sizeBytes": 1024,
            "workspaceId": "ws1"
        }
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["asset"]["status"] == "pending"
    assert data["upload"]["url"] == "http://url"

def test_complete_asset_api(monkeypatch):
    mock_row = {
        "id": "internal-uuid",
        "public_asset_id": VALID_ASSET_ID,
        "kind": "source",
        "metadata": {"upload": {"status": "pending"}},
        "bucket": "test-bucket",
        "object_key": "test-key"
    }

    class MockRepo:
        def get_asset_by_public_id(self, *args, **kwargs):
            return mock_row
        def update_asset(self, *args, **kwargs):
            mock_row["metadata"] = kwargs.get("metadata_merge")
            mock_row["public_url"] = kwargs.get("public_url")
            return mock_row

    monkeypatch.setattr("orchestrator.app.assets.service.asset_repo", MockRepo())
    monkeypatch.setattr("orchestrator.app.assets.service._resolve_workspace_id", lambda x, **kw: "ws1")
    monkeypatch.setattr("orchestrator.app.assets.service.db_transaction", lambda: __import__("contextlib").nullcontext())
    monkeypatch.setattr("orchestrator.app.assets.service.create_r2_client", lambda: None)

    from orchestrator.app.storage.errors import R2StorageUnavailableError
    def mock_head(*args, **kwargs):
        raise R2StorageUnavailableError("Not found")

    monkeypatch.setattr("orchestrator.app.assets.service.head_object", mock_head)

    resp = client__test_api_assets_router.post(f"/api/v1/assets/uploads/{VALID_ASSET_ID}/complete", params={"workspace_id": "ws1", "user_id": "user1"})
    assert resp.status_code == 503
    assert resp.json()["detail"]["error_code"] == "asset_storage_unavailable"

def test_get_asset_api(monkeypatch):
    mock_row = {
        "public_asset_id": VALID_ASSET_ID,
        "kind": "source",
        "metadata": {"upload": {"status": "ready"}},
        "storage_provider": "r2",
        "bucket": "b",
        "object_key": "k",
        "public_url": "http://image-url"
    }
    monkeypatch.setattr("orchestrator.app.assets.service._resolve_workspace_id", lambda x, **kw: "ws1")
    monkeypatch.setattr("orchestrator.app.assets.service.db_transaction", lambda *a, **kw: __import__("contextlib").nullcontext())

    class MockRepo:
        def get_asset_by_public_id(self, *args, **kwargs):
            return mock_row
    monkeypatch.setattr("orchestrator.app.assets.service.asset_repo", MockRepo())

    resp = client__test_api_assets_router.get(f"/api/v1/assets/{VALID_ASSET_ID}", params={"workspace_id": "ws1", "user_id": "user1"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["asset"]["status"] == "ready"
    assert data["asset"]["imageUrl"] == "http://image-url"


# ===== from test_api_brand_kits_router.py =====
import pytest
from fastapi.testclient import TestClient

from orchestrator.app.api.app import create_app
from orchestrator.app.brand_kits.service import reset_brand_kit_store_for_tests


@pytest.fixture(autouse=True)
def reset_store():
    reset_brand_kit_store_for_tests()
    yield
    reset_brand_kit_store_for_tests()


def client__test_api_brand_kits_router() -> TestClient:
    return create_app_client()


def test_openapi_registers_references_and_brand_kit_routes():
    schema = create_app().openapi()

    assert "/api/v1/references" in schema["paths"]
    assert "/api/v1/brand-kits/current" in schema["paths"]
    assert "/api/v1/brand-kits" in schema["paths"]
    assert "/api/v1/brand-kits/{brand_kit_id}" in schema["paths"]


def test_current_brand_kit_empty_state_then_created_current():
    http = client__test_api_brand_kits_router()

    empty = http.get("/api/v1/brand-kits/current")
    assert empty.status_code == 200
    empty_payload = empty.json()
    assert empty_payload["success"] is True
    assert empty_payload["has_brand_kit"] is False
    assert empty_payload["empty_state"]["kind"] == "no_brand_kit"

    created = http.post(
        "/api/v1/brand-kits",
        json={"store_name": "Moon Cafe", "business_type": "cafe", "brand_colors": ["#F6A5B8"]},
    )
    assert created.status_code == 200
    created_payload = created.json()
    assert created_payload["success"] is True
    assert created_payload["brand_kit"]["brand_kit_id"].startswith("bk_")

    current = http.get("/api/v1/brand-kits/current")
    assert current.status_code == 200
    assert current.json()["brand_kit"]["brand_kit_id"] == created_payload["brand_kit"]["brand_kit_id"]


def test_get_and_patch_brand_kit():
    http = client__test_api_brand_kits_router()
    created = http.post(
        "/api/v1/brand-kits",
        json={"user_id": "user_1", "store_name": "Moon Cafe", "business_type": "cafe"},
    ).json()
    brand_kit_id = created["brand_kit"]["brand_kit_id"]

    fetched = http.get(f"/api/v1/brand-kits/{brand_kit_id}")
    assert fetched.status_code == 200
    assert fetched.json()["brand_kit"]["brand_kit_id"] == brand_kit_id

    patched = http.patch(
        f"/api/v1/brand-kits/{brand_kit_id}",
        json={"store_name": "Sun Cafe", "brand_tones": ["premium"], "brand_colors": []},
    )
    assert patched.status_code == 200
    patched_payload = patched.json()["brand_kit"]
    assert patched_payload["store_name"] == "Sun Cafe"
    assert patched_payload["brand_tones"] == ["premium"]
    assert patched_payload["brand_colors"] == []


def test_invalid_brand_kit_id_returns_structured_404():
    response = client__test_api_brand_kits_router().get("/api/v1/brand-kits/bk_missing")

    assert response.status_code == 404
    detail = response.json()["detail"]
    assert detail["success"] is False
    assert detail["error_code"] == "brand_kit_not_found"


def test_invalid_update_returns_structured_400():
    http = client__test_api_brand_kits_router()
    brand_kit_id = http.post(
        "/api/v1/brand-kits",
        json={"store_name": "Moon Cafe", "business_type": "cafe"},
    ).json()["brand_kit"]["brand_kit_id"]

    response = http.patch(f"/api/v1/brand-kits/{brand_kit_id}", json={"store_name": ""})

    assert response.status_code == 400
    payload = response.json()
    assert payload["success"] is False
    assert payload["error_code"] == "invalid_brand_kit_request"


def test_brand_colors_validation_returns_400():
    response = client__test_api_brand_kits_router().post(
        "/api/v1/brand-kits",
        json={"store_name": "Moon Cafe", "business_type": "cafe", "brand_colors": ["F6A5B8"]},
    )

    assert response.status_code == 400
    assert response.json()["error_code"] == "invalid_brand_kit_request"


# ===== from test_api_chat_threads.py =====
import pytest
from fastapi.testclient import TestClient

from orchestrator.app.api.app import create_app
from orchestrator.app.chat_threads.service import reset_chat_thread_store_for_tests


@pytest.fixture(autouse=True)
def memory_backend(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "memory")
    reset_chat_thread_store_for_tests()
    yield
    reset_chat_thread_store_for_tests()


def test_chat_thread_api_create_append_list_flow():
    client = TestClient(create_app())

    created = client.post("/api/v1/chat-threads", json={"userId": "user_a", "title": "Campaign"}).json()
    thread_id = created["thread"]["thread_id"]

    msg = client.post(
        f"/api/v1/chat-threads/{thread_id}/messages?userId=user_a",
        json={"role": "user", "content": "hello", "payload": {"apiKey": "sk-secret", "safe": "visible"}},
    )
    listed = client.get(f"/api/v1/chat-threads/{thread_id}/messages?userId=user_a")

    assert msg.status_code == 201
    assert msg.json()["message"]["payload"] == {"safe": "visible"}
    assert listed.json()["total"] == 1


def test_chat_thread_api_owner_scope_returns_not_found():
    client = TestClient(create_app())

    created = client.post("/api/v1/chat-threads", json={"userId": "user_a", "title": "Campaign"}).json()
    response = client.get(f"/api/v1/chat-threads/{created['thread']['thread_id']}?userId=user_b")

    assert response.status_code == 404
    assert response.json()["detail"]["error_code"] == "chat_thread_not_found"


def test_generation_job_rejects_invalid_thread_id_prefix():
    client = TestClient(create_app())

    response = client.post("/api/v1/generation-jobs", json={"userInput": "Create ad", "threadId": "bad"})

    assert response.status_code == 400
    assert response.json()["error_code"] == "invalid_generation_job_request"


# ===== from test_api_contract_brand_kits.py =====
from pydantic import ValidationError

from orchestrator.app.api.schemas.brand_kits import (
    BrandKitCreateRequest,
    BrandKitGetCurrentResponse,
    BrandProduct,
)
from orchestrator.app.api.schemas.common import EmptyState


def test_brand_kit_create_request_validation_and_json_dump():
    request = BrandKitCreateRequest(
        store_name="Moon Cafe",
        business_type="cafe",
        brand_colors=["#F6A5B8"],
        representative_products=[BrandProduct(name="Strawberry cake", is_representative=True)],
    )

    dumped = request.model_dump(mode="json")

    assert dumped["store_name"] == "Moon Cafe"
    assert dumped["brand_colors"] == ["#F6A5B8"]


def test_brand_kit_create_request_rejects_empty_required_fields():
    try:
        BrandKitCreateRequest(store_name=" ", business_type="cafe")
    except ValidationError:
        pass
    else:
        raise AssertionError("empty store_name should fail validation")


def test_brand_kit_get_current_empty_state():
    response = BrandKitGetCurrentResponse(
        has_brand_kit=False,
        empty_state=EmptyState(kind="brand_kit_empty", title="No brand kit", message="Create a brand kit."),
    )

    dumped = response.model_dump(mode="json")

    assert dumped["success"] is True
    assert dumped["has_brand_kit"] is False
    assert dumped["empty_state"]["kind"] == "brand_kit_empty"


# ===== from test_api_contract_common.py =====
from pydantic import ValidationError

from orchestrator.app.api.schemas.common import ApiMeta, ErrorResponse, Pagination, RecoveryAction


def test_error_response_creation_and_json_dump():
    response = ErrorResponse(
        error_code="invalid_request",
        message="Invalid request",
        recovery_actions=[RecoveryAction(action="retry", label="Try again")],
        meta=ApiMeta(request_id="req_001"),
    )

    dumped = response.model_dump(mode="json")

    assert dumped["success"] is False
    assert dumped["error_code"] == "invalid_request"
    assert dumped["recovery_actions"][0]["action"] == "retry"
    assert dumped["meta"]["version"] == "v1"


def test_pagination_validation():
    pagination = Pagination(limit=20, offset=0, total=41, has_more=True)
    assert pagination.has_more is True

    try:
        Pagination(limit=0, offset=0, total=0, has_more=False)
    except ValidationError:
        pass
    else:
        raise AssertionError("limit=0 should fail validation")


# ===== from test_api_contract_generation_jobs.py =====
from pydantic import ValidationError

from orchestrator.app.api.schemas.generation_jobs import (
    GenerationJobAnswerRequest,
    GenerationJobCreateRequest,
    GenerationJobCreateResponse,
    GenerationJobResponse,
    GenerationProgress,
)


def test_generation_job_create_request_validation():
    request = GenerationJobCreateRequest(
        user_input="Create an Instagram ad for a strawberry cake launch.",
        selected_reference_template_id="seed_cafe_strawberry_feed_001",
    )

    assert request.run_mode == "queued_only"
    assert request.user_plan == "free"

    try:
        GenerationJobCreateRequest(user_input=" ")
    except ValidationError:
        pass
    else:
        raise AssertionError("blank user_input should fail validation")


def test_generation_job_answer_request_builds_option_resume_payload():
    request = GenerationJobAnswerRequest(
        field="business_type",
        value="cafe",
        custom_text=None,
    )

    payload = request.to_resume_payload(job_id="job_1", thread_id="thread_1")

    assert payload == {
        "job_id": "job_1",
        "thread_id": "thread_1",
        "field": "business_type",
        "value": "cafe",
    }


def test_generation_job_answer_request_supports_camel_case_custom_text():
    request = GenerationJobAnswerRequest.model_validate(
        {
            "field": "item_or_service",
            "value": "custom",
            "customText": "딸기라떼",
            "displayText": "딸기라떼",
        }
    )

    payload = request.to_resume_payload(job_id="job_1", thread_id="thread_1")

    assert payload["custom_text"] == "딸기라떼"
    assert payload["display_text"] == "딸기라떼"


def test_generation_job_answer_request_preserves_compliance_action():
    request = GenerationJobAnswerRequest.model_validate(
        {
            "action": "use_suggestion",
            "displayText": "안전한 문구로 수정",
        }
    )

    payload = request.to_resume_payload(job_id="job_1", thread_id="thread_1")

    assert payload["action"] == "use_suggestion"
    assert payload["display_text"] == "안전한 문구로 수정"


def test_generation_progress_percent_validation():
    progress = GenerationProgress(progress_percent=100, current_stage="completed")
    assert progress.progress_percent == 100

    try:
        GenerationProgress(progress_percent=101)
    except ValidationError:
        pass
    else:
        raise AssertionError("progress_percent > 100 should fail validation")


def test_generation_job_create_response_json_dump():
    job = GenerationJobResponse(
        job_id="job_001",
        status="queued",
        progress=GenerationProgress(),
        created_at="2026-05-29T00:00:00Z",
        updated_at="2026-05-29T00:00:00Z",
    )
    response = GenerationJobCreateResponse(job=job)

    dumped = response.model_dump(mode="json")

    assert dumped["success"] is True
    assert dumped["job"]["job_id"] == "job_001"


# ===== from test_api_contract_misc.py =====
from orchestrator.app.api.schemas.archive import ArchiveItemResponse, ArchiveListResponse
from orchestrator.app.api.schemas.common import Pagination
from orchestrator.app.api.schemas.settings import UserAppSettingsResponse
from orchestrator.app.api.schemas.usage import UsageEventResponse, UsageSummaryResponse


def test_archive_list_response_creation():
    response = ArchiveListResponse(
        items=[ArchiveItemResponse(ad_id="ad_001", title="Spring menu ad")],
        pagination=Pagination(limit=20, offset=0, total=1, has_more=False),
    )

    dumped = response.model_dump(mode="json")

    assert dumped["success"] is True
    assert dumped["items"][0]["status"] == "saved"


def test_usage_summary_response_creation():
    response = UsageSummaryResponse(
        period="2026-05",
        plan="free",
        monthly_limit=10,
        used=2,
        remaining=8,
        usage_rate=0.2,
        events=[UsageEventResponse(event_id="evt_001", event_type="generation_created")],
    )

    dumped = response.model_dump(mode="json")

    assert dumped["success"] is True
    assert dumped["events"][0]["amount"] == 1


def test_user_app_settings_response_creation():
    response = UserAppSettingsResponse()

    dumped = response.model_dump(mode="json")

    assert dumped["success"] is True
    assert dumped["default_output_format"] == "png"
    assert dumped["notification_settings"]["job_completed"] is True


# ===== from test_api_contract_references.py =====
from orchestrator.app.api.schemas.common import Pagination
from orchestrator.app.api.schemas.references import (
    ReferenceTemplateCardResponse,
    ReferenceTemplateDetailResponse,
    ReferenceTemplateListResponse,
)
from orchestrator.app.reference_catalog.service import load_reference_templates


def test_reference_template_list_response_creation():
    template = load_reference_templates()[0]
    card = ReferenceTemplateCardResponse.from_template(template)
    response = ReferenceTemplateListResponse(
        items=[card],
        pagination=Pagination(limit=20, offset=0, total=1, has_more=False),
    )

    dumped = response.model_dump(mode="json")

    assert dumped["success"] is True
    assert dumped["items"][0]["template_id"] == template.template_id
    assert dumped["items"][0]["thumbnail_url"] is None


def test_reference_template_detail_response_creation():
    templates = load_reference_templates()
    card = ReferenceTemplateCardResponse.from_template(templates[0])
    similar = ReferenceTemplateCardResponse.from_template(templates[1])
    response = ReferenceTemplateDetailResponse(
        template=card,
        detail={"source": "seed"},
        similar_templates=[similar],
    )

    dumped = response.model_dump(mode="json")

    assert dumped["template"]["template_id"] == templates[0].template_id
    assert dumped["similar_templates"][0]["template_id"] == templates[1].template_id


# ===== from test_api_generation_jobs_router.py =====
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from orchestrator.app.api.app import create_app
from orchestrator.app.api.schemas.generation_jobs import GenerationJobResponse, GenerationProgress
from orchestrator.app.chat_threads.errors import (
    ChatThreadArchivedError,
    ChatThreadHasActiveJobError,
    ChatThreadNotFoundError,
    ChatThreadServiceError,
)
from orchestrator.app.generation_jobs.service import reset_generation_job_store_for_tests
from orchestrator.app.chat_threads.service import reset_chat_thread_store_for_tests


@pytest.fixture(autouse=True)
def reset_store__test_api_generation_jobs_router():
    reset_generation_job_store_for_tests()
    reset_chat_thread_store_for_tests()
    yield
    reset_generation_job_store_for_tests()
    reset_chat_thread_store_for_tests()


@pytest.fixture()
def client__test_api_generation_jobs_router() -> TestClient:
    return create_app_client()


def test_run_graph_job_background_records_start_and_delegates(monkeypatch):
    from orchestrator.app.api.routers import generation_jobs as router

    events = []
    calls = []
    request = GenerationJobCreateRequest(userInput="Create an ad", runMode="graph_job")
    monkeypatch.setattr(router, "record_generation_job_lifecycle_event", lambda *args, **kwargs: events.append((args, kwargs)))
    monkeypatch.setattr(router, "execute_generation_job_graph", lambda *args, **kwargs: calls.append((args, kwargs)))

    router._run_graph_job_background(
        "job_123",
        request,
        "workspace_123",
        "user_123",
    )

    assert [event[0][1] for event in events] == ["background_started", "background_delegated"]
    assert events[0][0][0] == "job_123"
    assert events[0][1]["payload"] == {"task": "graph_create"}
    assert calls == [(("job_123", request), {})]


def test_resume_graph_job_background_records_start_and_delegates(monkeypatch):
    from orchestrator.app.api.routers import generation_jobs as router

    events = []
    calls = []
    request = GenerationJobAnswerRequest(userCustomHeadline="직접 입력")
    monkeypatch.setattr(router, "record_generation_job_lifecycle_event", lambda *args, **kwargs: events.append((args, kwargs)))
    monkeypatch.setattr(router, "resume_generation_job_graph", lambda *args, **kwargs: calls.append((args, kwargs)))

    router._resume_graph_job_background(
        "job_123",
        request,
        allow_running=True,
        workspace_id="workspace_123",
        user_id="user_123",
    )

    assert [event[0][1] for event in events] == ["background_started", "background_delegated"]
    assert events[0][1]["payload"] == {"task": "graph_resume"}
    assert calls == [
        (
            ("job_123", request),
            {"allow_running": True, "workspace_id": "workspace_123", "user_id": "user_123"},
        )
    ]


def test_run_graph_job_background_marks_failed_on_exception(monkeypatch):
    from orchestrator.app.api.routers import generation_jobs as router

    events = []
    failures = []
    request = GenerationJobCreateRequest(userInput="Create an ad", runMode="graph_job")
    monkeypatch.setattr(router, "record_generation_job_lifecycle_event", lambda *args, **kwargs: events.append((args, kwargs)))
    monkeypatch.setattr(router, "mark_generation_job_failed", lambda *args, **kwargs: failures.append((args, kwargs)))

    def raise_error(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(router, "execute_generation_job_graph", raise_error)

    with pytest.raises(RuntimeError):
        router._run_graph_job_background("job_123", request, "workspace_123", "user_123")

    assert [event[0][1] for event in events] == ["background_started", "background_failed"]
    assert failures == [
        (
            ("job_123", {"error_code": "generation_job_background_task_failed", "message": "Background graph create task failed: boom"}),
            {"workspace_id": "workspace_123", "user_id": "user_123"},
        )
    ]


def test_create_graph_job_route_records_background_enqueue(monkeypatch):
    from orchestrator.app.api.routers import generation_jobs as router

    events = []
    tasks = []
    job = GenerationJobResponse(
        job_id="job_123",
        thread_id="thread_123",
        user_id="user_123",
        status="queued",
        progress=GenerationProgress(progress_percent=0, current_stage="queued", stage_order=[]),
        created_at="2026-06-13T00:00:00+00:00",
        updated_at="2026-06-13T00:00:00+00:00",
        metadata={},
    )

    class FakeBackgroundTasks:
        def add_task(self, func, *args, **kwargs):
            tasks.append((func, args, kwargs))

    monkeypatch.setattr(router, "create_generation_job", lambda request: job)
    monkeypatch.setattr(router, "should_route_generation_job_to_modal", lambda request: False)
    monkeypatch.setattr(router, "record_generation_job_lifecycle_event", lambda *args, **kwargs: events.append((args, kwargs)))

    request = GenerationJobCreateRequest(
        userInput="Create an ad",
        runMode="graph_job",
        workspaceId="workspace_123",
        userId="user_123",
        accountType="user",
    )

    response = router.create_generation_job_route(
        request,
        FakeBackgroundTasks(),
        router.RequestPrincipal(user_id="user_123", workspace_id="workspace_123", account_type="user"),
    )

    assert response.job.job_id == "job_123"
    assert events[0][0][:2] == ("job_123", "background_enqueued")
    assert events[0][1]["payload"] == {"task": "graph_create", "source": "create_route"}
    assert tasks[0][0] is router._run_graph_job_background


def test_answer_graph_job_route_records_background_enqueue(monkeypatch):
    from orchestrator.app.api.routers import generation_jobs as router

    events = []
    tasks = []
    waiting_job = GenerationJobResponse(
        job_id="job_123",
        thread_id="thread_123",
        user_id="user_123",
        status="waiting_user_input",
        progress=GenerationProgress(progress_percent=50, current_stage="waiting_user_input", stage_order=[]),
        created_at="2026-06-13T00:00:00+00:00",
        updated_at="2026-06-13T00:00:00+00:00",
        metadata={},
    )
    running_job = waiting_job.model_copy(
        update={
            "status": "running",
            "progress": GenerationProgress(progress_percent=50, current_stage="planning", stage_order=[]),
        }
    )

    class FakeBackgroundTasks:
        def add_task(self, func, *args, **kwargs):
            tasks.append((func, args, kwargs))

    monkeypatch.setattr(router, "get_generation_job_scoped", lambda *args, **kwargs: waiting_job)
    monkeypatch.setattr(router, "mark_generation_job_running", lambda *args, **kwargs: running_job)
    monkeypatch.setattr(router, "record_generation_job_lifecycle_event", lambda *args, **kwargs: events.append((args, kwargs)))

    request = GenerationJobAnswerRequest(userCustomHeadline="직접 입력", userCustomSubcopy="설명")

    response = router.answer_generation_job_route(
        "job_123",
        request,
        FakeBackgroundTasks(),
        "workspace_123",
        router.RequestPrincipal(user_id="user_123", workspace_id="workspace_123", account_type="user"),
    )

    assert response.job.job_id == "job_123"
    assert events[0][0][:2] == ("job_123", "background_enqueued")
    assert events[0][1]["payload"] == {"task": "graph_resume", "source": "answer_route"}
    assert tasks[0][0] is router._resume_graph_job_background


def test_openapi_registers_generation_jobs_and_existing_routes():
    schema = create_app().openapi()

    assert "/api/v1/references" in schema["paths"]
    assert "/api/v1/brand-kits" in schema["paths"]
    assert "/api/v1/generation-jobs" in schema["paths"]
    assert "/api/v1/generation-jobs/{job_id}" in schema["paths"]
    assert "/api/v1/generation-jobs/{job_id}/answer" in schema["paths"]


def test_create_generation_job_and_get_job(client__test_api_generation_jobs_router):
    created = client__test_api_generation_jobs_router.post(
        "/api/v1/generation-jobs",
        json=generation_job_create_payload(),
    )

    assert created.status_code == 201
    job = created.json()["job"]
    assert job["job_id"].startswith("job_")
    assert job["thread_id"].startswith("thread_")
    assert job["status"] == "queued"
    assert job["progress"]["progress_percent"] == 0
    assert job["metadata"]["requested_run_mode"] == "queued_only"
    assert job["metadata"]["effective_run_mode"] == "queued_only"
    assert job["output_path"] is None

    fetched = client__test_api_generation_jobs_router.get(f"/api/v1/generation-jobs/{job['job_id']}?workspace_id=mem_workspace")
    assert fetched.status_code == 200
    assert fetched.json()["job"]["job_id"] == job["job_id"]


def test_get_generation_job_marks_stale_running_planning_job_failed(client__test_api_generation_jobs_router, monkeypatch):
    stale_job = GenerationJobResponse(
        job_id="job_stale_1",
        thread_id="thread_stale_1",
        user_id="user_1",
        status="running",
        progress=GenerationProgress(progress_percent=50, current_stage="planning", stage_order=[]),
        created_at=(datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat(),
        updated_at=(datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat(),
        metadata={"execution_mode": "graph_execution"},
    )
    failed_job = stale_job.model_copy(
        update={
            "status": "failed",
            "progress": GenerationProgress(progress_percent=50, current_stage="failed", stage_order=[]),
            "metadata": {"execution_mode": "stale_running_recovered"},
        }
    )
    calls = []

    monkeypatch.setattr("orchestrator.app.api.routers.generation_jobs.get_generation_job_scoped", lambda job_id, **kwargs: stale_job)

    def fake_maybe_mark_stale_generation_job_failed(job, **kwargs):
        calls.append(job.job_id)
        return failed_job

    monkeypatch.setattr(
        "orchestrator.app.api.routers.generation_jobs.maybe_mark_stale_generation_job_failed",
        fake_maybe_mark_stale_generation_job_failed,
    )

    response = client__test_api_generation_jobs_router.get("/api/v1/generation-jobs/job_stale_1?workspace_id=mem_workspace")

    assert response.status_code == 200
    assert response.json()["job"]["status"] == "failed"
    assert response.json()["job"]["progress"]["current_stage"] == "failed"
    assert calls == ["job_stale_1"]


def test_create_generation_job_mock_immediate_completes(client__test_api_generation_jobs_router):
    response = client__test_api_generation_jobs_router.post(
        "/api/v1/generation-jobs",
        json={"user_input": "Create an ad", "run_mode": "mock_immediate"},
    )

    assert response.status_code == 201
    job = response.json()["job"]
    assert job["status"] == "done"
    assert job["progress"]["progress_percent"] == 100
    assert job["progress"]["current_stage"] == "completed"
    assert job["output_path"].endswith("/final_0.png")
    assert job["result_payload"]["schema_version"] == "result_artifact_v1"
    assert job["result_payload"]["final_image_path"] == job["output_path"]
    assert job["result_payload"]["download_url"] is None
    assert job["result_payload"]["final_image_url"] is None
    assert job["result_payload"]["prompt_summary"]
    assert job["result_payload"]["validation_summary"]["overall_pass"] is True
    assert job["metadata"]["effective_run_mode"] == "mock_immediate"
    assert job["metadata"]["execution_mode"] == "deterministic_mock"


def test_invalid_job_reference_and_request_errors(client__test_api_generation_jobs_router):
    missing_job = client__test_api_generation_jobs_router.get("/api/v1/generation-jobs/job_missing?workspace_id=mem_workspace")
    assert missing_job.status_code == 404
    assert missing_job.json()["detail"]["error_code"] == "generation_job_not_found"

    missing_template = client__test_api_generation_jobs_router.post(
        "/api/v1/generation-jobs",
        json={"user_input": "Create an ad", "selected_reference_template_id": "missing_template"},
    )
    assert missing_template.status_code == 404
    assert missing_template.json()["detail"]["error_code"] == "reference_template_not_found"

    invalid = client__test_api_generation_jobs_router.post("/api/v1/generation-jobs", json={"user_input": " "})
    assert invalid.status_code == 400
    assert invalid.json()["error_code"] == "invalid_generation_job_request"

    legacy_run_mode = client__test_api_generation_jobs_router.post(
        "/api/v1/generation-jobs",
        json={"user_input": "Create an ad", "run_mode": "graph_immediate"},
    )
    assert legacy_run_mode.status_code == 400
    assert legacy_run_mode.json()["error_code"] == "invalid_generation_job_request"


def test_graph_job_pending_metadata(client__test_api_generation_jobs_router):
    response = client__test_api_generation_jobs_router.post(
        "/api/v1/generation-jobs",
        json={
            "user_input": "카페 신메뉴 광고 만들어줘",
            "run_mode": "graph_job",
        },
    )

    assert response.status_code == 201
    body = response.json()
    job = body["job"]

    assert job["status"] in ("queued", "waiting_user_input")
    assert job["output_path"] is None
    assert job["result_payload"] is None
    assert job["metadata"]["requested_run_mode"] == "graph_job"
    assert job["metadata"]["effective_run_mode"] == "graph_job"
    assert job["metadata"]["execution_mode"] in ("pending_graph_execution", "graph_job")


def test_graph_job_routes_to_graph_executor_with_engine_metadata(client__test_api_generation_jobs_router, monkeypatch):
    captured = {}

    def fake_execute_generation_job_graph(job_id, request):
        from orchestrator.app.generation_jobs.service import get_generation_job

        captured["job_id"] = job_id
        captured["run_mode"] = request.run_mode
        captured["metadata"] = request.metadata
        job = get_generation_job(job_id)
        assert job is not None
        return job

    monkeypatch.setattr(
        "orchestrator.app.api.routers.generation_jobs.execute_generation_job_graph",
        fake_execute_generation_job_graph,
    )

    response = client__test_api_generation_jobs_router.post(
        "/api/v1/generation-jobs",
        json={
            "user_input": "카페 신메뉴 광고 만들어줘",
            "run_mode": "graph_job",
            "metadata": {
                "selected_engine": "flux2_klein_4b",
                "requested_engine": "flux2_klein_4b",
                "t2i_engine": "flux2_klein_4b",
            },
        },
    )

    assert response.status_code == 201
    assert captured["run_mode"] == "graph_job"
    assert captured["metadata"]["selected_engine"] == "flux2_klein_4b"
    assert captured["metadata"]["requested_engine"] == "flux2_klein_4b"
    assert captured["metadata"]["t2i_engine"] == "flux2_klein_4b"


def test_generation_job_answer_route_resumes_waiting_job(client__test_api_generation_jobs_router, monkeypatch):
    captured = {}

    def fake_resume_generation_job_graph(job_id, answer, *, allow_running=False, **kwargs):
        from orchestrator.app.generation_jobs.service import get_generation_job, update_generation_job

        captured["job_id"] = job_id
        captured["allow_running"] = allow_running
        captured["payload"] = answer.to_resume_payload(job_id=job_id, thread_id="thread_1")
        updated = update_generation_job(
            job_id,
            status="done",
            metadata={"execution_mode": "graph_execution"},
        )
        return updated or get_generation_job(job_id)

    monkeypatch.setattr(
        "orchestrator.app.api.routers.generation_jobs.resume_generation_job_graph",
        fake_resume_generation_job_graph,
    )

    create_response = client__test_api_generation_jobs_router.post(
        "/api/v1/generation-jobs",
        json={"user_input": "광고 만들어줘", "run_mode": "queued_only"},
    )
    job = create_response.json()["job"]
    from orchestrator.app.generation_jobs.service import update_generation_job
    update_generation_job(job["job_id"], status="waiting_user_input")

    answer_response = client__test_api_generation_jobs_router.post(
        f"/api/v1/generation-jobs/{job['job_id']}/answer?workspace_id=mem_workspace",
        json={"field": "business_type", "value": "cafe"},
    )

    assert answer_response.status_code == 200
    assert answer_response.json()["job"]["status"] == "running"
    assert captured["job_id"] == job["job_id"]
    assert captured["allow_running"] is True
    assert captured["payload"]["field"] == "business_type"
    assert captured["payload"]["value"] == "cafe"


def test_actual_lanes_default_disabled_return_failed_job(client__test_api_generation_jobs_router, monkeypatch):
    monkeypatch.setenv("EASYADS_ENABLE_EXTERNAL_T2I", "false")
    monkeypatch.setenv("EASYADS_ENABLE_GPT_IMAGE_1", "false")
    monkeypatch.setenv("EASYADS_ENABLE_GPT_IMAGE_2", "false")
    monkeypatch.setenv("EASYADS_ENABLE_SD35_LOCAL", "false")
    monkeypatch.setenv("EASYADS_ENABLE_FLUX_LOCAL", "false")

    gpt = client__test_api_generation_jobs_router.post("/api/v1/generation-jobs", json={"user_input": "Create an ad", "run_mode": "gpt_image_1_smoke"})
    sd35 = client__test_api_generation_jobs_router.post("/api/v1/generation-jobs", json={"user_input": "Create an ad", "run_mode": "sd35_local_smoke"})
    flux = client__test_api_generation_jobs_router.post("/api/v1/generation-jobs", json={"user_input": "Create an ad", "run_mode": "flux_local_smoke"})

    assert gpt.status_code == 201
    assert gpt.json()["job"]["status"] == "failed"
    assert gpt.json()["job"]["error"]["error_code"] == "t2i_engine_not_enabled"
    assert sd35.status_code == 201
    assert sd35.json()["job"]["status"] == "failed"
    assert sd35.json()["job"]["error"]["error_code"] == "t2i_engine_not_enabled"
    assert flux.status_code == 201
    assert flux.json()["job"]["status"] == "failed"
    assert flux.json()["job"]["error"]["error_code"] == "t2i_engine_not_enabled"
    assert flux.json()["job"]["metadata"]["t2i_engine"] == "flux2_klein_4b"


def test_create_generation_job_accepts_camel_case_reference_alias(client__test_api_generation_jobs_router):
    response = client__test_api_generation_jobs_router.post(
        "/api/v1/generation-jobs",
        json={
            "userInput": "Create a cafe launch ad",
            "selectedReferenceTemplateId": "seed_cafe_strawberry_feed_001",
            "runMode": "queued_only",
        },
    )

    assert response.status_code == 201
    job = response.json()["job"]
    assert job["selected_reference_template_id"] == "seed_cafe_strawberry_feed_001"
    assert job["metadata"]["selected_reference_template_id"] == "seed_cafe_strawberry_feed_001"


def test_create_generation_job_accepts_snake_case_reference_id(client__test_api_generation_jobs_router):
    response = client__test_api_generation_jobs_router.post(
        "/api/v1/generation-jobs",
        json={
            "user_input": "Create a cafe launch ad",
            "selected_reference_template_id": "seed_cafe_strawberry_feed_001",
            "run_mode": "queued_only",
        },
    )

    assert response.status_code == 201
    job = response.json()["job"]
    assert job["selected_reference_template_id"] == "seed_cafe_strawberry_feed_001"


@pytest.mark.parametrize(
    ("exc", "status_code"),
    [
        (ChatThreadNotFoundError(), 404),
        (ChatThreadArchivedError(), 409),
        (ChatThreadHasActiveJobError(), 409),
        (ChatThreadServiceError("invalid_chat_thread_request", "Invalid thread."), 400),
    ],
)
def test_generation_job_chat_thread_errors_are_mapped(client__test_api_generation_jobs_router, monkeypatch, exc, status_code):
    from orchestrator.app.api.routers import generation_jobs as router

    monkeypatch.setattr(router, "create_generation_job", lambda request: (_ for _ in ()).throw(exc))

    response = client__test_api_generation_jobs_router.post(
        "/api/v1/generation-jobs",
        json={"user_input": "Create an ad", "thread_id": "thread_existing"},
    )

    assert response.status_code == status_code
    assert response.json()["detail"]["error_code"] == exc.error_code


def test_generation_job_actual_payload_preserves_quality_batch_metadata(client__test_api_generation_jobs_router, monkeypatch):
    monkeypatch.setenv("EASYADS_ENABLE_EXTERNAL_T2I", "false")
    monkeypatch.setenv("EASYADS_ENABLE_GPT_IMAGE_2", "false")
    monkeypatch.setenv("EASYADS_QUALITY_BATCH_CONFIRM", "false")
    monkeypatch.setenv("OPENAI_API_KEY", "")

    response = client__test_api_generation_jobs_router.post(
        "/api/v1/generation-jobs",
        json={
            "user_input": "Create a quality batch ad background",
            "run_mode": "gpt_image_2_actual",
            "selected_reference_template_id": "seed_cafe_strawberry_feed_001",
            "ad_format": "instagram_feed",
            "metadata": {
                "quality_batch_id": "gpt_image2_quality_batch_v1",
                "case_id": "cafe_dessert_001",
            },
        },
    )

    assert response.status_code == 201
    job = response.json()["job"]
    assert job["selected_reference_template_id"] == "seed_cafe_strawberry_feed_001"
    assert job["metadata"]["quality_batch_id"] == "gpt_image2_quality_batch_v1"
    assert job["metadata"]["case_id"] == "cafe_dessert_001"
    assert job["status"] == "failed"
    assert job["error"]["error_code"] == "t2i_engine_not_enabled"

    assert response.status_code == 201
    job = response.json()["job"]
    assert job["selected_reference_template_id"] == "seed_cafe_strawberry_feed_001"
    assert job["metadata"]["quality_batch_id"] == "gpt_image2_quality_batch_v1"
    assert job["metadata"]["case_id"] == "cafe_dessert_001"
    assert job["status"] == "failed"
    assert job["error"]["error_code"] == "t2i_engine_not_enabled"


# ===== from test_api_generation_jobs_workspace_scope.py =====
from fastapi.testclient import TestClient

from orchestrator.app.api.app import create_app
from orchestrator.app.api.schemas.generation_jobs import GenerationJobResponse, GenerationProgress
from orchestrator.app.generation_jobs.service import reset_generation_job_store_for_tests


WORKSPACE_A = "11111111-1111-1111-1111-111111111111"
WORKSPACE_B = "22222222-2222-2222-2222-222222222222"


def test_generation_job_get_route_rejects_missing_scope(monkeypatch):
    response = TestClient(create_app()).get("/api/v1/generation-jobs/job_scoped")

    assert response.status_code == 400
    assert response.json()["detail"]["error_code"] == "workspace_required"


def test_generation_job_get_route_does_not_trust_query_user_id(monkeypatch):
    captured = {}

    def fake_get_generation_job(job_id, *, workspace_id=None, user_id=None):
        captured.update({"workspace_id": workspace_id, "user_id": user_id})
        return None

    monkeypatch.setattr("orchestrator.app.api.routers.generation_jobs.get_generation_job_scoped", fake_get_generation_job)

    response = TestClient(create_app()).get(
        f"/api/v1/generation-jobs/job_scoped?workspace_id={WORKSPACE_A}&user_id=user_a"
    )

    assert response.status_code == 404
    assert captured == {"workspace_id": WORKSPACE_A, "user_id": None}


def test_generation_job_get_route_recovers_scope_from_existing_job_without_header(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")
    monkeypatch.setenv("EASYADS_ALLOW_DEMO_WORKSPACE_FALLBACK", "false")
    captured = {}
    scoped_resolution = {}
    stale_scope = {}
    modal_scope = {}
    resolved_workspace = "33333333-3333-3333-3333-333333333333"
    job = GenerationJobResponse(
        job_id="job_polling",
        thread_id="thread_polling",
        user_id="user_a",
        status="waiting_user_input",
        progress=GenerationProgress(progress_percent=50, current_stage="waiting_user_input", stage_order=[]),
        created_at="2026-06-09T00:00:00+00:00",
        updated_at="2026-06-09T00:00:00+00:00",
        metadata={},
    )

    def fake_get_generation_job(job_id, *, workspace_id=None, user_id=None):
        captured.update({"job_id": job_id, "workspace_id": workspace_id, "user_id": user_id})
        return job

    def fake_mark_stale(current_job, **kwargs):
        stale_scope.update(kwargs)
        return current_job

    def fake_poll_modal(current_job, **kwargs):
        modal_scope.update(kwargs)
        return current_job

    def fake_resolve_scoped_workspace_id(workspace_id, user_id, account_type=None):
        scoped_resolution.update({"workspace_id": workspace_id, "user_id": user_id, "account_type": account_type})
        return resolved_workspace

    monkeypatch.setattr(
        "orchestrator.app.api.routers.generation_jobs.resolve_generation_job_scope_from_existing_job",
        lambda job_id: (WORKSPACE_A, "user_a"),
    )
    monkeypatch.setattr(
        "orchestrator.app.api.routers.generation_jobs.get_generation_job_internal_with_scope",
        lambda job_id: (None, None, None),
        raising=False,
    )
    monkeypatch.setattr("orchestrator.app.api.routers.generation_jobs.resolve_scoped_workspace_id", fake_resolve_scoped_workspace_id)
    monkeypatch.setattr("orchestrator.app.api.routers.generation_jobs.get_generation_job_scoped", fake_get_generation_job)
    monkeypatch.setattr("orchestrator.app.api.routers.generation_jobs.maybe_mark_stale_generation_job_failed", fake_mark_stale)
    monkeypatch.setattr("orchestrator.app.api.routers.generation_jobs.maybe_poll_generation_job_from_modal", fake_poll_modal)

    response = TestClient(create_app()).get("/api/v1/generation-jobs/job_polling")

    assert response.status_code == 200
    assert scoped_resolution == {"workspace_id": WORKSPACE_A, "user_id": "user_a", "account_type": None}
    assert captured == {"job_id": "job_polling", "workspace_id": resolved_workspace, "user_id": "user_a"}
    assert stale_scope == {"workspace_id": resolved_workspace, "user_id": "user_a"}
    assert modal_scope == {"workspace_id": resolved_workspace, "user_id": "user_a"}


def test_generation_job_get_route_reuses_existing_job_scope_without_extra_lookup(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")
    monkeypatch.setenv("EASYADS_ALLOW_DEMO_WORKSPACE_FALLBACK", "false")
    stale_scope = {}
    modal_scope = {}
    calls = {"internal_with_scope": 0, "scoped": 0}
    job = GenerationJobResponse(
        job_id="job_polling",
        thread_id="thread_polling",
        user_id="user_a",
        status="running",
        progress=GenerationProgress(progress_percent=50, current_stage="brief_interpretation", stage_order=[]),
        created_at="2026-06-09T00:00:00+00:00",
        updated_at="2026-06-09T00:00:00+00:00",
        metadata={},
    )

    def fake_get_internal_with_scope(job_id):
        calls["internal_with_scope"] += 1
        return job, WORKSPACE_A, "user_a"

    def fake_get_scoped(*args, **kwargs):
        calls["scoped"] += 1
        return job

    def fake_mark_stale(current_job, **kwargs):
        stale_scope.update(kwargs)
        return current_job

    def fake_poll_modal(current_job, **kwargs):
        modal_scope.update(kwargs)
        return current_job

    monkeypatch.setattr(
        "orchestrator.app.api.routers.generation_jobs.get_generation_job_internal_with_scope",
        fake_get_internal_with_scope,
        raising=False,
    )
    monkeypatch.setattr("orchestrator.app.api.routers.generation_jobs.get_generation_job_scoped", fake_get_scoped)
    monkeypatch.setattr("orchestrator.app.api.routers.generation_jobs.maybe_mark_stale_generation_job_failed", fake_mark_stale)
    monkeypatch.setattr("orchestrator.app.api.routers.generation_jobs.maybe_poll_generation_job_from_modal", fake_poll_modal)

    response = TestClient(create_app()).get(
        "/api/v1/generation-jobs/job_polling",
        headers={"X-EasyAds-User-Id": "user_a"},
    )

    assert response.status_code == 200
    assert calls == {"internal_with_scope": 1, "scoped": 0}
    assert stale_scope == {"workspace_id": WORKSPACE_A, "user_id": "user_a"}
    assert modal_scope == {"workspace_id": WORKSPACE_A, "user_id": "user_a"}


def test_generation_job_get_route_rejects_reused_scope_for_other_user(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")
    monkeypatch.setenv("EASYADS_ALLOW_DEMO_WORKSPACE_FALLBACK", "false")
    job = GenerationJobResponse(
        job_id="job_polling",
        thread_id="thread_polling",
        user_id="user_a",
        status="running",
        progress=GenerationProgress(progress_percent=50, current_stage="brief_interpretation", stage_order=[]),
        created_at="2026-06-09T00:00:00+00:00",
        updated_at="2026-06-09T00:00:00+00:00",
        metadata={},
    )

    monkeypatch.setattr(
        "orchestrator.app.api.routers.generation_jobs.get_generation_job_internal_with_scope",
        lambda job_id: (job, WORKSPACE_A, "user_a"),
    )
    monkeypatch.setattr(
        "orchestrator.app.api.routers.generation_jobs.get_generation_job_scoped",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("scoped lookup should not run after user mismatch")),
    )

    response = TestClient(create_app()).get(
        "/api/v1/generation-jobs/job_polling",
        headers={"X-EasyAds-User-Id": "user_b"},
    )

    assert response.status_code == 404
    assert response.json()["detail"]["error_code"] == "generation_job_not_found"


def test_generation_job_get_route_passes_workspace_scope(monkeypatch):
    reset_generation_job_store_for_tests()
    captured = {}
    job = GenerationJobResponse(
        job_id="job_scoped",
        thread_id="thread_scoped",
        user_id="user_a",
        status="queued",
        progress=GenerationProgress(progress_percent=0, current_stage="queued", stage_order=[]),
        created_at="2026-06-09T00:00:00+00:00",
        updated_at="2026-06-09T00:00:00+00:00",
        metadata={},
    )

    def fake_get_generation_job(job_id, *, workspace_id=None, user_id=None):
        captured.update({"job_id": job_id, "workspace_id": workspace_id, "user_id": user_id})
        return job if workspace_id == WORKSPACE_A else None

    monkeypatch.setattr("orchestrator.app.api.routers.generation_jobs.get_generation_job_scoped", fake_get_generation_job)
    monkeypatch.setattr("orchestrator.app.api.routers.generation_jobs.maybe_mark_stale_generation_job_failed", lambda job, **kwargs: job)
    monkeypatch.setattr("orchestrator.app.api.routers.generation_jobs.maybe_poll_generation_job_from_modal", lambda job, **kwargs: job)

    response = TestClient(create_app()).get(
        f"/api/v1/generation-jobs/job_scoped?workspace_id={WORKSPACE_A}",
        headers={"X-EasyAds-User-Id": "user_a"},
    )

    assert response.status_code == 200
    assert captured == {"job_id": "job_scoped", "workspace_id": WORKSPACE_A, "user_id": "user_a"}


def test_generation_job_get_route_resolves_workspace_from_user_header(monkeypatch):
    # B1: HITL polling only carries the authenticated user (no workspace id).
    # The route must resolve a workspace instead of raising "workspaceId is required.".
    captured = {}

    def fake_get_generation_job(job_id, *, workspace_id=None, user_id=None):
        captured.update({"job_id": job_id, "workspace_id": workspace_id, "user_id": user_id})
        return None

    monkeypatch.setattr("orchestrator.app.api.routers.generation_jobs.get_generation_job_scoped", fake_get_generation_job)

    response = TestClient(create_app()).get(
        "/api/v1/generation-jobs/job_scoped",
        headers={"X-EasyAds-User-Id": "user_a"},
    )

    # Memory backend resolves to the shared mem workspace; no 400 workspace_required.
    assert response.status_code == 404
    assert captured == {"job_id": "job_scoped", "workspace_id": "mem_workspace", "user_id": "user_a"}


def test_generation_job_get_route_passes_guest_account_type_to_workspace_resolution(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")
    monkeypatch.setenv("EASYADS_ALLOW_DEMO_WORKSPACE_FALLBACK", "false")
    captured_scope = {}
    captured_job = {}

    def fake_resolve_scoped_workspace_id(workspace_id, user_id, account_type=None):
        captured_scope.update({"workspace_id": workspace_id, "user_id": user_id, "account_type": account_type})
        return WORKSPACE_A

    def fake_get_generation_job(job_id, *, workspace_id=None, user_id=None):
        captured_job.update({"job_id": job_id, "workspace_id": workspace_id, "user_id": user_id})
        return None

    monkeypatch.setattr(
        "orchestrator.app.api.routers.generation_jobs.get_generation_job_internal_with_scope",
        lambda job_id: (None, None, None),
        raising=False,
    )
    monkeypatch.setattr("orchestrator.app.api.routers.generation_jobs.resolve_scoped_workspace_id", fake_resolve_scoped_workspace_id)
    monkeypatch.setattr("orchestrator.app.api.routers.generation_jobs.get_generation_job_scoped", fake_get_generation_job)

    response = TestClient(create_app()).get(
        "/api/v1/generation-jobs/job_guest",
        headers={
            "X-EasyAds-User-Id": "guest_uuid_1",
            "X-EasyAds-Account-Type": "guest",
        },
    )

    assert response.status_code == 404
    assert captured_scope == {"workspace_id": None, "user_id": "guest_uuid_1", "account_type": "guest"}
    assert captured_job == {"job_id": "job_guest", "workspace_id": WORKSPACE_A, "user_id": "guest_uuid_1"}


def test_generation_job_get_route_returns_404_for_cross_workspace(monkeypatch):
    monkeypatch.setattr("orchestrator.app.api.routers.generation_jobs.get_generation_job_scoped", lambda job_id, **kwargs: None)

    response = TestClient(create_app()).get(
        f"/api/v1/generation-jobs/job_scoped?workspace_id={WORKSPACE_B}",
        headers={"X-EasyAds-User-Id": "user_a"},
    )

    assert response.status_code == 404
    assert response.json()["detail"]["error_code"] == "generation_job_not_found"


def test_generation_job_answer_route_passes_workspace_scope(monkeypatch):
    captured = {}
    job = GenerationJobResponse(
        job_id="job_waiting",
        thread_id="thread_waiting",
        user_id="user_a",
        status="waiting_user_input",
        progress=GenerationProgress(progress_percent=50, current_stage="waiting_user_input", stage_order=[]),
        created_at="2026-06-09T00:00:00+00:00",
        updated_at="2026-06-09T00:00:00+00:00",
        metadata={},
    )

    def fake_get_generation_job(job_id, *, workspace_id=None, user_id=None):
        captured.update({"job_id": job_id, "workspace_id": workspace_id, "user_id": user_id})
        return job

    monkeypatch.setattr("orchestrator.app.api.routers.generation_jobs.get_generation_job_scoped", fake_get_generation_job)
    monkeypatch.setattr("orchestrator.app.api.routers.generation_jobs.mark_generation_job_running", lambda job_id, stage="planning", **kwargs: job)
    monkeypatch.setattr("orchestrator.app.api.routers.generation_jobs.resume_generation_job_graph", lambda *args, **kwargs: job)

    response = TestClient(create_app()).post(
        f"/api/v1/generation-jobs/job_waiting/answer?workspace_id={WORKSPACE_A}",
        headers={"X-EasyAds-User-Id": "user_a"},
        json={"field": "business_type", "value": "cafe"},
    )

    assert response.status_code == 200
    assert captured == {"job_id": "job_waiting", "workspace_id": WORKSPACE_A, "user_id": "user_a"}


def test_generation_job_answer_route_recovers_scope_from_existing_job_without_header(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")
    monkeypatch.setenv("EASYADS_ALLOW_DEMO_WORKSPACE_FALLBACK", "false")
    captured = {}
    running_scope = {}
    resume_scope = {}
    job = GenerationJobResponse(
        job_id="job_waiting",
        thread_id="thread_waiting",
        user_id="user_a",
        status="waiting_user_input",
        progress=GenerationProgress(progress_percent=50, current_stage="waiting_user_input", stage_order=[]),
        created_at="2026-06-09T00:00:00+00:00",
        updated_at="2026-06-09T00:00:00+00:00",
        metadata={},
    )

    def fake_get_generation_job(job_id, *, workspace_id=None, user_id=None):
        captured.update({"job_id": job_id, "workspace_id": workspace_id, "user_id": user_id})
        return job

    def fake_mark_running(job_id, stage="planning", **kwargs):
        running_scope.update(kwargs)
        return job

    def fake_resume(job_id, answer, *, allow_running=False, **kwargs):
        resume_scope.update(kwargs)
        return job

    monkeypatch.setattr(
        "orchestrator.app.api.routers.generation_jobs.resolve_generation_job_scope_from_existing_job",
        lambda job_id: (WORKSPACE_A, "user_a"),
    )
    monkeypatch.setattr("orchestrator.app.api.routers.generation_jobs.get_generation_job_scoped", fake_get_generation_job)
    monkeypatch.setattr("orchestrator.app.api.routers.generation_jobs.mark_generation_job_running", fake_mark_running)
    monkeypatch.setattr("orchestrator.app.api.routers.generation_jobs.resume_generation_job_graph", fake_resume)
    monkeypatch.setattr("orchestrator.app.api.routers.generation_jobs.record_generation_job_lifecycle_event", lambda *args, **kwargs: None)

    response = TestClient(create_app()).post(
        "/api/v1/generation-jobs/job_waiting/answer",
        json={"field": "business_type", "value": "cafe"},
    )

    assert response.status_code == 200
    assert captured == {"job_id": "job_waiting", "workspace_id": WORKSPACE_A, "user_id": "user_a"}
    assert running_scope == {"workspace_id": WORKSPACE_A, "user_id": "user_a"}
    assert resume_scope == {"workspace_id": WORKSPACE_A, "user_id": "user_a"}


def test_generation_job_answer_route_passes_guest_account_type_to_workspace_resolution(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")
    monkeypatch.setenv("EASYADS_ALLOW_DEMO_WORKSPACE_FALLBACK", "false")
    captured_scope = {}
    captured_job = {}
    job = GenerationJobResponse(
        job_id="job_waiting",
        thread_id="thread_waiting",
        user_id="guest_uuid_1",
        status="waiting_user_input",
        progress=GenerationProgress(progress_percent=50, current_stage="waiting_user_input", stage_order=[]),
        created_at="2026-06-09T00:00:00+00:00",
        updated_at="2026-06-09T00:00:00+00:00",
        metadata={},
    )

    def fake_resolve_scoped_workspace_id(workspace_id, user_id, account_type=None):
        captured_scope.update({"workspace_id": workspace_id, "user_id": user_id, "account_type": account_type})
        return WORKSPACE_A

    def fake_get_generation_job(job_id, *, workspace_id=None, user_id=None):
        captured_job.update({"job_id": job_id, "workspace_id": workspace_id, "user_id": user_id})
        return job

    monkeypatch.setattr("orchestrator.app.api.routers.generation_jobs.resolve_scoped_workspace_id", fake_resolve_scoped_workspace_id)
    monkeypatch.setattr("orchestrator.app.api.routers.generation_jobs.get_generation_job_scoped", fake_get_generation_job)
    monkeypatch.setattr("orchestrator.app.api.routers.generation_jobs.mark_generation_job_running", lambda job_id, stage="planning", **kwargs: job)
    monkeypatch.setattr("orchestrator.app.api.routers.generation_jobs.resume_generation_job_graph", lambda *args, **kwargs: job)
    monkeypatch.setattr("orchestrator.app.api.routers.generation_jobs.record_generation_job_lifecycle_event", lambda *args, **kwargs: None)

    response = TestClient(create_app()).post(
        "/api/v1/generation-jobs/job_waiting/answer",
        headers={
            "X-EasyAds-User-Id": "guest_uuid_1",
            "X-EasyAds-Account-Type": "guest",
        },
        json={"field": "business_type", "value": "cafe"},
    )

    assert response.status_code == 200
    assert captured_scope == {"workspace_id": None, "user_id": "guest_uuid_1", "account_type": "guest"}
    assert captured_job == {"job_id": "job_waiting", "workspace_id": WORKSPACE_A, "user_id": "guest_uuid_1"}


def test_generation_job_create_route_passes_guest_account_type_header(monkeypatch):
    captured = {}
    job = GenerationJobResponse(
        job_id="job_guest",
        thread_id="thread_guest",
        user_id="guest_uuid_1",
        status="queued",
        progress=GenerationProgress(progress_percent=0, current_stage="queued", stage_order=[]),
        created_at="2026-06-11T00:00:00+00:00",
        updated_at="2026-06-11T00:00:00+00:00",
        metadata={"account_type": "guest"},
    )

    def fake_create_generation_job(request):
        captured["user_id"] = request.user_id
        captured["account_type"] = request.account_type
        return job

    monkeypatch.setattr("orchestrator.app.api.routers.generation_jobs.create_generation_job", fake_create_generation_job)
    monkeypatch.setattr("orchestrator.app.api.routers.generation_jobs.should_route_generation_job_to_modal", lambda request: False)

    response = TestClient(create_app()).post(
        "/api/v1/generation-jobs",
        headers={
            "X-EasyAds-User-Id": "guest_uuid_1",
            "X-EasyAds-Account-Type": "guest",
        },
        json={"userInput": "게스트 광고", "runMode": "queued_only"},
    )

    assert response.status_code == 201
    assert captured == {"user_id": "guest_uuid_1", "account_type": "guest"}


def test_generation_job_create_route_merges_guest_scope_with_demo_fallback(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "postgres")
    monkeypatch.setenv("EASYADS_ALLOW_DEMO_WORKSPACE_FALLBACK", "true")
    captured = {}
    job = GenerationJobResponse(
        job_id="job_guest",
        thread_id="thread_guest",
        user_id=None,
        status="queued",
        progress=GenerationProgress(progress_percent=0, current_stage="queued", stage_order=[]),
        created_at="2026-06-11T00:00:00+00:00",
        updated_at="2026-06-11T00:00:00+00:00",
        metadata={"account_type": "guest"},
    )

    def fake_create_generation_job(request):
        captured["user_id"] = request.user_id
        captured["workspace_id"] = request.workspace_id
        captured["account_type"] = request.account_type
        return job

    monkeypatch.setattr("orchestrator.app.api.routers.generation_jobs.create_generation_job", fake_create_generation_job)
    monkeypatch.setattr("orchestrator.app.api.routers.generation_jobs.should_route_generation_job_to_modal", lambda request: False)

    response = TestClient(create_app()).post(
        "/api/v1/generation-jobs",
        headers={
            "X-EasyAds-Workspace-Id": WORKSPACE_A,
            "X-EasyAds-Account-Type": "guest",
        },
        json={"userInput": "게스트 광고", "runMode": "queued_only"},
    )

    assert response.status_code == 201
    assert captured == {"user_id": None, "workspace_id": WORKSPACE_A, "account_type": "guest"}


# ===== from test_api_generation_outputs_router.py =====
import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from orchestrator.app.api.app import create_app

@pytest.fixture
def client__test_api_generation_outputs_router():
    return create_app_client()

def test_list_generation_outputs(client__test_api_generation_outputs_router, monkeypatch):
    mock_service = MagicMock()
    mock_service.return_value = ([], 0)
    monkeypatch.setattr("orchestrator.app.api.routers.generation_outputs.list_generation_outputs", mock_service)

    mock_scope = MagicMock()
    mock_scope.return_value = "ws1"
    monkeypatch.setattr("orchestrator.app.db.workspace_scope.resolve_workspace_scope", mock_scope)

    resp = client__test_api_generation_outputs_router.get("/api/v1/generation-outputs?workspace_id=ws1")
    assert resp.status_code == 200
    assert resp.json()["items"] == []

def test_select_final_generation_output(client__test_api_generation_outputs_router, monkeypatch):
    mock_service = MagicMock()

    from orchestrator.app.api.schemas.generation_outputs import GenerationOutputResponse

    mock_service.return_value = GenerationOutputResponse(
        output_id="out1", is_final=True, variant_index=0, output_type="final_image", created_at="2026-06-06T00:00:00Z", updated_at="2026-06-06T00:00:00Z"
    )
    monkeypatch.setattr("orchestrator.app.api.routers.generation_outputs.select_final_generation_output", mock_service)

    mock_scope = MagicMock()
    mock_scope.return_value = "ws1"
    monkeypatch.setattr("orchestrator.app.db.workspace_scope.resolve_workspace_scope", mock_scope)

    resp = client__test_api_generation_outputs_router.post("/api/v1/generation-outputs/out1/select-final?workspace_id=ws1")
    assert resp.status_code == 200
    assert resp.json()["output_id"] == "out1"


# ===== from test_api_references_router.py =====
import json

from fastapi.testclient import TestClient

from orchestrator.app.api.app import create_app
from orchestrator.app.reference_catalog.service import load_reference_templates
import orchestrator.app.reference_catalog.service as reference_service


LOCAL_PATH_PATTERNS = [
    "C:\\",
    "C:/",
    "\\Users\\",
    "/home/",
    "data/reference_templates",
    "data/outputs",
    "data/processed",
]


def client__test_api_references_router() -> TestClient:
    return TestClient(create_app())


def assert_no_local_paths(payload: object) -> None:
    text = json.dumps(payload, ensure_ascii=False)
    for pattern in LOCAL_PATH_PATTERNS:
        assert pattern not in text


def test_create_app_openapi_registers_reference_routes():
    app = create_app()
    schema = app.openapi()

    assert schema["info"]["title"] == "EasyAds Orchestrator API"
    assert "/api/v1/references" in schema["paths"]
    assert "/api/v1/references/{template_id}" in schema["paths"]
    assert "/api/v1/references/{template_id}/similar" in schema["paths"]


def test_list_references_returns_items_and_pagination():
    response = client__test_api_references_router().get("/api/v1/references")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert isinstance(payload["items"], list)
    assert payload["items"]
    assert payload["pagination"]["total"] >= len(payload["items"])
    assert_no_local_paths(payload)


def test_reference_filters_and_sorting_work():
    http = client__test_api_references_router()

    by_category = http.get("/api/v1/references", params={"category": "cafe"})
    assert by_category.status_code == 200
    assert all(item["category"] == "cafe" for item in by_category.json()["items"])

    by_business = http.get("/api/v1/references", params={"business_type": "cafe"})
    assert by_business.status_code == 200
    assert all("cafe" in item["business_types"] for item in by_business.json()["items"])

    by_format = http.get("/api/v1/references", params={"ad_format": "instagram_feed"})
    assert by_format.status_code == 200
    assert all("instagram_feed" in item["ad_formats"] for item in by_format.json()["items"])

    by_keyword = http.get("/api/v1/references", params={"keyword": "cafe"})
    assert by_keyword.status_code == 200
    assert by_keyword.json()["items"]

    by_tags = http.get("/api/v1/references?tags=CTA&tags=CTA")
    assert by_tags.status_code == 200

    by_style = http.get("/api/v1/references?style_keywords=warm&style_keywords=cute")
    assert by_style.status_code == 200

    popular = http.get("/api/v1/references", params={"sort_by": "popular", "limit": 3})
    assert popular.status_code == 200
    scores = [item["popularity_score"] for item in popular.json()["items"]]
    assert scores == sorted(scores, reverse=True)


def test_reference_keyword_aliases_include_cafe_for_food_and_drink():
    http = client__test_api_references_router()

    food = http.get("/api/v1/references", params={"keyword": "음식", "limit": 20})
    assert food.status_code == 200
    assert any(item["category"] == "cafe" for item in food.json()["items"])
    assert any(item["category"] == "restaurant" for item in food.json()["items"])

    drink = http.get("/api/v1/references", params={"keyword": "음료", "limit": 20})
    assert drink.status_code == 200
    assert any(item["category"] == "cafe" for item in drink.json()["items"])

    english_drink = http.get("/api/v1/references", params={"keyword": "drink", "limit": 20})
    assert english_drink.status_code == 200
    assert any(item["category"] == "cafe" for item in english_drink.json()["items"])


def test_reference_multi_tag_query_matches_any_alias_term():
    response = client__test_api_references_router().get("/api/v1/references?tags=음료&tags=삼겹살&limit=20")

    assert response.status_code == 200
    categories = {item["category"] for item in response.json()["items"]}
    assert {"cafe", "restaurant"} <= categories


def test_reference_food_category_includes_cafe_and_restaurant():
    response = client__test_api_references_router().get("/api/v1/references", params={"category": "food", "limit": 20})

    assert response.status_code == 200
    payload = response.json()
    assert any(item["category"] == "cafe" for item in payload["items"])
    assert any(item["category"] == "restaurant" for item in payload["items"])


def test_limit_offset_and_empty_state():
    http = client__test_api_references_router()
    limited = http.get("/api/v1/references", params={"limit": 2, "offset": 1})
    assert limited.status_code == 200
    assert len(limited.json()["items"]) <= 2
    assert limited.json()["pagination"]["offset"] == 1

    empty = http.get("/api/v1/references", params={"keyword": "no-such-template-keyword"})
    payload = empty.json()
    assert empty.status_code == 200
    assert payload["items"] == []
    assert payload["empty_state"]["kind"] == "no_reference_templates"


def test_reference_detail_returns_slim_template_and_no_internal_paths():
    template = load_reference_templates()[0]
    response = client__test_api_references_router().get(f"/api/v1/references/{template.template_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["template"]["template_id"] == template.template_id
    assert "similar_templates" in payload
    assert "has_source_image" in payload["detail"]
    assert_no_local_paths(payload)


def test_reference_detail_not_found_returns_structured_error():
    response = client__test_api_references_router().get("/api/v1/references/not_found")

    assert response.status_code == 404
    detail = response.json()["detail"]
    assert detail["success"] is False
    assert detail["error_code"] == "reference_template_not_found"


def test_similar_references_excludes_self_and_applies_limit():
    template = load_reference_templates()[0]
    response = client__test_api_references_router().get(f"/api/v1/references/{template.template_id}/similar", params={"limit": 2})

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["template_id"] == template.template_id
    assert len(payload["items"]) <= 2
    assert all(item["template_id"] != template.template_id for item in payload["items"])
    assert_no_local_paths(payload)


def test_temporary_reference_assets_are_exposed_without_local_paths(monkeypatch, tmp_path):
    manifest_dir = tmp_path / "2026-06-user-refs"
    manifest_dir.mkdir()
    image_path = manifest_dir / "watermelon-juice.png"
    image_path.write_bytes(b"temporary image")
    manifest = {
        "removal_group": "2026-06-user-refs",
        "items": [
            {
                "template_id": "temp_watermelon_juice_feed",
                "title": "수박주스 블루 여름 피드",
                "category": "cafe",
                "tags": ["수박", "여름"],
                "business_types": ["cafe"],
                "ad_formats": ["instagram_feed"],
                "platforms": ["instagram"],
                "assets": {
                    "thumbnail_path": "watermelon-juice.png",
                    "preview_path": "watermelon-juice.png",
                },
                "style_keywords": ["summer", "blue"],
                "color_palette": ["#5AB4F2", "#EF3B3B"],
                "layout_hint": "top_large_headline_center_product_bottom_copy",
                "background_style": "bright blue summer beverage poster",
                "popularity_score": 0.5,
            }
        ],
    }
    (manifest_dir / "catalog.local.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("EASYADS_TEMP_REFERENCE_ROOT", str(tmp_path))
    monkeypatch.setenv("EASYADS_ENABLE_TEMP_REFERENCES", "true")

    response = client__test_api_references_router().get("/api/v1/references", params={"keyword": "수박주스"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["template_id"] == "temp_watermelon_juice_feed"
    assert payload["items"][0]["thumbnail_url"] == "/api/v1/references/temp-assets/2026-06-user-refs/watermelon-juice.png"
    assert payload["items"][0]["preview_url"] == "/api/v1/references/temp-assets/2026-06-user-refs/watermelon-juice.png"
    assert_no_local_paths(payload)

    asset_response = client__test_api_references_router().get(payload["items"][0]["thumbnail_url"])
    assert asset_response.status_code == 200
    assert asset_response.content == b"temporary image"
    assert asset_response.headers["cache-control"] == "public, max-age=604800, immutable"


def test_permanent_reference_assets_use_r2_public_urls(monkeypatch, tmp_path):
    manifest_path = tmp_path / "permanent-catalog.json"
    object_key = "reference-templates/v1/ref_test_cafe_owned_001/source.png"
    manifest = {
        "items": [
            {
                "template_id": "ref_test_cafe_owned_001",
                "title": "운영 샘플 테스트",
                "category": "cafe",
                "tags": ["음료"],
                "business_types": ["cafe"],
                "ad_formats": ["instagram_feed"],
                "platforms": ["instagram"],
                "assets": {
                    "thumbnail_path": f"r2://{object_key}",
                    "preview_path": f"r2://{object_key}",
                },
                "style_keywords": ["clean"],
                "popularity_score": 0.5,
                "metadata": {
                    "source_file": "owned-cafe.png",
                    "r2_object_key": object_key,
                },
            }
        ]
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("EASYADS_PERMANENT_REFERENCE_MANIFEST", str(manifest_path))
    monkeypatch.setenv("EASYADS_R2_PUBLIC_BASE_URL", "https://assets.example.com/easyads")

    response = client__test_api_references_router().get("/api/v1/references", params={"keyword": "운영 샘플"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["template_id"] == "ref_test_cafe_owned_001"
    assert payload["items"][0]["thumbnail_url"] == f"https://assets.example.com/easyads/{object_key}"
    assert payload["items"][0]["preview_url"] == f"https://assets.example.com/easyads/{object_key}"
    assert_no_local_paths(payload)

    detail = client__test_api_references_router().get("/api/v1/references/ref_test_cafe_owned_001")
    assert detail.status_code == 200
    assert_no_local_paths(detail.json())


def test_permanent_reference_assets_use_signed_r2_urls_when_public_base_is_missing(monkeypatch, tmp_path):
    manifest_path = tmp_path / "permanent-catalog.json"
    object_key = "reference-templates/v1/ref_test_signed_001/source.png"
    manifest = {
        "items": [
            {
                "template_id": "ref_test_signed_001",
                "title": "서명 URL 샘플 테스트",
                "category": "cafe",
                "tags": ["음료"],
                "business_types": ["cafe"],
                "ad_formats": ["instagram_feed"],
                "platforms": ["instagram"],
                "assets": {
                    "thumbnail_path": f"r2://{object_key}",
                    "preview_path": f"r2://{object_key}",
                },
                "style_keywords": ["clean"],
                "popularity_score": 0.5,
                "metadata": {"r2_object_key": object_key},
            }
        ]
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("EASYADS_PERMANENT_REFERENCE_MANIFEST", str(manifest_path))
    monkeypatch.delenv("EASYADS_R2_PUBLIC_BASE_URL", raising=False)
    monkeypatch.setenv("EASYADS_ENABLE_R2_UPLOAD", "true")
    monkeypatch.setenv("EASYADS_R2_URL_MODE", "signed")
    monkeypatch.setenv("EASYADS_R2_BUCKET", "easyads-assets")
    monkeypatch.setenv("EASYADS_R2_ENDPOINT_URL", "https://r2.example.com")
    monkeypatch.setenv("EASYADS_R2_ACCESS_KEY_ID", "key")
    monkeypatch.setenv("EASYADS_R2_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setattr(reference_service, "create_r2_client", lambda: object())
    monkeypatch.setattr(
        reference_service,
        "generate_signed_get_url",
        lambda *, client, bucket, object_key, expires_in: f"https://signed.example.com/{object_key}?ttl={expires_in}",
    )

    response = client__test_api_references_router().get("/api/v1/references", params={"keyword": "서명 URL"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["template_id"] == "ref_test_signed_001"
    assert payload["items"][0]["thumbnail_url"].startswith("https://signed.example.com/reference-templates/v1/ref_test_signed_001/source.png")
    assert payload["items"][0]["preview_url"].startswith("https://signed.example.com/reference-templates/v1/ref_test_signed_001/source.png")
    assert_no_local_paths(payload)


# ===== from test_api_usage_summary.py =====
from fastapi.testclient import TestClient

from orchestrator.app.api.app import create_app
from orchestrator.app.usage import service


def setup_function():
    service.reset_usage_store_for_tests()


def teardown_function():
    service.reset_usage_store_for_tests()


def test_openapi_registers_usage_summary():
    schema = create_app().openapi()

    assert "/api/v1/usage/summary" in schema["paths"]


def test_usage_summary_api_returns_memory_totals(monkeypatch):
    monkeypatch.setenv("EASYADS_DB_BACKEND", "memory")
    monkeypatch.setattr("orchestrator.app.api.routers.usage.resolve_workspace_scope", lambda workspace_id, user_id: "ws1")
    service.record_llm_usage(
        workspace_id="ws1",
        provider="openai",
        model_name="gpt-4.1-mini",
        input_tokens=10,
        output_tokens=5,
        plan="premium",
    )

    response = TestClient(create_app()).get(
        "/api/v1/usage/summary",
        params={
            "workspaceId": "ws1",
            "plan": "premium",
            "startAt": "2026-01-01T00:00:00Z",
            "endAt": "2027-01-01T00:00:00Z",
        },
    )

    assert response.status_code == 200
    summary = response.json()["summary"]
    assert summary["scope"] == "workspace"
    assert summary["totals"]["llmCalls"] == 1
    assert summary["totals"]["llmInputTokens"] == 10
    assert summary["totals"]["llmOutputTokens"] == 5
    assert summary["totals"]["unpricedEventCount"] == 1
