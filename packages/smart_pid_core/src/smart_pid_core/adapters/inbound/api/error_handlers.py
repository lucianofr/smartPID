"""Global exception handlers mapping domain exceptions to HTTP status codes."""
from __future__ import annotations

from math import isfinite

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from smart_pid_domain.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ControllerNotFoundError,
    DomainError,
)


def _json_renderable(value: object) -> object:
    """Return *value* with every non-finite float replaced by its name.

    A validation error echoes the rejected input back to the client, and
    ``JSONResponse`` renders with ``allow_nan=False``. So the DTOs that refuse
    NaN/inf (``FiniteFloat``) produced a correct 422 whose *body* then failed
    to serialise — ``ValueError: Out of range float values are not JSON
    compliant`` — turning every non-finite command into a 500. Stringifying
    the echo keeps the error legible and the response renderable.
    """
    if isinstance(value, float):
        return value if isfinite(value) else str(value)
    if isinstance(value, dict):
        return {k: _json_renderable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_renderable(v) for v in value]
    return value


def register_error_handlers(app: FastAPI) -> None:
    """Register global exception handlers on the FastAPI app."""

    @app.exception_handler(RequestValidationError)
    async def _validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Same shape as FastAPI's default handler, minus the unrenderable floats.
        return JSONResponse(
            status_code=422,
            content={"detail": _json_renderable(jsonable_encoder(exc.errors()))},
        )

    @app.exception_handler(ControllerNotFoundError)
    async def _controller_not_found(
        request: Request, exc: ControllerNotFoundError
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(DomainError)
    async def _domain_error(request: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(AuthenticationError)
    async def _auth_error(request: Request, exc: AuthenticationError) -> JSONResponse:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    @app.exception_handler(AuthorizationError)
    async def _authz_error(request: Request, exc: AuthorizationError) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": str(exc)})
