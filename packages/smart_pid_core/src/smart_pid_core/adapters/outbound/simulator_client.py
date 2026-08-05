"""SimulatorClient — async RPC client for the standalone digital-twin service.

The twin (``smart_pid_core.simulator_service``, entry point ``smart-pid-sim``)
is a fully independent process: the daemon never runs simulator dynamics
itself and reaches it only over this HTTP surface (plus OPC-UA for
telemetry/control, wired separately via OPCUAAdapter).

Method names mirror ``SimulatorAdapter``'s (the twin's own in-process
implementation) so every daemon call site that used to call the adapter
synchronously now just awaits the same-named client method — the edit is
mechanical, not a redesign.

Error translation: any non-2xx response from the twin is re-raised as
``HTTPException`` with the twin's own status code and detail, so the
daemon's ``/simulator/*`` routes keep answering the web UI with exactly the
codes they always did (404 unknown controller, 409 duplicate loop id/bad
preset, ...). A transport failure (twin unreachable, timed out) becomes
``HTTPException(502, "Simulator service unavailable")`` — the daemon is up,
the twin is not, which is a gateway failure rather than a bad request.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import httpx
from fastapi import HTTPException

from smart_pid_domain.dtos.simulator import ControllerSimStatus

if TYPE_CHECKING:
    from collections.abc import Iterable

    from smart_pid_domain.dtos.simulator import AutoDisturbanceRequest, AutoSPRequest
    from smart_pid_domain.enums import ProcessPresetName

# Mirrors SIMULATOR_MODE_INT_MAP in the twin's simulator_adapter.py: how the
# twin encodes its Mode node (0=MAN, 1=AUTO). bind_opcua_client needs this to
# point the OPC-UA *client* adapter's mode_int_map at the twin's encoding —
# duplicated rather than imported because the two now live in separate
# processes/packages and this is a wire-format fact, not adapter internals.
SIMULATOR_MODE_INT_MAP: dict[str, int] = {"MAN": 0, "AUTO": 1}


def _extract_detail(resp: httpx.Response) -> str:
    try:
        body = resp.json()
    except ValueError:
        return resp.text or f"Simulator error {resp.status_code}"
    if isinstance(body, dict) and "detail" in body:
        return str(body["detail"])
    return str(body)


class SimulatorClient:
    """Async httpx wrapper over the twin's REST control surface."""

    def __init__(
        self,
        base_url: str,
        timeout: float = 5.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout, transport=transport)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _request(self, method: str, path: str, **kwargs: object) -> httpx.Response:
        try:
            resp = await self._client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=502, detail="Simulator service unavailable",
            ) from exc
        if resp.status_code >= 400:
            raise HTTPException(status_code=resp.status_code, detail=_extract_detail(resp))
        return resp

    async def health(self) -> bool:
        """Best-effort twin liveness probe. Never raises — a failed transport
        or non-200 status both come back ``False`` so a boot readiness loop
        can retry without unwrapping a network exception each iteration."""
        try:
            resp = await self._client.get("/health")
        except httpx.HTTPError:
            return False
        return resp.status_code == 200

    # ----- lifecycle ---------------------------------------------------

    async def start(self) -> None:
        await self._request("POST", "/start")

    async def stop(self) -> None:
        await self._request("POST", "/stop")

    async def is_running(self) -> bool:
        resp = await self._request("GET", "/status")
        return bool(resp.json()["running"])

    async def get_status(self) -> dict[int, ControllerSimStatus]:
        resp = await self._request("GET", "/status")
        controllers = resp.json()["controllers"]
        return {int(cid): ControllerSimStatus(**payload) for cid, payload in controllers.items()}

    async def get_controller_status(self, controller_id: int) -> ControllerSimStatus:
        """Not a dedicated twin route — the twin's status payload already
        carries every controller, so this just narrows ``get_status()`` to
        one. Raises the same 404 shape a per-controller route would."""
        statuses = await self.get_status()
        try:
            return statuses[controller_id]
        except KeyError as exc:
            raise HTTPException(
                status_code=404,
                detail=f"Controller {controller_id} is not registered in the simulator",
            ) from exc

    # ----- controller lifecycle -----------------------------------------

    async def register_controller(
        self, controller_id: int, pv_min: float = 0.0, pv_max: float = 100.0,
    ) -> None:
        await self._request(
            "POST", "/controllers",
            json={"controller_id": controller_id, "pv_min": pv_min, "pv_max": pv_max},
        )

    async def unregister_controller(self, controller_id: int) -> bool:
        resp = await self._request("DELETE", f"/controllers/{controller_id}")
        return bool(resp.json().get("removed", False))

    async def create_loop(
        self,
        controller_id: int | None = None,
        pv_min: float = 0.0,
        pv_max: float = 100.0,
    ) -> int:
        resp = await self._request(
            "POST", "/loops",
            json={"controller_id": controller_id, "pv_min": pv_min, "pv_max": pv_max},
        )
        return int(resp.json()["controller_id"])

    async def controller_ids(self) -> list[int]:
        resp = await self._request("GET", "/controllers")
        return [int(cid) for cid in resp.json()["controller_ids"]]

    async def has_controller(self, controller_id: int) -> bool:
        return controller_id in await self.controller_ids()

    # ----- OPC-UA server lifecycle ---------------------------------------

    async def opcua_running(self) -> bool:
        resp = await self._request("GET", "/opcua")
        return bool(resp.json()["running"])

    async def opcua_port(self) -> int:
        resp = await self._request("GET", "/opcua")
        return int(resp.json()["port"])

    async def opcua_endpoint(self) -> str:
        resp = await self._request("GET", "/opcua")
        return str(resp.json()["endpoint"])

    async def start_opcua(self) -> None:
        await self._request("POST", "/opcua/start")

    async def stop_opcua(self) -> None:
        await self._request("POST", "/opcua/stop")

    async def opcua_node_ids(self, controller_id: int) -> dict[str, str]:
        """``{}`` for a controller the twin has never heard of — same
        "never registered here" contract as the in-process adapter had."""
        try:
            resp = await self._request("GET", f"/node-ids/{controller_id}")
        except HTTPException as exc:
            if exc.status_code == 404:
                return {}
            raise
        return dict(resp.json())

    # ----- process model / disturbances -----------------------------------

    async def set_preset(self, controller_id: int, preset: ProcessPresetName) -> None:
        await self._request(
            "POST", "/preset",
            json={"controller_id": controller_id, "preset": preset},
        )

    async def set_parameters(
        self,
        controller_id: int,
        gain: float,
        tau1: float,
        tau2: float | None,
        dead_time: float,
    ) -> None:
        await self._request(
            "PUT", "/parameters",
            json={
                "controller_id": controller_id, "gain": gain, "tau1": tau1,
                "tau2": tau2, "dead_time": dead_time,
            },
        )

    async def inject_step(self, controller_id: int, amplitude: float) -> None:
        await self._request(
            "POST", "/disturbance",
            json={"controller_id": controller_id, "type": "step", "amplitude": amplitude},
        )

    async def inject_noise(self, controller_id: int, amplitude: float) -> None:
        await self._request(
            "POST", "/disturbance",
            json={"controller_id": controller_id, "type": "noise", "amplitude": amplitude},
        )

    async def clear_disturbance(self, controller_id: int) -> None:
        await self._request("DELETE", f"/disturbance/{controller_id}")

    # ----- PID --------------------------------------------------------

    async def set_pid_params(self, controller_id: int, kp: float, ti: float, td: float) -> None:
        await self._request(
            "POST", "/pid/params",
            json={"controller_id": controller_id, "kp": kp, "ti": ti, "td": td},
        )

    async def set_pid_sp(self, controller_id: int, sp: float) -> None:
        await self._request(
            "POST", "/pid/sp", json={"controller_id": controller_id, "sp": sp},
        )

    async def set_pid_mode(self, controller_id: int, mode: int) -> None:
        await self._request(
            "POST", "/pid/mode", json={"controller_id": controller_id, "mode": mode},
        )

    async def write_output(self, controller_id: int, co: float) -> None:
        await self._request(
            "POST", "/pid/output", json={"controller_id": controller_id, "co": co},
        )

    async def get_pid_status(self, controller_id: int) -> dict:
        resp = await self._request("GET", f"/pid/status/{controller_id}")
        return resp.json()

    # ----- auto-excitation ----------------------------------------------

    async def set_auto_sp(self, controller_id: int, req: AutoSPRequest) -> None:
        await self._request(
            "POST", f"/auto-sp/{controller_id}", json=req.model_dump(mode="json"),
        )

    async def set_auto_disturbance(self, controller_id: int, req: AutoDisturbanceRequest) -> None:
        await self._request(
            "POST", f"/auto-disturbance/{controller_id}", json=req.model_dump(mode="json"),
        )

    # ----- persisted config ------------------------------------------

    async def load_sim_config(self, cfg: dict) -> None:
        await self._request("POST", "/load-config", json={"cfg": cfg})

    async def get_config_dict(self, controller_id: int) -> dict:
        resp = await self._request("GET", f"/config/{controller_id}")
        return resp.json()

    async def consume_dirty_cids(self) -> list[int]:
        resp = await self._request("POST", "/consume-dirty")
        return [int(cid) for cid in resp.json()["controller_ids"]]


async def bind_opcua_client(
    opcua_adapter: object,
    simulator_client: SimulatorClient,
    controller_ids: Iterable[int],
) -> list[int]:
    """Point the OPC-UA *client* adapter at the twin's nodes for these ids.

    Async, twin-over-the-wire counterpart of the daemon's old in-process
    binder: in simulator mode the twin owns the address space, so a
    controller's ``tag_bindings`` are empty and the client adapter has to be
    registered against the node ids the twin minted. Called from daemon
    boot, ``POST /controllers`` and project switch so the three cannot drift.

    Returns the ids that were bound (ones the twin does not know are
    skipped).
    """
    bound: list[int] = []
    for cid in controller_ids:
        nodes = await simulator_client.opcua_node_ids(cid)
        if not nodes:
            continue
        mode_node = nodes.get("mode", "")
        opcua_adapter.register_controller(  # type: ignore[attr-defined]
            controller_id=cid,
            node_id_pv=nodes.get("pv", ""),
            node_id_sp=nodes.get("sp", ""),
            node_id_co=nodes.get("co", ""),
            node_id_kp=nodes.get("kp", ""),
            node_id_ti=nodes.get("ti", ""),
            node_id_td=nodes.get("td", ""),
            node_id_mode_target=mode_node,
            node_id_mode_actual=mode_node,
            mode_int_map=dict(SIMULATOR_MODE_INT_MAP),
        )
        bound.append(cid)
    return bound
