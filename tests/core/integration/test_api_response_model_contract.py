"""Contract test: web dashboard (Fatia 0+1) routes declare response_model.

The React dashboard consumes a generated OpenAPI surface for four endpoints.
For the generated TypeScript types to be accurate, each route must declare an
explicit `response_model` so its 200 response references the matching schema.

This test mounts only the routers under test on a bare FastAPI app (no DB/ZMQ
required) and inspects the generated OpenAPI document. It fails if any of the
four consumed endpoints stops referencing its expected response model.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI

from smart_pid_core.adapters.inbound.api.routers import auth, controllers, opcua


def _build_openapi() -> dict:
    """Mount only the audited routers and return the OpenAPI document.

    Mounting in isolation keeps the test scoped to the route metadata
    (response_model) without constructing the full app dependency graph.
    """
    app = FastAPI()
    app.include_router(auth.router, prefix="/auth", tags=["auth"])
    app.include_router(controllers.router, prefix="/controllers", tags=["controllers"])
    app.include_router(opcua.router, prefix="/opcua", tags=["opcua"])
    return app.openapi()


def _ref_name(schema: dict) -> str | None:
    """Resolve the component name a 200 JSON schema points at.

    Handles both a direct object ($ref) and an array of objects (items.$ref),
    so `list[ControllerResponse]` and `ControllerResponse` both resolve.
    """
    if "$ref" in schema:
        return schema["$ref"].rsplit("/", 1)[-1]
    if schema.get("type") == "array":
        items = schema.get("items", {})
        if "$ref" in items:
            return items["$ref"].rsplit("/", 1)[-1]
    return None


def _ok_schema(openapi: dict, path: str, method: str) -> dict:
    operation = openapi["paths"][path][method]
    return operation["responses"]["200"]["content"]["application/json"]["schema"]


# (path, method, expected component name referenced by the 200 response)
_CONTRACT = [
    ("/auth/login", "post", "TokenResponse"),
    ("/controllers", "get", "ControllerResponse"),
    ("/controllers/{controller_id}", "get", "ControllerResponse"),
    ("/opcua/status", "get", "OPCUAStatusResponse"),
]


@pytest.mark.parametrize(("path", "method", "expected"), _CONTRACT)
def test_dashboard_route_references_expected_model(
    path: str, method: str, expected: str
) -> None:
    openapi = _build_openapi()
    schema = _ok_schema(openapi, path, method)
    assert _ref_name(schema) == expected, (
        f"{method.upper()} {path} must reference {expected} in its 200 response"
    )


def test_list_controllers_returns_array_of_controller_response() -> None:
    """GET /controllers is typed as a JSON array (list[ControllerResponse])."""
    openapi = _build_openapi()
    schema = _ok_schema(openapi, "/controllers", "get")
    assert schema.get("type") == "array"
    assert _ref_name(schema) == "ControllerResponse"
