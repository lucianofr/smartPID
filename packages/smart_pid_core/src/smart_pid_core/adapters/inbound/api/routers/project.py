"""Project management REST API routes."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from smart_pid_domain.dtos.project import (
    ProjectCreate,
    ProjectOpen,
    ProjectResponse,
    ProjectSaveAs,
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
    dest = Path(body.path)
    if dest.exists():
        raise HTTPException(status_code=409, detail="File already exists")
    svc = request.app.state.project_service
    return await svc.new_project(body.name, dest)


@router.post("/open", response_model=ProjectResponse)
async def open_project(body: ProjectOpen, request: Request) -> ProjectResponse:
    """Open an existing project file."""
    svc = request.app.state.project_service
    try:
        return await svc.open_project(Path(body.path))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project file not found") from exc


@router.post("/save-as", response_model=ProjectResponse)
async def save_as(body: ProjectSaveAs, request: Request) -> ProjectResponse:
    """Save current project to a new path."""
    svc = request.app.state.project_service
    return await svc.save_as(Path(body.path))
