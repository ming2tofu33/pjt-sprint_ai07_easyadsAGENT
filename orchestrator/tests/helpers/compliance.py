def assert_compliance_badge(candidate: dict, *, status: str, disabled: bool) -> None:
    badge = candidate["metadata"]["compliance"]
    assert badge["status"] == status
    assert badge["disabled"] is disabled


def assert_compliance_record(record: dict, *, candidate_id: str, publication_ready: bool | None = None) -> None:
    assert record["candidate_id"] == candidate_id
    if publication_ready is not None:
        assert record["publication_ready"] is publication_ready
