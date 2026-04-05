"""Embedded asyncua.Server for OPC-UA integration testing."""
from __future__ import annotations

import asyncio
import socket
import threading

from asyncua import Server, ua


def get_free_port() -> int:
    """Ask the OS for an ephemeral port that is currently free."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class OPCUATestServer:
    """Lightweight OPC-UA server for testing.

    Creates a namespace with Float nodes (PV, SP, CO) and Int node (Mode)
    for one controller.
    """

    URI = "urn:smartpid:test"

    def __init__(self, port: int = 0) -> None:
        self._port = port if port != 0 else get_free_port()
        self._server: Server | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._stop_event = threading.Event()
        self.node_ids: dict[str, str] = {}

    @property
    def endpoint(self) -> str:
        return f"opc.tcp://localhost:{self._port}"

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="opcua-test-server",
        )
        self._thread.start()
        if not self._ready.wait(timeout=10.0):
            raise RuntimeError("OPC-UA test server failed to start")

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=10.0)
            self._thread = None

    def _run(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._setup_and_serve())
        except Exception:
            pass
        finally:
            self._loop.close()
            self._loop = None

    async def _setup_and_serve(self) -> None:
        self._server = Server()
        await self._server.init()
        self._server.set_endpoint(self.endpoint)
        self._server.set_server_name("SmartPID Test Server")

        idx = await self._server.register_namespace(self.URI)

        objects = self._server.nodes.objects
        ctrl_folder = await objects.add_folder(idx, "Controller1")

        pv_node = await ctrl_folder.add_variable(idx, "PV", 50.0, ua.VariantType.Float)
        sp_node = await ctrl_folder.add_variable(idx, "SP", 50.0, ua.VariantType.Float)
        co_node = await ctrl_folder.add_variable(idx, "CO", 0.0, ua.VariantType.Float)
        mode_node = await ctrl_folder.add_variable(idx, "Mode", 0, ua.VariantType.Int32)

        await pv_node.set_writable()
        await sp_node.set_writable()
        await co_node.set_writable()
        await mode_node.set_writable()

        self.node_ids = {
            "pv": pv_node.nodeid.to_string(),
            "sp": sp_node.nodeid.to_string(),
            "co": co_node.nodeid.to_string(),
            "mode": mode_node.nodeid.to_string(),
        }

        async with self._server:
            self._ready.set()
            while not self._stop_event.is_set():
                await asyncio.sleep(0.1)
