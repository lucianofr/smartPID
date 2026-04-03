"""Controller CRUD DTOs."""
from __future__ import annotations

from pydantic import BaseModel


class ControllerCreate(BaseModel):
    name: str
    description: str = ""
    scan_rate_ms: int = 1000
    gain: float = 1.0
    reset: float = 10.0
    rate: float = 0.0
    sp_hi_lim: float = 100.0
    sp_lo_lim: float = 0.0
    out_hi_lim: float = 100.0
    out_lo_lim: float = 0.0


class ControllerUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    scan_rate_ms: int | None = None
    gain: float | None = None
    reset: float | None = None
    rate: float | None = None
    sp_hi_lim: float | None = None
    sp_lo_lim: float | None = None
    out_hi_lim: float | None = None
    out_lo_lim: float | None = None


class ControllerResponse(BaseModel):
    id: int
    name: str
    description: str
    mode: str
    pv: float
    sp: float
    co: float
    scan_rate_ms: int = 1000
    gain: float = 1.0
    reset: float = 10.0
    rate: float = 0.0
    sp_hi_lim: float = 100.0
    sp_lo_lim: float = 0.0
    out_hi_lim: float = 100.0
    out_lo_lim: float = 0.0
