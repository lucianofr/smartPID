"""Project management DTOs."""
from __future__ import annotations

import re

from pydantic import BaseModel, field_validator

#: Project names become filesystem paths, so they are restricted to a safe,
#: portable character set: no separators, no traversal, no NUL bytes. Defined
#: here — the one place both the API boundary and ``ProjectService`` can reach
#: without breaking the hexagonal rule — so the rule has a single definition.
MAX_PROJECT_NAME_LEN = 128
PROJECT_NAME_CHARSET = r"[A-Za-z0-9._\- ]"
PROJECT_NAME_PATTERN = rf"^{PROJECT_NAME_CHARSET}{{1,{MAX_PROJECT_NAME_LEN}}}$"
_PROJECT_NAME_RE = re.compile(PROJECT_NAME_PATTERN)


def validate_project_name(name: str) -> str:
    """Return *name* unchanged, or raise ``ValueError`` if it is not a safe
    project name.

    The charset alone is not the whole rule: ``.`` and ``..`` are built from
    legal characters but name directories, and an all-blank name is legal by
    charset yet unusable. Both layers that gate a project name — the request
    DTOs below and ``ProjectService._safe_project_path`` — call this, so the
    boundary can never end up laxer than the path builder behind it.
    """
    if not isinstance(name, str) or not _PROJECT_NAME_RE.fullmatch(name):
        raise ValueError(f"Invalid project name: {name!r}")
    if name in {".", ".."} or not name.strip():
        raise ValueError(f"Invalid project name: {name!r}")
    return name


class _ProjectNamed(BaseModel):
    """Shared name validation for the project request bodies."""

    name: str

    @field_validator("name")
    @classmethod
    def _check_name(cls, value: str) -> str:
        return validate_project_name(value)


class ProjectCreate(_ProjectNamed):
    """Request to create a new project."""


class ProjectOpen(_ProjectNamed):
    """Request to open a project by name."""


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
