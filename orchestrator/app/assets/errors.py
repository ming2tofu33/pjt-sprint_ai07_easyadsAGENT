"""Asset service errors."""

class AssetServiceError(Exception):
    status_code = 400
    def __init__(self, message: str, error_code: str):
        super().__init__(message)
        self.message = message
        self.error_code = error_code

class NotFoundError(AssetServiceError):
    status_code = 404

class ConflictError(AssetServiceError):
    status_code = 409

class UnprocessableEntityError(AssetServiceError):
    status_code = 422

class PayloadTooLargeError(AssetServiceError):
    status_code = 413

class UnsupportedMediaTypeError(AssetServiceError):
    status_code = 415

class ServiceUnavailableError(AssetServiceError):
    status_code = 503

class AssetWorkspaceRequired(AssetServiceError):
    status_code = 400

class AssetWorkspaceForbidden(AssetServiceError):
    status_code = 403
