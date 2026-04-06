"""Tests for project DTOs."""
from smart_pid_domain.dtos.project import (
    ProjectCreate,
    ProjectListItem,
    ProjectListResponse,
    ProjectOpen,
    ProjectResponse,
)


def test_project_create_has_name_only():
    dto = ProjectCreate(name="elkem")
    assert dto.name == "elkem"
    assert not hasattr(dto, "path") or "path" not in dto.model_fields


def test_project_open_has_name():
    dto = ProjectOpen(name="elkem")
    assert dto.name == "elkem"


def test_project_list_item():
    item = ProjectListItem(name="elkem", controller_count=3, size_bytes=73728)
    assert item.name == "elkem"
    assert item.controller_count == 3
    assert item.size_bytes == 73728


def test_project_list_item_defaults():
    item = ProjectListItem(name="test")
    assert item.controller_count == 0
    assert item.size_bytes == 0


def test_project_list_response():
    resp = ProjectListResponse(
        projects=[
            ProjectListItem(name="a", controller_count=1, size_bytes=100),
            ProjectListItem(name="b"),
        ]
    )
    assert len(resp.projects) == 2
    assert resp.projects[0].name == "a"


def test_project_response():
    resp = ProjectResponse(name="elkem", path="elkem.spid", controller_count=3)
    assert resp.name == "elkem"
    assert resp.path == "elkem.spid"
