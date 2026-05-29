"""Pydantic DTOs for backend API contracts."""

from orchestrator.app.api.schemas.archive import ArchiveItemResponse, ArchiveListResponse
from orchestrator.app.api.schemas.brand_kits import (
    BrandKitCreateRequest,
    BrandKitGetCurrentResponse,
    BrandKitResponse,
    BrandKitUpdateRequest,
    BrandProduct,
)
from orchestrator.app.api.schemas.common import (
    ApiMeta,
    AssetRef,
    EmptyState,
    ErrorResponse,
    Pagination,
    RecoveryAction,
)
from orchestrator.app.api.schemas.generation_jobs import (
    GenerationJobCreateRequest,
    GenerationJobCreateResponse,
    GenerationJobGetResponse,
    GenerationJobResponse,
    GenerationProgress,
)
from orchestrator.app.api.schemas.references import (
    ReferenceTemplateCardResponse,
    ReferenceTemplateDetailResponse,
    ReferenceTemplateListResponse,
    ReferenceTemplateSimilarResponse,
)
from orchestrator.app.api.schemas.settings import (
    NotificationSettingsResponse,
    UserAppSettingsResponse,
    UserAppSettingsUpdateRequest,
)
from orchestrator.app.api.schemas.usage import UsageEventResponse, UsageSummaryResponse

__all__ = [
    "ApiMeta",
    "ArchiveItemResponse",
    "ArchiveListResponse",
    "AssetRef",
    "BrandKitCreateRequest",
    "BrandKitGetCurrentResponse",
    "BrandKitResponse",
    "BrandKitUpdateRequest",
    "BrandProduct",
    "EmptyState",
    "ErrorResponse",
    "GenerationJobCreateRequest",
    "GenerationJobCreateResponse",
    "GenerationJobGetResponse",
    "GenerationJobResponse",
    "GenerationProgress",
    "NotificationSettingsResponse",
    "Pagination",
    "RecoveryAction",
    "ReferenceTemplateCardResponse",
    "ReferenceTemplateDetailResponse",
    "ReferenceTemplateListResponse",
    "ReferenceTemplateSimilarResponse",
    "UsageEventResponse",
    "UsageSummaryResponse",
    "UserAppSettingsResponse",
    "UserAppSettingsUpdateRequest",
]
