"""Per-controller PID tuning and tag-binding configuration DTOs."""
from __future__ import annotations

from pydantic import BaseModel

from smart_pid_domain.dtos.controllers import PIDParamsDTO, TagBindingsDTO


class PIDTuningUpdate(BaseModel):
    """Partial update for PID tuning parameters."""

    gain: float | None = None
    reset: float | None = None
    rate: float | None = None
    alpha: float | None = None
    deadband: float | None = None


class PIDTuningResponse(BaseModel):
    """Current PID tuning parameters for a controller."""

    controller_id: int
    pid_params: PIDParamsDTO = PIDParamsDTO()


class TagBindingsUpdate(BaseModel):
    """Partial update for OPC-UA tag bindings."""

    node_id_pv: str | None = None
    node_id_sp: str | None = None
    node_id_co: str | None = None
    node_id_integral: str | None = None
    node_id_bkcal_in: str | None = None
    node_id_bkcal_out: str | None = None
    node_id_kp: str | None = None
    node_id_ti: str | None = None
    node_id_td: str | None = None
    node_id_mode: str | None = None


class TagBindingsResponse(BaseModel):
    """Current OPC-UA tag bindings for a controller."""

    controller_id: int
    tag_bindings: TagBindingsDTO = TagBindingsDTO()
