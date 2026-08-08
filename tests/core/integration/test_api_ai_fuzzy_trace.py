"""HTTP contract for GET /controllers/{id}/ai/fuzzy.

The Fuzzy screen is a pure renderer of this payload: it plots the membership
functions from `functions[].params`, positions the crisp marker from `value`
inside `[domain_min, domain_max]`, and highlights rules by `fired`/`strength`.
So the wire shape IS the feature, and the three 404 branches are the screen's
empty state — the endpoint must never invent an inference that did not run.
"""
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from smart_pid_core.application.loop_manager import LoopContext
from smart_pid_core.application.workers.ai_worker import AIWorker
from smart_pid_core.domain.services.fuzzy_engine_v2 import (
    RULES,
    FuzzyEngineV2Dispatcher,
)
from smart_pid_domain.enums import AIEngine, ControlObjective
from smart_pid_domain.models.controller import AIConfig, Controller, PIDParams

if TYPE_CHECKING:
    from httpx import AsyncClient


async def _register(
    api_deps: dict,
    *,
    engine: AIEngine,
    objective: ControlObjective = ControlObjective.SP_TRACKING,
    infer: tuple[float, ...] | None = None,
) -> int:
    """Register a loop whose AI worker carries a real fuzzy dispatcher.

    `LoopManager.get_ai_workers()` only reports workers whose thread is alive,
    so the worker itself is a spec'd stub — but `_engine` is the genuine
    dispatcher, because the endpoint reads the trace the real `infer()`
    records. `infer=None` leaves `last_trace` unset, i.e. "never ran".
    """
    saved = await api_deps["repo"].save(
        Controller(
            id=0,
            name=f"AIC-{engine.value}",
            pid_params=PIDParams(gain=1.0, reset=10.0, rate=0.0),
            ai_config=AIConfig(engine=engine, objective=objective),
        )
    )
    dispatcher = FuzzyEngineV2Dispatcher(objective=objective)
    if infer is not None:
        dispatcher.engine.infer(*infer)

    worker = MagicMock(spec=AIWorker)
    worker.is_alive.return_value = True
    worker._ai_config = saved.ai_config
    worker._engine = dispatcher
    api_deps["loop_manager"]._loops[saved.id] = LoopContext(
        controller=saved, ai_worker=worker
    )
    return saved.id


class TestFuzzyTracePayload:
    @pytest.mark.asyncio
    async def test_returns_every_rule_with_the_fired_one_flagged(
        self, client: AsyncClient, user_headers: dict[str, str], api_deps: dict
    ) -> None:
        # iae=0.7 -> HIGH, osc/eff/ovs at 0 -> STABLE/SMOOTH/NONE, which is
        # exactly RULES[2] ({iae HIGH, osc STABLE, eff SMOOTH, ovs NONE} -> R).
        cid = await _register(
            api_deps, engine=AIEngine.FUZZY, infer=(0.7, 0.0, 0.0, 0.0)
        )
        resp = await client.get(f"/controllers/{cid}/ai/fuzzy", headers=user_headers)
        assert resp.status_code == 200
        body = resp.json()

        assert body["controller_id"] == cid
        assert body["objective"] == ControlObjective.SP_TRACKING.value
        # The whole rule base is published, not just the firing subset: the
        # screen renders every rule and highlights the ones that fired.
        assert len(body["rules"]) == len(RULES)
        assert [r["index"] for r in body["rules"]] == list(range(len(RULES)))

        fired = [r for r in body["rules"] if r["fired"]]
        assert [r["index"] for r in fired] == [2]
        assert fired[0]["output"] == "R"
        assert fired[0]["conditions"] == {
            "iae": "HIGH",
            "osc": "STABLE",
            "eff": "SMOOTH",
            "ovs": "NONE",
        }
        # min(mu_HIGH(0.7), 1, 1, 1) with MF_IAE HIGH = trap(0.6, 0.8, 1, 1).
        assert fired[0]["strength"] == pytest.approx(0.5)
        assert all(r["strength"] == 0.0 for r in body["rules"] if not r["fired"])

        # Single active output level -> centre-of-gravity collapses onto it.
        by_label = {o["label"]: o for o in body["outputs"]}
        assert by_label["R"]["strength"] == pytest.approx(0.5)
        assert body["delta_ti"] == pytest.approx(by_label["R"]["center"])

    @pytest.mark.asyncio
    async def test_every_input_is_plottable(
        self, client: AsyncClient, user_headers: dict[str, str], api_deps: dict
    ) -> None:
        cid = await _register(
            api_deps, engine=AIEngine.FUZZY, infer=(0.7, 0.0, 0.0, 0.0)
        )
        body = (
            await client.get(f"/controllers/{cid}/ai/fuzzy", headers=user_headers)
        ).json()

        assert {i["name"] for i in body["inputs"]} == {"iae", "osc", "eff", "ovs"}
        for src in body["inputs"]:
            # A marker outside the axis, or a collapsed axis, renders off-canvas.
            assert src["domain_min"] < src["domain_max"] < 1.0e6
            assert src["domain_min"] <= src["value"] <= src["domain_max"]
            assert src["functions"], f"{src['name']} has no membership functions"
            for mf in src["functions"]:
                assert mf["kind"] in {"tri", "trap"}
                assert len(mf["params"]) == (3 if mf["kind"] == "tri" else 4)
                assert 0.0 <= mf["degree"] <= 1.0
            # Fuzzification is the point of the screen: something must belong.
            assert max(mf["degree"] for mf in src["functions"]) > 0.0


class TestFuzzyTraceRefusals:
    @pytest.mark.asyncio
    async def test_no_inference_yet_is_404_not_a_fabricated_trace(
        self, client: AsyncClient, user_headers: dict[str, str], api_deps: dict
    ) -> None:
        cid = await _register(api_deps, engine=AIEngine.FUZZY, infer=None)
        resp = await client.get(f"/controllers/{cid}/ai/fuzzy", headers=user_headers)
        assert resp.status_code == 404
        assert "no fuzzy inference" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_non_fuzzy_engine_is_404(
        self, client: AsyncClient, user_headers: dict[str, str], api_deps: dict
    ) -> None:
        cid = await _register(api_deps, engine=AIEngine.RL)
        resp = await client.get(f"/controllers/{cid}/ai/fuzzy", headers=user_headers)
        assert resp.status_code == 404
        assert "not fuzzy" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_unknown_controller_is_404(
        self, client: AsyncClient, user_headers: dict[str, str]
    ) -> None:
        resp = await client.get("/controllers/9999/ai/fuzzy", headers=user_headers)
        assert resp.status_code == 404
        assert "no ai worker" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_requires_authentication(self, client: AsyncClient) -> None:
        resp = await client.get("/controllers/1/ai/fuzzy")
        assert resp.status_code == 401
