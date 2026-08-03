"""User management DTOs."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from smart_pid_domain.enums import UserRole  # noqa: TC001


class UserResponse(BaseModel):
    id: int
    username: str
    role: UserRole
    active: bool = True
    created_at: str = ""


class UserUpdate(BaseModel):
    role: UserRole | None = None
    password: str | None = None
    active: bool | None = None


class UserThemeUpdate(BaseModel):
    """The operator's chosen HMI palette.

    Validated against the theme ids the frontend actually ships so a typo,
    or a stale client, cannot park an unrenderable value on the account and
    leave the operator staring at an unstyled page after every login.
    """

    theme: Literal[
        "optimizer",
        "optimizer-dark",
        "recorder",
        "phosphor",
        "isa101",
        "neon",
    ]
