"""Project management DTOs."""
from __future__ import annotations

from pydantic import BaseModel


class ProjectCreate(BaseModel):
    """Request to create a new project."""

    name: str


class ProjectOpen(BaseModel):
    """Request to open a project by name."""

    name: str


class ProjectListItem(BaseModel):
    """Single project in a list response."""

    name: str
    controller_count: int = 0
    size_bytes: int = 0


class ProjectListResponse(BaseModel):
    """List of available projects."""

    projects: list[ProjectListItem]


class ProjectResponse(BaseModel):
    """Project metadata response."""

    name: str
    path: str
    controller_count: int = 0
