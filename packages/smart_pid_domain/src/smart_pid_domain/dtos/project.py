"""Project management DTOs."""
from __future__ import annotations

from pydantic import BaseModel


class ProjectCreate(BaseModel):
    """Request to create a new project file."""

    name: str
    path: str


class ProjectOpen(BaseModel):
    """Request to open an existing project file."""

    path: str


class ProjectSaveAs(BaseModel):
    """Request to save project to a new path."""

    path: str


class ProjectResponse(BaseModel):
    """Project metadata response."""

    name: str
    path: str
    controller_count: int = 0
