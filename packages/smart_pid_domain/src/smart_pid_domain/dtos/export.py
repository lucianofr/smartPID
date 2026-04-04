"""Export DTOs — ExportRequest and ExportJob for data export operations."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class ExportRequest(BaseModel):
    """Request to create a data export job."""

    controller_id: int
    start: str
    end: str
    format: Literal["csv", "json"] = "csv"


class ExportJob(BaseModel):
    """Tracks the state of an export job."""

    id: str
    controller_id: int
    start: str
    end: str
    format: Literal["csv", "json"]
    status: Literal["pending", "running", "done", "error"] = "pending"
    progress: int = 0
    file_path: str | None = None
