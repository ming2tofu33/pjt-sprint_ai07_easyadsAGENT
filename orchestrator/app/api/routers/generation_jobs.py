"""GenerationJob API routes."""

from __future__ import annotations

from typing import NoReturn

from fastapi import APIRouter, status

from orchestrator.app.api.errors import raise_api_error
from orchestrator.app.api.schemas.generation_jobs import (
    GenerationJobCreateRequest,
    GenerationJobCreateResponse,
    GenerationJobGetResponse,
)
from orchestrator.app.generation_jobs.service import create_generation_job, get_generation_job
from orchestrator.app.reference_catalog.service import get_reference_template

router = APIRouter()


def _generation_job_not_found(job_id: str) -> NoReturn:
    raise_api_error(
        status_code=404,
        error_code="generation_job_not_found",
        message="Generation job was not found.",
        detail=f"job_id={job_id}",
    )


def _reference_template_not_found(template_id: str) -> NoReturn:
    raise_api_error(
        status_code=404,
        error_code="reference_template_not_found",
        message="Reference template was not found.",
        detail=f"template_id={template_id}",
    )


@router.post("/generation-jobs", response_model=GenerationJobCreateResponse, status_code=status.HTTP_201_CREATED)
def create_generation_job_route(request: GenerationJobCreateRequest) -> GenerationJobCreateResponse:
    if request.selected_reference_template_id and not get_reference_template(request.selected_reference_template_id):
        _reference_template_not_found(request.selected_reference_template_id)
    return GenerationJobCreateResponse(job=create_generation_job(request))


@router.get("/generation-jobs/{job_id}", response_model=GenerationJobGetResponse)
def get_generation_job_route(job_id: str) -> GenerationJobGetResponse:
    job = get_generation_job(job_id)
    if not job:
        _generation_job_not_found(job_id)
    return GenerationJobGetResponse(job=job)
