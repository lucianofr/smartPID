"""Command DTOs for setpoint, mode, and output changes."""
from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field

from smart_pid_domain.enums import ControllerMode

#: Controller ids are SQLite AUTOINCREMENT primary keys, so 0 and negatives can
#: never name a real loop; rejecting them here turns an off-by-one or an
#: uninitialised client field into a 422 instead of a 404 chased through logs.
ControllerId = Annotated[int, Field(gt=0)]

#: Setpoints and outputs are engineering-unit values whose valid span is
#: per-controller (a furnace SP of 1500 and a vacuum SP of -0.9 are both
#: legitimate), so no numeric range belongs in a shared DTO — the range check
#: stays in LoopManager against that loop's own sp/out limits. What is never
#: valid in any unit is a non-finite value: NaN or inf reaching the
#: velocity-form engine poisons the integral irrecoverably, and NaN compares
#: false against every limit, so it slips straight through that per-loop clamp.
FiniteFloat = Annotated[float, Field(allow_inf_nan=False)]

#: Reset (Ti) and rate (Td) are times in seconds: negative is meaningless and a
#: negative reset flips the sign of the integral term. Zero stays legal —
#: PIDEngine reads it as "term disabled".
FiniteTime = Annotated[float, Field(ge=0.0, allow_inf_nan=False)]


class SetpointCommand(BaseModel):
    controller_id: ControllerId
    value: FiniteFloat


class ModeCommand(BaseModel):
    controller_id: ControllerId
    mode: ControllerMode


class OutputCommand(BaseModel):
    controller_id: ControllerId
    value: FiniteFloat


class TuningCommand(BaseModel):
    """Direct PID tuning write. A SUPERVISORY loop receives it on the DCS
    block over OPC-UA; a DDC loop persists it into ``pid_params``. Only the
    supplied fields are written; ``kp`` below ``KP_MIN`` is refused with 422
    (ADR 0001)."""

    controller_id: ControllerId
    kp: FiniteFloat | None = None
    ti: FiniteTime | None = None
    td: FiniteTime | None = None


class OptimizationCommand(BaseModel):
    """Enable/disable the online tuning optimizer (ENABLE_OPTIMIZER) for a loop."""

    controller_id: ControllerId
    enabled: bool


class CommandResponse(BaseModel):
    ok: bool
    controller_id: int | None = None
    detail: str | None = None
    # Present on optimization toggle responses; reports the resulting state.
    enabled: bool | None = None
