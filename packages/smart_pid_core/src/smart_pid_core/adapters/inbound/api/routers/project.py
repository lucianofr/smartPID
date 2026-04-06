"""Project management REST API routes."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from smart_pid_domain.dtos.project import (
    ProjectCreate,
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
