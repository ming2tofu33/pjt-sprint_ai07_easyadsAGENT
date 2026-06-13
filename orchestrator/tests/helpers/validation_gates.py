def assert_validation_decision(result, expected_decision: str) -> None:
    assert result.decision == expected_decision


def assert_validation_status(result, expected_status: str) -> None:
    assert result.status == expected_status
