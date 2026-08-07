"""Unit tests for the AIWorker full-retune producer.

Drives ``_observe_steady_state`` / ``_maybe_recommend_retune`` directly so the
steady-state gates and the gain fit can be exercised without waiting on the
worker's timer.  The bus-driven path is covered by
``tests/core/integration/test_tuning_recommendation_flow.py``.
"""
from __future__ import annotations

import logging

import msgpack
import pytest

from smart_pid_core.application.tuning_store import TuningRecommendationStore
from smart_pid_core.application.workers.ai_worker import AIWorker
from smart_pid_domain.enums import (
    AIEngine,
    ControlObjective,
    IntegralType,
    TuningRecStatus,
)
from smart_pid_domain.models.controller import (
    AIConfig,
    Controller,
    PIDParams,
    ScaleConfig,
)

_AI_WORKER_LOGGER = "smart_pid_core.application.workers.ai_worker"


class _StubBus:
    """AIWorker only touches the bus from its thread; constructing needs none."""


class _StubPub:
    def __init__(self) -> None:
        self.sent: list[tuple[bytes, dict]] = []

    def send(self, topic: bytes, payload: bytes) -> None:
        self.sent.append((topic, msgpack.unpackb(payload)))


def _quiet_stats(
    pk_pk: float = 0.0, samples: float = 60.0, tv: float = 0.0,
) -> dict[str, float]:
    return {
        "pk_pk_error": pk_pk, "sample_count": samples,
        "tv_per_sample": tv, "osc": 0.0,
    }


def _controller(
    *,
    integral_type: IntegralType = IntegralType.TIME_TI,
    objective: ControlObjective = ControlObjective.SP_TRACKING,
) -> Controller:
    return Controller(
        id=1, name="TIC-P", scan_rate_s=0.02, tss_s=0.20,
        integral_type=integral_type,
        pid_params=PIDParams(gain=1.0, reset=10.0, rate=0.0),
        pv_scale=ScaleConfig(eu_min=0.0, eu_max=100.0),
        ai_config=AIConfig(
            engine=AIEngine.FUZZY, objective=objective,
            dead_time_l=0.04, limit_min=0.001, limit_max=1000.0,
        ),
    )


def _worker(controller: Controller, store: TuningRecommendationStore) -> AIWorker:
    worker = AIWorker(
        bus=_StubBus(),  # type: ignore[arg-type]
        controller=controller,
        tuning_store=store,
    )
    worker._last_mode = "AUTO"
    worker._has_telemetry = True
    worker._latest_stats = _quiet_stats()
    return worker


_HELD_SP = 50.0


def _feed(
    worker: AIWorker,
    points: list[tuple[float, float]],
    *,
    pk_pk: float = 0.0,
    tv: float = 0.0,
    sp: float = _HELD_SP,
) -> None:
    """Present each (CO %, PV %) pair as a fresh settled observation.

    SP is held fixed across the whole sequence, and the cadence / SP-hold
    clocks are wound back so each call is eligible without real waiting.
    """
    for co, pv in points:
        worker._last_co = co
        worker._last_pv = pv
        worker._last_sp = sp
        worker._latest_stats = _quiet_stats(pk_pk=pk_pk, tv=tv)
        worker._last_ss_record_mono = 0.0
        worker._observed_sp = sp
        worker._sp_changed_mono = 0.0
        worker._observe_steady_state()


_LINEAR = [(20.0, 30.0), (40.0, 60.0), (60.0, 90.0)]  # PV = 1.5 * CO


class TestSteadyStateObservation:
    def test_records_settled_points(self) -> None:
        w = _worker(_controller(), TuningRecommendationStore())
        _feed(w, _LINEAR)
        assert len(w._ss_points) == 3
        assert w._estimate_process_gain() == pytest.approx(1.5)

    def test_rejects_moving_pv(self) -> None:
        """A large error excursion with SP fixed means PV is still moving."""
        w = _worker(_controller(), TuningRecommendationStore())
        _feed(w, _LINEAR, pk_pk=50.0)
        assert w._ss_points == {}

    def test_rejects_moving_valve(self) -> None:
        """PV can look quiet for a scan or two while CO is still travelling."""
        w = _worker(_controller(), TuningRecommendationStore())
        _feed(w, _LINEAR, tv=2.0)
        assert w._ss_points == {}

    def test_accepts_steady_offset(self) -> None:
        """PV parked off SP is still a point on the process curve."""
        w = _worker(_controller(), TuningRecommendationStore())
        _feed(w, _LINEAR, sp=_HELD_SP)  # PV 30/60/90 vs SP 50
        assert len(w._ss_points) == 3
        assert w._estimate_process_gain() == pytest.approx(1.5)

    def test_rejects_window_straddling_an_sp_step(self) -> None:
        """Right after an SP move the window holds a transient, not a steady state."""
        w = _worker(_controller(), TuningRecommendationStore())
        for co, pv in _LINEAR:
            w._last_co, w._last_pv = co, pv
            w._last_sp = pv  # a different SP each pass = a fresh SP step
            w._last_ss_record_mono = 0.0
            w._observe_steady_state()
        assert w._ss_points == {}

    def test_rejects_unpopulated_stats_window(self) -> None:
        w = _worker(_controller(), TuningRecommendationStore())
        _feed(w, _LINEAR)
        w._ss_points.clear()
        for co, pv in _LINEAR:
            w._last_co, w._last_pv, w._last_sp = co, pv, _HELD_SP
            w._latest_stats = _quiet_stats(samples=3.0)
            w._last_ss_record_mono = 0.0
            w._observe_steady_state()
        assert w._ss_points == {}

    def test_rejects_non_auto_mode(self) -> None:
        w = _worker(_controller(), TuningRecommendationStore())
        w._last_mode = "MAN"
        _feed(w, _LINEAR)
        assert w._ss_points == {}

    def test_cadence_gate_blocks_back_to_back_records(self) -> None:
        """Without a full TSS between records the stats window is stale."""
        w = _worker(_controller(), TuningRecommendationStore())
        _feed(w, _LINEAR[:1])
        for co, pv in _LINEAR[1:]:
            w._last_co, w._last_pv, w._last_sp = co, pv, _HELD_SP
            w._observe_steady_state()  # no _last_ss_record_mono reset
        assert len(w._ss_points) == 1

    def test_same_operating_point_collapses_to_one_bucket(self) -> None:
        w = _worker(_controller(), TuningRecommendationStore())
        _feed(w, [(40.0, 60.0), (40.4, 60.6), (41.0, 61.5)])
        assert len(w._ss_points) == 1

    def test_bucket_capacity_is_bounded(self) -> None:
        w = _worker(_controller(), TuningRecommendationStore())
        _feed(w, [(float(co), 1.5 * co) for co in range(0, 100, 5)])
        assert len(w._ss_points) <= 8


class TestGainEstimation:
    def test_too_few_points_is_unknown(self) -> None:
        w = _worker(_controller(), TuningRecommendationStore())
        _feed(w, _LINEAR[:2])
        assert w._estimate_process_gain() is None

    def test_insufficient_co_travel_is_unknown(self) -> None:
        w = _worker(_controller(), TuningRecommendationStore())
        # Three buckets but only 1.2 % of CO between the extremes.
        _feed(w, [(40.0, 60.0), (41.0, 61.5), (41.2, 61.8)])
        assert w._estimate_process_gain() is None

    def test_uncorrelated_cloud_is_unknown(self) -> None:
        """Closed-loop constant-SP operation carries no gain information."""
        w = _worker(_controller(), TuningRecommendationStore())
        _feed(w, [(20.0, 50.0), (40.0, 50.2), (60.0, 49.9), (80.0, 50.1)])
        assert w._estimate_process_gain() is None

    def test_reverse_acting_gain_is_negative(self) -> None:
        w = _worker(_controller(), TuningRecommendationStore())
        _feed(w, [(20.0, 90.0), (40.0, 60.0), (60.0, 30.0)])
        assert w._estimate_process_gain() == pytest.approx(-1.5)


class TestSkipDiagnostics:
    """The "why is there no recommendation?" trail."""

    def test_logs_reason_when_gain_unknown(self, caplog) -> None:
        w = _worker(_controller(), TuningRecommendationStore())
        with caplog.at_level(logging.INFO, logger=_AI_WORKER_LOGGER):
            w._maybe_recommend_retune(_StubPub())
        assert "tuning_retune_skip cid=1 reason=gain_unidentifiable" in caplog.text

    def test_reason_is_edge_triggered(self, caplog) -> None:
        """An unidentifiable loop must not fill the log every AI tick."""
        w = _worker(_controller(), TuningRecommendationStore())
        with caplog.at_level(logging.INFO, logger=_AI_WORKER_LOGGER):
            for _ in range(5):
                w._maybe_recommend_retune(_StubPub())
        assert caplog.text.count("tuning_retune_skip") == 1

    def test_logs_the_new_reason_when_it_changes(self, caplog) -> None:
        w = _worker(_controller(integral_type=IntegralType.GAIN_KI),
                    TuningRecommendationStore())
        with caplog.at_level(logging.INFO, logger=_AI_WORKER_LOGGER):
            w._maybe_recommend_retune(_StubPub())
        assert "reason=integral_type_not_time_ti" in caplog.text


class TestRetuneProduction:
    def test_produces_pending_recommendation(self) -> None:
        store = TuningRecommendationStore()
        w = _worker(_controller(), store)
        pub = _StubPub()
        _feed(w, _LINEAR)
        w._maybe_recommend_retune(pub)

        tracked = store.get(1)
        assert tracked is not None
        assert tracked.status == TuningRecStatus.PENDING
        rec = tracked.recommendation
        assert rec.recommended_kp == pytest.approx(0.5)
        assert rec.recommended_ti == pytest.approx(0.06)
        assert rec.recommended_td == pytest.approx(0.04 * 0.04 / 0.12)
        assert rec.current_kp == pytest.approx(1.0)
        assert rec.current_ti == pytest.approx(10.0)

    def test_publishes_tuning_recommended_off_the_action_topic(self) -> None:
        """It must never ride ACTION.AI.*, which IOWorker writes to the PLC."""
        w = _worker(_controller(), TuningRecommendationStore())
        pub = _StubPub()
        _feed(w, _LINEAR)
        w._maybe_recommend_retune(pub)

        assert len(pub.sent) == 1
        topic, payload = pub.sent[0]
        assert topic == b"EVENT.TUNING_REC.1"
        assert not topic.startswith(b"ACTION.AI")
        assert payload["recommended_kp"] == pytest.approx(0.5)
        assert payload["controller_id"] == 1
        assert "IMC" in payload["reason"]

    def test_no_gain_produces_nothing(self) -> None:
        store = TuningRecommendationStore()
        w = _worker(_controller(), store)
        w._maybe_recommend_retune(_StubPub())
        assert store.get(1) is None

    def test_gain_ki_loops_are_skipped(self) -> None:
        """The IMC rule yields an integral time; a Ki node has other units."""
        store = TuningRecommendationStore()
        w = _worker(_controller(integral_type=IntegralType.GAIN_KI), store)
        pub = _StubPub()
        _feed(w, _LINEAR)
        w._maybe_recommend_retune(pub)
        assert store.get(1) is None
        assert pub.sent == []

    def test_no_store_is_a_no_op(self) -> None:
        controller = _controller()
        w = AIWorker(bus=_StubBus(), controller=controller)  # type: ignore[arg-type]
        w._last_mode = "AUTO"
        w._has_telemetry = True
        pub = _StubPub()
        _feed(w, _LINEAR)
        w._maybe_recommend_retune(pub)
        assert pub.sent == []

    def test_repeat_tick_does_not_republish(self) -> None:
        """Anti-churn: an unchanged proposal is not raised twice."""
        store = TuningRecommendationStore()
        w = _worker(_controller(), store)
        pub = _StubPub()
        _feed(w, _LINEAR)
        w._maybe_recommend_retune(pub)
        first = store.get(1).recommendation.id
        for _ in range(3):
            w._maybe_recommend_retune(pub)
        assert len(pub.sent) == 1
        assert store.get(1).recommendation.id == first

    def test_materially_different_model_republishes(self) -> None:
        store = TuningRecommendationStore()
        w = _worker(_controller(), store)
        pub = _StubPub()
        _feed(w, _LINEAR)
        w._maybe_recommend_retune(pub)
        first = store.get(1).recommendation.id

        # Process gain halves -> Kp doubles, well past the 10 % gate.
        w._ss_points.clear()
        _feed(w, [(20.0, 15.0), (40.0, 30.0), (60.0, 45.0)])
        w._maybe_recommend_retune(pub)

        assert len(pub.sent) == 2
        second = store.get(1)
        assert second.recommendation.id != first
        assert second.recommendation.recommended_kp == pytest.approx(1.0)

    def test_objective_changes_the_proposal(self) -> None:
        store = TuningRecommendationStore()
        w = _worker(
            _controller(objective=ControlObjective.SURGE_LEVEL), store,
        )
        _feed(w, _LINEAR)
        w._maybe_recommend_retune(_StubPub())
        rec = store.get(1).recommendation
        # lambda = max(3*0.04, 0.8*0.04) = 0.12 -> Kp = 0.12 / (2*1.5*0.16)
        assert rec.recommended_kp == pytest.approx(0.12 / 0.48)
        assert "SURGE_LEVEL" in rec.reason


class TestIntegralSuggestionIsOfferedWhenAutoApplyIsOff:
    """With the auto-apply gate closed the optimizer still knows what it
    wants. If that suggestion is not parked anywhere, the operator can see it
    on the faceplate and has no way to accept it — the Apply button stays
    disabled and the loop can never be tuned by hand.
    """

    def test_it_parks_a_pending_recommendation(self) -> None:
        store = TuningRecommendationStore()
        controller = _controller()
        worker = _worker(controller, store)

        worker._park_integral_suggestion(10.0, 13.5)

        tracked = store.get(1)
        assert tracked is not None
        assert tracked.status == TuningRecStatus.PENDING
        rec = tracked.recommendation
        assert rec.current_ti == 10.0
        assert rec.recommended_ti == 13.5
        # Only the integral term moves.
        assert rec.recommended_kp == rec.current_kp == controller.pid_params.gain
        assert rec.recommended_td == rec.current_td == controller.pid_params.rate

    def test_a_suggestion_that_changes_nothing_is_not_offered(self) -> None:
        store = TuningRecommendationStore()
        worker = _worker(_controller(), store)
        worker._park_integral_suggestion(10.0, 10.0)
        assert store.get(1) is None

    def test_it_never_overwrites_a_standing_full_retune(self) -> None:
        """A full Kp+Ti+Td proposal is richer and may already be on the
        operator's screen awaiting an answer."""
        from uuid import uuid4

        from smart_pid_domain.models.tuning import TuningRecommendation

        store = TuningRecommendationStore()
        worker = _worker(_controller(), store)
        store.put(TuningRecommendation(
            id=uuid4(), controller_id=1,
            current_kp=1.0, current_ti=10.0, current_td=0.0,
            recommended_kp=2.5, recommended_ti=20.0, recommended_td=1.0,
            reason="full retune", timestamp=1.0,
        ))

        worker._park_integral_suggestion(10.0, 13.5)

        rec = store.get(1).recommendation
        assert rec.reason == "full retune"
        assert rec.recommended_kp == 2.5

    def test_it_refreshes_its_own_earlier_suggestion(self) -> None:
        store = TuningRecommendationStore()
        worker = _worker(_controller(), store)
        worker._park_integral_suggestion(10.0, 12.0)
        worker._park_integral_suggestion(10.0, 15.0)
        assert store.get(1).recommendation.recommended_ti == 15.0

    def test_no_store_is_not_an_error(self) -> None:
        worker = _worker(_controller(), TuningRecommendationStore())
        worker._tuning_store = None
        worker._park_integral_suggestion(10.0, 13.5)  # must not raise


class TestLiveConfigEditsReachTheWorker:
    """The worker caches its Controller, so a persisted edit has to be pushed
    in. Without this the auto-apply switch moved in the database while the
    optimizer thread kept reading its start-up copy."""

    def test_the_auto_apply_gate_can_be_flipped_at_runtime(self) -> None:
        from dataclasses import replace

        from smart_pid_domain.enums import TuningWriteMode

        controller = _controller()
        worker = _worker(controller, TuningRecommendationStore())
        assert worker._controller.tuning_write_mode == TuningWriteMode.APPROVAL_REQUIRED

        worker.update_controller(
            replace(controller, tuning_write_mode=TuningWriteMode.AUTO_APPLY),
        )
        assert worker._controller.tuning_write_mode == TuningWriteMode.AUTO_APPLY

    def test_a_config_save_does_not_restart_a_stopped_optimizer(self) -> None:
        """`_enabled` belongs to CMD.AI, not to the config form."""
        from dataclasses import replace

        controller = _controller()
        worker = _worker(controller, TuningRecommendationStore())
        worker.set_enabled(False)
        worker.set_paused(True)

        worker.update_controller(replace(controller, optimization_enabled=True))

        assert worker.is_enabled is False
        assert worker.is_paused is True

    def test_it_adopts_the_new_ai_period_and_band(self) -> None:
        from dataclasses import replace

        controller = _controller()
        worker = _worker(controller, TuningRecommendationStore())
        worker.update_controller(
            replace(controller, tss_s=30.0, stability_band_pct=0.5),
        )
        assert worker._ai_period_s == pytest.approx(60.0)
        assert worker._stability_band_pct == pytest.approx(0.5)


class TestCadence:
    """The AI tick is 2 × TSS at rest, and follows the measured oscillation
    period while the loop actually oscillates.
    """

    @staticmethod
    def _cadence_worker(stats: dict[str, float] | None) -> AIWorker:
        from dataclasses import replace

        worker = _worker(
            replace(_controller(), tss_s=60.0), TuningRecommendationStore(),
        )
        worker._latest_stats = stats
        return worker

    def test_the_base_period_is_two_tss(self) -> None:
        assert self._cadence_worker(None)._ai_period_s == pytest.approx(120.0)

    def test_no_stats_yet_holds_the_base_period(self) -> None:
        worker = self._cadence_worker(None)
        assert worker._effective_period_s() == pytest.approx(120.0)

    def test_a_score_below_the_gate_holds_the_base_period(self) -> None:
        worker = self._cadence_worker({"osc": 0.2, "osc_period_s": 30.0})
        assert worker._effective_period_s() == pytest.approx(120.0)

    def test_an_unmeasurable_period_holds_the_base_period(self) -> None:
        """A high score with no measured period is not actionable evidence."""
        worker = self._cadence_worker({"osc": 0.8, "osc_period_s": 0.0})
        assert worker._effective_period_s() == pytest.approx(120.0)

    def test_an_oscillating_loop_follows_two_oscillation_periods(self) -> None:
        worker = self._cadence_worker({"osc": 0.8, "osc_period_s": 30.0})
        assert worker._effective_period_s() == pytest.approx(60.0)

    def test_a_fast_oscillation_is_held_at_the_floor(self) -> None:
        """2 × 4 s would re-tune on stats the window has not refreshed."""
        worker = self._cadence_worker({"osc": 0.8, "osc_period_s": 4.0})
        assert worker._effective_period_s() == pytest.approx(15.0)

    def test_a_slow_oscillation_is_capped_at_the_legacy_cadence(self) -> None:
        """Posc > TSS legitimately runs slower than the base, but never
        slower than the 3 × TSS the worker used before.
        """
        worker = self._cadence_worker({"osc": 0.8, "osc_period_s": 200.0})
        assert worker._effective_period_s() == pytest.approx(180.0)

    def test_the_cadence_source_is_edge_logged(self, caplog) -> None:
        """One line per flip, not per tick — this runs every AI cycle."""
        worker = self._cadence_worker({"osc": 0.8, "osc_period_s": 30.0})
        with caplog.at_level(logging.INFO, logger=_AI_WORKER_LOGGER):
            for _ in range(3):
                worker._effective_period_s()
            assert caplog.text.count("ai_cadence") == 1
            assert "mode=osc period_s=60.0" in caplog.text

            worker._latest_stats = None
            worker._effective_period_s()
        assert caplog.text.count("ai_cadence") == 2
        assert "mode=base period_s=120.0" in caplog.text
