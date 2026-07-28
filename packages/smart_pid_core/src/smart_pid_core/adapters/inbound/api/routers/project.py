"""Project management REST API routes.

Authorization model (mirrors commands/controllers routers):
- current / list                  -> operator (read)
- new / open / import / download   -> supervisor (changes the active plant config)
- delete                          -> admin (destructive)

Project names are sanitized in ``ProjectService`` to prevent path traversal,
surfaced here as HTTP 400.
"""
from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
from pathlib import Path
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

# The upload is streamed to a staging file a chunk at a time, so this — not the
# archive size — is what an import costs in resident memory.
_UPLOAD_CHUNK = 1 * 1024 * 1024  # 1 MB


async def _stage_upload(
    file: UploadFile,
    staging_dir: Path,
    max_bytes: int,
    min_free_bytes: int,
) -> Path:
    """Stream ``file`` into a staging file beside the projects and return it.

    Staging inside ``staging_dir`` is deliberate: the archive is later moved
    into place with ``os.replace``, which is only atomic within one filesystem.

    Two refusals are enforced as the bytes land, before the archive is even
    looked at — HTTP 413 once the body passes ``max_bytes`` (abuse ceiling) and
    HTTP 507 once accepting the next chunk would leave the volume with less
    than ``min_free_bytes``. A rejected or abandoned upload leaves nothing
    behind; leaking staging files would itself be the disk-fill vector.

    The caller owns the returned path and must unlink it once consumed.
    """
    staging_dir.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=staging_dir, prefix=".import-", suffix=".part"
    )
    staged = Path(tmp_name)
    total = 0
    try:
        with os.fdopen(fd, "wb") as sink:
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
                free = shutil.disk_usage(staging_dir).free
                if free - len(chunk) < min_free_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_507_INSUFFICIENT_STORAGE,
                        detail=(
                            "Not enough free space on the projects volume to "
                            "accept this upload"
                        ),
                    )
                await asyncio.to_thread(sink.write, chunk)
    except BaseException:
        staged.unlink(missing_ok=True)
        raise
    return staged


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
    # Outside the try below: 413/507 must not be caught and remapped to 400.
    staged = await _stage_upload(
        file,
        svc.projects_dir,
        settings.max_upload_bytes,
        settings.min_free_disk_bytes,
    )
    # An explicit ``name`` wins; the filename is only a fallback, and it comes
    # with the ``.spid`` suffix the caller would not have asked for.
    fallback = (file.filename or "imported").removesuffix(".spid")
    proj_name = name or fallback or "imported"
    try:
        return await svc.import_project(proj_name, staged)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        # A successful import moved the file away; every other path must not
        # leave the partial archive occupying the projects volume.
        staged.unlink(missing_ok=True)


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
