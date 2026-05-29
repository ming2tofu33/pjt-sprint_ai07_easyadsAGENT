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
