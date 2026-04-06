"""Project management REST API routes."""
from __future__ import annotations

from fastapi import APIRouter, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse

from smart_pid_domain.dtos.project import (
    ProjectCreate,
    ProjectListResponse,
    ProjectOpen,
    ProjectResponse,
)

router = APIRouter()


@router.get("/current", response_model=ProjectResponse)
async def get_current(request: Request) -> ProjectResponse:
    """Return metadata about the currently-open project."""
    svc = request.app.state.project_service
    return await svc.get_current()


@router.post("/new", response_model=ProjectResponse)
async def new_project(body: ProjectCreate, request: Request) -> ProjectResponse:
    """Create a new project file."""
    svc = request.app.state.project_service
    try:
        return await svc.new_project(body.name)
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/open", response_model=ProjectResponse)
async def open_project(body: ProjectOpen, request: Request) -> ProjectResponse:
    """Open an existing project by name."""
    svc = request.app.state.project_service
    try:
        return await svc.open_project(body.name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc


@router.get("/list", response_model=ProjectListResponse)
async def list_projects(request: Request) -> ProjectListResponse:
    """List all available projects in the backend directory."""
    svc = request.app.state.project_service
    items = await svc.list_projects()
    return ProjectListResponse(projects=items)


@router.post("/import", response_model=ProjectResponse)
async def import_project(
    request: Request,
    file: UploadFile,
    name: str = Form(default=""),
) -> ProjectResponse:
    """Upload a .spid file to the backend projects directory."""
    svc = request.app.state.project_service
    proj_name = name.strip() or (file.filename or "imported").removesuffix(".spid")
    data = await file.read()
    try:
        return await svc.import_project(proj_name, data)
    except FileExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc


@router.get("/download")
async def download_project(request: Request) -> FileResponse:
    """Download the active project as a .spid file."""
    svc = request.app.state.project_service
    path = svc.download_path()
    return FileResponse(
        path=str(path),
        filename=path.name,
        media_type="application/octet-stream",
    )


@router.delete("/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(name: str, request: Request) -> None:
    """Delete a project file from the backend directory."""
    svc = request.app.state.project_service
    try:
        await svc.delete_project(name)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
