"""SPA history-API fallback for the static bundle mount.

Without the fallback, reloading or deep-linking /simulator on a deployed
single-origin build answered Starlette's 404 JSON instead of index.html,
because no file named `simulator` exists in dist/.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from smart_pid_core.adapters.inbound.api.app import _SPAStaticFiles


@pytest.fixture
def spa_client(tmp_path) -> TestClient:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>spa</html>")
    (dist / "assets").mkdir()
    (dist / "assets" / "index.js").write_text("/*js*/")
    app = FastAPI()
    app.mount("/", _SPAStaticFiles(directory=str(dist), html=True), name="spa")
    with TestClient(app) as client:
        yield client


async def test_spa_route_falls_back_to_index(spa_client) -> None:
    res = spa_client.get("/simulator")
    assert res.status_code == 200
    assert "<html>spa</html>" in res.text


async def test_root_serves_index(spa_client) -> None:
    res = spa_client.get("/")
    assert res.status_code == 200
    assert "<html>spa</html>" in res.text


async def test_real_assets_still_served(spa_client) -> None:
    res = spa_client.get("/assets/index.js")
    assert res.status_code == 200
    assert "/*js*/" in res.text
