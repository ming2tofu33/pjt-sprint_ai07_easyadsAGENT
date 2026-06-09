"""Errors for GenerationJob service."""

class GenerationJobError(Exception):
    status_code = 400
    error_code = "generation_job_error"
    
    def __init__(self, message: str, error_code: str | None = None):
        self.message = message
        if error_code:
            self.error_code = error_code
        super().__init__(self.message)

class GenerationJobAssetNotFound(GenerationJobError):
    status_code = 404
    error_code = "asset_not_found"

class GenerationJobAssetNotReady(GenerationJobError):
    status_code = 409
    error_code = "asset_not_ready"

class GenerationJobAssetKindInvalid(GenerationJobError):
    status_code = 422
    error_code = "asset_kind_invalid"

class GenerationJobAssetPersistenceRequired(GenerationJobError):
    status_code = 400
    error_code = "asset_persistence_required"


class GenerationJobWorkspaceRequired(GenerationJobError):
    status_code = 400
    error_code = "workspace_required"


class GenerationJobWorkspaceNotFound(GenerationJobError):
    status_code = 404
    error_code = "workspace_not_found"


class GenerationJobWorkspaceForbidden(GenerationJobError):
    status_code = 404
    error_code = "workspace_not_found"


class GenerationJobWorkspaceConflict(GenerationJobError):
    status_code = 409
    error_code = "generation_job_workspace_conflict"
