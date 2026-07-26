"""Project management REST API routes.

Authorization model (mirrors commands/controllers routers):
- current / list                  -> operator (read)
- new / open / import / download   -> supervisor (changes the active plant config)
- delete                          -> admin (destructive)

Project names are sanitized in ``ProjectService`` to prevent path traversal,
surfaced here as HTTP 400.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from smart_pid_core.adapters.inbound.api.dependencies import (
    get_settings,
    require_admin,
    require_user,
)
from smart_pid_core.config import CoreSettings  # noqa: TC001
from smart_pid_domain.dtos.auth import UserClaims  # noqa: TC001
from smart_pid_domain.dtos.project import (
    ProjectCreate,
    ProjectListResponse,
    ProjectOpen,
    ProjectResponse,
)

router = APIRouter()

# Read the multipart upload in bounded chunks so an oversized .spid is rejected
# before the whole body is buffered in memory (DoS guard).
_UPLOAD_CHUNK = 1 * 1024 * 1024  # 1 MB


async def _read_upload_limited(file: UploadFile, max_bytes: int) -> bytes:
    """Read an UploadFile, raising HTTP 413 if it exceeds ``max_bytes``."""
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(_UPLOAD_CHUNK)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"Upload exceeds maximum size of {max_bytes} bytes",
            )
        chunks.append(chunk)
    return b"".join(chunks)


@router.get("/current", response_model=ProjectResponse)
async def get_current(
    request: Request,
    user: Annotated[UserClaims, Depends(require_user)],
) -> ProjectResponse:
    """Return metadata about the currently-open project."""
    svc = request.app.state.project_service
    return await svc.get_current()


@router.post("/new", response_model=ProjectResponse)
async def new_project(
    body: ProjectCreate,
    request: Request,
    user: Annotated[UserClaims, Depends(require_admin)],
) -> ProjectResponse:
    """Create a new project file."""
    svc = request.app.state.project_service
    try:
        return await svc.new_project(body.name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/open", response_model=ProjectResponse)
async def open_project(
    body: ProjectOpen,
    request: Request,
    user: Annotated[UserClaims, Depends(require_admin)],
) -> ProjectResponse:
    """Open an existing project by name."""
    svc = request.app.state.project_service
    try:
        return await svc.open_project(body.name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc


@router.get("/list", response_model=ProjectListResponse)
async def list_projects(
    request: Request,
    user: Annotated[UserClaims, Depends(require_admin)],
) -> ProjectListResponse:
    """List all available projects in the backend directory."""
    svc = request.app.state.project_service
    items = await svc.list_projects()
    return ProjectListResponse(projects=items)


@router.post("/import", response_model=ProjectResponse)
async def import_project(
    request: Request,
    file: UploadFile,
    user: Annotated[UserClaims, Depends(require_admin)],
    settings: Annotated[CoreSettings, Depends(get_settings)],
    name: str = Form(default=""),
) -> ProjectResponse:
    """Import a project file (admin-only)."""
    svc = request.app.state.project_service
    # Outside the try below: the 413 must not be caught and remapped to 400.
    data = await _read_upload_limited(file, settings.max_upload_bytes)
    proj_name = name or file.filename or "imported"
    try:
        return await svc.import_project(proj_name, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/download")
async def download_project(
    request: Request,
    user: Annotated[UserClaims, Depends(require_admin)],
) -> FileResponse:
    """Download the active project as a .spid file (WAL checkpointed first)."""
    svc = request.app.state.project_service
    path = await svc.prepare_download()
    return FileResponse(
        path=str(path),
        filename=path.name,
        media_type="application/octet-stream",
    )


@router.delete("/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    name: str,
    request: Request,
    user: Annotated[UserClaims, Depends(require_admin)],
) -> None:
    """Delete a project file from the backend directory."""
    svc = request.app.state.project_service
    try:
        await svc.delete_project(name)
    except ValueError as exc:
        # Sanitization rejects malicious names; active-project guard also
        # raises ValueError. Distinguish so legitimate "active project" stays 409.
        if "active" in str(exc).lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=str(exc)
            ) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
