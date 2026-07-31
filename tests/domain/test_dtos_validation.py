"""Input bounds at the API boundary.

These are the trust-boundary checks: names that become filesystem paths or
OPC-UA node names, ids that index a loop table, and numeric command values
that reach the velocity-form PID engine.
"""
from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from smart_pid_domain.dtos.commands import (
    ModeCommand,
    OptimizationCommand,
    OutputCommand,
    SetpointCommand,
    TuningCommand,
)
from smart_pid_domain.dtos.controllers import (
    MAX_CONTROLLER_NAME_LEN,
    ControllerCreate,
    ControllerUpdate,
)
from smart_pid_domain.dtos.project import (
    MAX_PROJECT_NAME_LEN,
    ProjectCreate,
    ProjectOpen,
)

_ID_COMMANDS = (SetpointCommand, OutputCommand)


class TestControllerName:
    def test_accepts_a_normal_tag(self) -> None:
        assert ControllerCreate(name="TIC-101").name == "TIC-101"

    def test_rejects_empty(self) -> None:
        with pytest.raises(ValidationError):
            ControllerCreate(name="")

    def test_rejects_over_length(self) -> None:
        with pytest.raises(ValidationError):
            ControllerCreate(name="A" * (MAX_CONTROLLER_NAME_LEN + 1))

    def test_accepts_exactly_max_length(self) -> None:
        name = "A" * MAX_CONTROLLER_NAME_LEN
        assert ControllerCreate(name=name).name == name

    def test_update_still_allows_omitting_the_name(self) -> None:
        assert ControllerUpdate().name is None

    def test_update_rejects_empty_name(self) -> None:
        with pytest.raises(ValidationError):
            ControllerUpdate(name="")


class TestProjectName:
    @pytest.mark.parametrize("model", [ProjectCreate, ProjectOpen])
    def test_accepts_a_portable_name(self, model: type) -> None:
        assert model(name="planta 1_v2.0-final").name == "planta 1_v2.0-final"

    @pytest.mark.parametrize("model", [ProjectCreate, ProjectOpen])
    @pytest.mark.parametrize(
        "bad",
        [
            "../../etc/evil",   # traversal
            "a/b",              # separator
            "a\\b",             # windows separator
            "nul\x00byte",      # NUL
            "",                 # empty
            ".",                # current dir
            "..",               # parent dir
            "acentuação",       # outside the portable charset
        ],
    )
    def test_rejects_unsafe_names(self, model: type, bad: str) -> None:
        with pytest.raises(ValidationError):
            model(name=bad)

    @pytest.mark.parametrize("model", [ProjectCreate, ProjectOpen])
    def test_rejects_over_length(self, model: type) -> None:
        with pytest.raises(ValidationError):
            model(name="A" * (MAX_PROJECT_NAME_LEN + 1))

    @pytest.mark.parametrize(
        "bad",
        ["../../etc/evil", "a/b", "a\\b", "", ".", "..", "   ", "acentuação"],
    )
    def test_boundary_and_path_builder_reject_the_same_names(
        self, bad: str, tmp_path,
    ) -> None:
        """The DTO must never be laxer than the path builder behind it.

        Exercises the real ``ProjectService._safe_project_path`` rather than
        the shared helper, so the assertion still holds if the service ever
        stops delegating to it.
        """
        from smart_pid_core.application.project_service import ProjectService

        svc = ProjectService(repo=None, loop_manager=None, projects_dir=tmp_path)  # type: ignore[arg-type]
        with pytest.raises(ValidationError):
            ProjectCreate(name=bad)
        with pytest.raises(ValueError):
            svc._safe_project_path(bad)

    def test_both_layers_accept_the_same_legal_names(self, tmp_path) -> None:
        from smart_pid_core.application.project_service import ProjectService

        svc = ProjectService(repo=None, loop_manager=None, projects_dir=tmp_path)  # type: ignore[arg-type]
        for name in ("ok name", "a.b-c_1", "A" * MAX_PROJECT_NAME_LEN):
            assert ProjectCreate(name=name).name == name
            assert svc._safe_project_path(name).parent == tmp_path.resolve()


class TestCommandControllerId:
    @pytest.mark.parametrize("model", _ID_COMMANDS)
    @pytest.mark.parametrize("bad_id", [0, -1])
    def test_rejects_non_positive_id(self, model: type, bad_id: int) -> None:
        with pytest.raises(ValidationError):
            model(controller_id=bad_id, value=10.0)

    def test_rejects_non_positive_id_on_mode(self) -> None:
        with pytest.raises(ValidationError):
            ModeCommand(controller_id=0, mode="AUTO")

    def test_rejects_non_positive_id_on_optimization(self) -> None:
        with pytest.raises(ValidationError):
            OptimizationCommand(controller_id=0, enabled=True)

    def test_rejects_non_positive_id_on_tuning(self) -> None:
        with pytest.raises(ValidationError):
            TuningCommand(controller_id=0, kp=1.0)

    @pytest.mark.parametrize("model", _ID_COMMANDS)
    def test_accepts_the_first_real_id(self, model: type) -> None:
        assert model(controller_id=1, value=0.0).controller_id == 1


class TestCommandValueFiniteness:
    """Engineering-unit ranges stay per-controller; only non-finite is refused."""

    @pytest.mark.parametrize("model", _ID_COMMANDS)
    @pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
    def test_rejects_non_finite(self, model: type, bad: float) -> None:
        with pytest.raises(ValidationError):
            model(controller_id=1, value=bad)

    @pytest.mark.parametrize("model", _ID_COMMANDS)
    @pytest.mark.parametrize("good", [-273.15, 0.0, 1500.0, 1e9])
    def test_accepts_any_finite_engineering_value(
        self, model: type, good: float,
    ) -> None:
        """A furnace SP of 1500 and a cryogenic -273.15 are both legitimate:
        the DTO must not impose a 0-100 range."""
        assert model(controller_id=1, value=good).value == good


class TestTuningCommandBounds:
    @pytest.mark.parametrize("field", ["kp", "ti", "td"])
    def test_rejects_non_finite(self, field: str) -> None:
        with pytest.raises(ValidationError):
            TuningCommand(controller_id=1, **{field: math.nan})

    @pytest.mark.parametrize("field", ["ti", "td"])
    def test_rejects_negative_times(self, field: str) -> None:
        with pytest.raises(ValidationError):
            TuningCommand(controller_id=1, **{field: -1.0})

    @pytest.mark.parametrize("field", ["ti", "td"])
    def test_allows_zero_meaning_term_disabled(self, field: str) -> None:
        cmd = TuningCommand(controller_id=1, **{field: 0.0})
        assert getattr(cmd, field) == 0.0

    def test_allows_negative_gain(self) -> None:
        """Sign of the gain is a legitimate configuration; only NaN/inf is not."""
        assert TuningCommand(controller_id=1, kp=-2.0).kp == -2.0

    def test_all_fields_remain_optional(self) -> None:
        cmd = TuningCommand(controller_id=1)
        assert (cmd.kp, cmd.ti, cmd.td) == (None, None, None)
