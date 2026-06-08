"""Quality gate errors."""


class QualityGateError(RuntimeError):
    pass


class QualityGateUnavailable(QualityGateError):
    pass


class QualityGateInvalidResponse(QualityGateError):
    pass

