"""Integration tests for AI model metadata and tuning log persistence."""
from __future__ import annotations

import pytest

from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository


@pytest.fixture
async def repo(tmp_path):
    r = SQLiteRepository(tmp_path / "test.spid")
    await r.initialize()
    # Need a controller row for FK reference
    await r.db.execute(
        "INSERT INTO Controladores (id, nome) VALUES (1, 'Test')"
    )
    await r.db.commit()
    yield r


class TestAIModelRepo:
    @pytest.mark.asyncio
    async def test_save_and_get_model_metadata(self, repo):
        from smart_pid_core.adapters.outbound.ai_repo import AIRepository

        ai_repo = AIRepository(repo.db)
        model_id = await ai_repo.save_model_metadata(
            controller_id=1,
            algorithm="SAC",
            episodes=100,
            avg_reward=0.85,
            model_path="/models/ctrl1/sac_001.zip",
        )
        assert model_id > 0

        model = await ai_repo.get_latest_model(controller_id=1)
        assert model is not None
        assert model["algorithm"] == "SAC"
        assert model["episodes"] == 100

    @pytest.mark.asyncio
    async def test_log_tuning_action(self, repo):
        from smart_pid_core.adapters.outbound.ai_repo import AIRepository

        ai_repo = AIRepository(repo.db)
        await ai_repo.log_tuning_action(
            controller_id=1,
            engine="FUZZY",
            gamma=0.5,
            old_ki=10.0,
            new_ki=11.5,
            objective="SP_TRACKING",
            reasoning="test action",
        )
        history = await ai_repo.get_tuning_history(controller_id=1, limit=10)
        assert len(history) == 1
        assert history[0]["motor"] == "FUZZY"
        assert history[0]["ki_antes"] == pytest.approx(10.0)
        assert history[0]["ki_depois"] == pytest.approx(11.5)
