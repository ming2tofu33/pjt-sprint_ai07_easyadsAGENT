"""Validation feedback errors."""


class ValidationFeedbackError(RuntimeError):
    status_code = 400
    error_code = "validation_feedback_error"
    message = "Validation feedback request failed."


class GenerationOutputNotFound(ValidationFeedbackError):
    status_code = 404
    error_code = "generation_output_not_found"
    message = "Generation output was not found."


class ValidationReportNotFound(ValidationFeedbackError):
    status_code = 404
    error_code = "validation_report_not_found"
    message = "Validation report was not found."


class InvalidRegenerationAction(ValidationFeedbackError):
    status_code = 400
    error_code = "invalid_regeneration_action"
    message = "Regeneration action is not allowed for this output."


class RegenerationNotRecommended(ValidationFeedbackError):
    status_code = 409
    error_code = "regeneration_not_recommended"
    message = "Regeneration is not recommended for this output."


class RegenerationDepthExceeded(ValidationFeedbackError):
    status_code = 409
    error_code = "regeneration_depth_exceeded"
    message = "Maximum regeneration depth was reached."

