"""Foundation Fieldbus signal value objects.

Every process signal (PV, SP, CO, BKCAL_IN, BKCAL_OUT) carries value, quality
status, and timestamp as a single unit — matching OPC-UA DataValue semantics.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from smart_pid_domain.enums import InitSubStatus, LimitBits, SignalSeverity

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(frozen=True)
class FFSignalStatus:
    """Composite status matching OPC-UA StatusCode semantics."""

    severity: SignalSeverity = SignalSeverity.GOOD
    limit_bits: LimitBits = LimitBits.NONE
    sub_status: InitSubStatus = InitSubStatus.NONE

    @property
    def is_good(self) -> bool:
        return self.severity == SignalSeverity.GOOD

    @property
    def is_bad(self) -> bool:
        return self.severity == SignalSeverity.BAD

    @property
    def is_high_limited(self) -> bool:
        return self.limit_bits == LimitBits.HIGH_LIMITED

    @property
    def is_low_limited(self) -> bool:
        return self.limit_bits == LimitBits.LOW_LIMITED

    @property
    def is_constant(self) -> bool:
        return self.limit_bits == LimitBits.CONSTANT

    @property
    def is_not_invited(self) -> bool:
        return self.sub_status == InitSubStatus.NI

    @property
    def is_init_request(self) -> bool:
        return self.sub_status == InitSubStatus.IR

    @property
    def is_init_acknowledge(self) -> bool:
        return self.sub_status == InitSubStatus.IA

    @property
    def is_good_cascade(self) -> bool:
        return self.sub_status == InitSubStatus.GOOD_CASCADE


@dataclass(frozen=True)
class FFSignal:
    """A process signal with value, quality status, and timestamp.

    Mirrors the OPC-UA DataValue structure and Foundation Fieldbus signal
    semantics. Every signal in the PID engine (PV, SP, CO, BKCAL_IN,
    BKCAL_OUT) uses this type.
    """

    value: float
    status: FFSignalStatus = field(default_factory=FFSignalStatus)
    timestamp: datetime | None = None

    @staticmethod
    def good(value: float, ts: datetime | None = None) -> FFSignal:
        """Create a signal with GOOD status."""
        return FFSignal(value=value, status=FFSignalStatus(), timestamp=ts)

    @staticmethod
    def bad(value: float = 0.0, ts: datetime | None = None) -> FFSignal:
        """Create a signal with BAD status."""
        return FFSignal(
            value=value,
            status=FFSignalStatus(severity=SignalSeverity.BAD),
            timestamp=ts,
        )

    @staticmethod
    def with_limits(
        value: float, limit_bits: LimitBits, ts: datetime | None = None,
    ) -> FFSignal:
        """Create a GOOD signal with specific limit bits."""
        return FFSignal(
            value=value,
            status=FFSignalStatus(limit_bits=limit_bits),
            timestamp=ts,
        )
