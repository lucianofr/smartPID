"""Export router — create, track, and download data exports."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse

from smart_pid_core.adapters.inbound.api.dependencies import require_operator
from smart_pid_domain.dtos.auth import UserClaims  # noqa: TC001
from smart_pid_domain.models.export_models import ExportJob, ExportRequest

router = APIRouter()


def get_export_worker(request: Request):
    """Extract export_worker from app state."""
    worker = getattr(request.app.state, "export_worker", None)
    if worker is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Export worker not available",
        )
    return worker


@router.post("", response_model=ExportJob, status_code=status.HTTP_201_CREATED)
async def create_export(
    body: ExportRequest,
    _user: Annotated[UserClaims, Depends(require_operator)],
    worker=Depends(get_export_worker),
) -> ExportJob:
    """Create a new export job."""
    return worker.create_job(body)


@router.get("/{export_id}", response_model=ExportJob)
async def get_export_status(
    export_id: str,
    _user: Annotated[UserClaims, Depends(require_operator)],
    worker=Depends(get_export_worker),
) -> ExportJob:
    """Get the status of an export job."""
    job = worker.get_job(export_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Export job {export_id} not found",
        )
    return job


@router.get("/{export_id}/download")
async def download_export(
    export_id: str,
    _user: Annotated[UserClaims, Depends(require_operator)],
    worker=Depends(get_export_worker),
) -> FileResponse:
    """Download the completed export file."""
    job = worker.get_job(export_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Export job {export_id} not found",
        )
    if job.status != "done" or job.file_path is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Export not yet complete",
        )
    media = "text/csv" if job.format == "csv" else "application/json"
    return FileResponse(
        path=job.file_path,
        media_type=media,
        filename=f"export_{export_id}.{job.format}",
    )
