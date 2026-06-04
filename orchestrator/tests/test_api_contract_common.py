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
