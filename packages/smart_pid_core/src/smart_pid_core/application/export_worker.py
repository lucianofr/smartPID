"""ExportWorker — creates and runs CSV/JSON export jobs from historian data."""
from __future__ import annotations

import csv
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from smart_pid_domain.models.export_models import ExportJob, ExportRequest

if TYPE_CHECKING:
    from smart_pid_core.domain.ports.outbound import HistorianWriter


class ExportWorker:
    """Manages export jobs: creation, tracking, and execution."""

    def __init__(self, historian: HistorianWriter, export_dir: str) -> None:
        self._historian = historian
        self._export_dir = Path(export_dir)
        self._export_dir.mkdir(parents=True, exist_ok=True)
        self._jobs: dict[str, ExportJob] = {}

    def create_job(self, request: ExportRequest) -> ExportJob:
        """Create a new pending export job and schedule its execution."""
        job = ExportJob(
            id=str(uuid.uuid4()),
            controller_id=request.controller_id,
            start=request.start,
            end=request.end,
            format=request.format,
        )
        self._jobs[job.id] = job
        # Schedule the export to run in the background
        import asyncio

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.run_export(job))
        except RuntimeError:
            # No running event loop — run synchronously in a new loop
            asyncio.run(self.run_export(job))
        return job

    def get_job(self, export_id: str) -> ExportJob | None:
        """Retrieve a job by ID, or None if not found."""
        return self._jobs.get(export_id)

    async def run_export(self, job: ExportJob) -> None:
        """Execute the export: query historian, write file, update job status."""
        # Update status to running
        job = job.model_copy(update={"status": "running", "progress": 10})
        self._jobs[job.id] = job

        try:
            start_dt = datetime.fromisoformat(job.start)
            end_dt = datetime.fromisoformat(job.end)

            frames = await self._historian.query(job.controller_id, start_dt, end_dt)

            job = job.model_copy(update={"progress": 50})
            self._jobs[job.id] = job

            ext = "csv" if job.format == "csv" else "json"
            file_path = self._export_dir / f"export_{job.id}.{ext}"

            if job.format == "csv":
                self._write_csv(file_path, frames)
            else:
                self._write_json(file_path, frames)

            job = job.model_copy(
                update={
                    "status": "done",
                    "progress": 100,
                    "file_path": str(file_path),
                },
            )
        except Exception:
            job = job.model_copy(update={"status": "error", "progress": 0})

        self._jobs[job.id] = job

    @staticmethod
    def _write_csv(path: Path, frames: list) -> None:
        """Write telemetry frames as CSV."""
        with path.open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "controller_id", "pv", "sp", "co", "integral_val"])
            for fr in frames:
                writer.writerow([
                    fr.timestamp.isoformat(),
                    fr.controller_id,
                    fr.pv.value,
                    fr.sp.value,
                    fr.co.value,
                    fr.integral_val,
                ])

    @staticmethod
    def _write_json(path: Path, frames: list) -> None:
        """Write telemetry frames as JSON."""
        data = [
            {
                "timestamp": fr.timestamp.isoformat(),
                "controller_id": fr.controller_id,
                "pv": fr.pv.value,
                "sp": fr.sp.value,
                "co": fr.co.value,
                "integral_val": fr.integral_val,
            }
            for fr in frames
        ]
        path.write_text(json.dumps(data, indent=2))
