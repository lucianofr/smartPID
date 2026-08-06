"""Tests for Phase 2 DTOs."""
from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from smart_pid_domain.dtos.auth import LoginRequest, TokenResponse, UserClaims, UserCreate
from smart_pid_domain.dtos.commands import (
    CommandResponse,
    ModeCommand,
    OutputCommand,
    SetpointCommand,
)
from smart_pid_domain.dtos.controllers import (
    ControllerCreate,
    ControllerResponse,
    ControllerUpdate,
)
from smart_pid_domain.dtos.history import HistoryResponse, TelemetryFrameDTO
from smart_pid_domain.dtos.system import SystemStatusResponse
from smart_pid_domain.enums import ControllerMode, UserRole


class TestAuthDTOs:
    def test_login_request(self) -> None:
        req = LoginRequest(username="admin", password="secret")
        assert req.username == "admin"
        assert req.password == "secret"

    def test_token_response_default(self) -> None:
        resp = TokenResponse(access_token="tok123")
        assert resp.token_type == "bearer"

    def test_user_create_default_role(self) -> None:
        u = UserCreate(username="bob", password="pass")
        assert u.role == UserRole.USER

    def test_user_claims(self) -> None:
        c = UserClaims(user_id=1, username="admin", role="admin")
        assert c.user_id == 1
        assert c.role == UserRole.ADMIN

    def test_user_claims_rejects_legacy_role(self) -> None:
        with pytest.raises(ValidationError):
            UserClaims(user_id=1, username="admin", role="ADMIN")


class TestCommandDTOs:
    def test_setpoint_command(self) -> None:
        cmd = SetpointCommand(controller_id=1, value=55.0)
        assert cmd.controller_id == 1
        assert cmd.value == 55.0

    def test_mode_command(self) -> None:
        cmd = ModeCommand(controller_id=1, mode=ControllerMode.AUTO)
        assert cmd.mode == ControllerMode.AUTO

    def test_output_command(self) -> None:
        cmd = OutputCommand(controller_id=1, value=75.0)
        assert cmd.value == 75.0

    def test_command_response(self) -> None:
        resp = CommandResponse(ok=True, controller_id=1, detail="SP set to 55.0")
        assert resp.ok is True


class TestControllerDTOs:
    def test_controller_create_defaults(self) -> None:
        c = ControllerCreate(name="TIC-101")
        assert c.description == ""
        assert c.scan_rate_s == 1.0

    def test_controller_update_all_optional(self) -> None:
        u = ControllerUpdate()
        assert u.name is None
        assert u.description is None

    def test_controller_response(self) -> None:
        r = ControllerResponse(
            id=1, name="TIC-101", description="Temp", mode="AUTO",
            pv=50.0, sp=50.0, co=25.0,
        )
        assert r.id == 1


class TestHistoryDTOs:
    def test_telemetry_frame_dto(self) -> None:
        now = datetime.now(tz=UTC)
        f = TelemetryFrameDTO(
            timestamp=now, pv=50.0, sp=50.0, co=25.0, mode="AUTO", status="GOOD",
        )
        assert f.pv == 50.0

    def test_history_response(self) -> None:
        r = HistoryResponse(controller_id=1, frames=[], count=0)
        assert r.count == 0


class TestSystemDTOs:
    def test_system_status(self) -> None:
        s = SystemStatusResponse(
            status="running", uptime_s=123.4, active_controllers=2,
            bus_active=True, api_version="2.0.0",
        )
        assert s.status == "running"
