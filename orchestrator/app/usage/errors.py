"""Usage tracking errors."""

from __future__ import annotations


class UsageError(RuntimeError):
    status_code = 400
    error_code = "usage_error"

    def __init__(self, message: str, error_code: str | None = None):
        super().__init__(message)
        self.message = message
        if error_code:
            self.error_code = error_code


class UsagePersistenceUnavailable(UsageError):
    status_code = 503
    error_code = "usage_persistence_unavailable"


class InvalidUsageRange(UsageError):
    status_code = 400
    error_code = "invalid_usage_range"


class InvalidUsageScope(UsageError):
    status_code = 400
    error_code = "invalid_usage_scope"


class InvalidUsagePlan(UsageError):
    status_code = 400
    error_code = "invalid_usage_plan"
