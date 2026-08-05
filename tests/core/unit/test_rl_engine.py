"""Unit tests for RLEngine -- KPI-driven extremum-seeking optimizer.

Pure domain service, no sb3/numpy imports. The two convergence tests
(symptom regressions) are the direct proof of the fix: the engine must
converge on the Ti/Ki that maximizes the windowed-KPI reward, STOP
there (sustained gamma = 0), and never ratchet to the limit.
"""
from __future__ import annotations

import math

import pytest

from smart_pid_domain.enums import ControlObjective, ProcessSpeed


def make_stats(mae_frac=0.0, osc=0.0, tv=0.0, n=100, span=100.0):
    """StatsWorker-shaped snapshot: errors are absolute units."""
    return {
        "mean_abs_error": mae_frac * span,
        "osc": osc,
        "tv_per_sample": tv,
        "sample_count": n,
    }


def run_cycle(
    engine,
    ki,
    stats,
    *,
    applied=True,
    objective=None,
    integral_type="TIME_TI",
    limit_min=0.1,
    limit_max=100.0,
):
    """One AI decision with the worker's call shape (speed MEDIUM).

    ``ki`` is whatever the loop actuates: Ti itself for TIME_TI loops,
    the integral gain for GAIN_KI loops.
    """
    if objective is None:
        objective = ControlObjective.SP_TRACKING
    return engine.compute_gamma(
        error=5.0,
        delta_error=0.0,
        ki_current=ki,
        span=100.0,
        co=50.0,
        integral_val=0.0,
        objective=objective,
        speed=ProcessSpeed.MEDIUM,
        limit_min=limit_min,
        limit_max=limit_max,
        integral_type=integral_type,
        stats=stats,
        applied=applied,
    )


class TestEngineBasics:
    def test_creates_without_sb3_or_numpy(self):
        """Construction must not require sb3/gymnasium (or numpy)."""
        from smart_pid_core.domain.services.rl_engine import RLEngine

        engine = RLEngine()
        assert engine.reward_steps == 0
        assert engine.step_count == 0
        assert engine.avg_reward == 0.0

    def test_no_stats_returns_zero_gamma_and_arms_nothing(self):
        from smart_pid_core.domain.services.rl_engine import RLEngine

        engine = RLEngine()
        d = run_cycle(engine, 10.0, None)
        assert d.gamma == 0.0
        assert d.new_ki == 10.0
        assert "waiting" in d.reasoning
        # No search state armed: a following real window probes fresh.
        assert engine._pending_judge is False
        assert engine._dwell == 0
        assert engine.reward_steps == 0

    def test_dwell_settles_one_decision_after_a_probe(self):
        from smart_pid_core.domain.services.rl_engine import RLEngine

        engine = RLEngine()
        d1 = run_cycle(engine, 10.0, make_stats(mae_frac=0.05))
        assert d1.gamma != 0.0  # first probe
        # Even with a better reward, the next decision is the settling window.
        d2 = run_cycle(engine, d1.new_ki, make_stats(mae_frac=0.01))
        assert d2.gamma == 0.0
        assert "settling" in d2.reasoning


class TestConvergence:
    """Symptom regressions: converge, stop, never pin at the limit."""

    def test_converges_and_stops_on_synthetic_landscape(self):
        """mae_frac(ti) has its optimum at Ti=2.0; start far away at Ti=20."""
        from smart_pid_core.domain.services.rl_engine import RLEngine

        def mae_frac(ti):
            return min(0.5, abs(math.log(ti / 2.0)) * 0.08)

        engine = RLEngine()
        ti = 20.0
        gammas = []
        for _ in range(120):
            d = run_cycle(engine, ti, make_stats(mae_frac=mae_frac(ti)))
            gammas.append(d.gamma)
            ti = d.new_ki
            assert ti < 100.0  # never touched limit_max

        assert 1.0 <= ti <= 4.0, f"Ti={ti} did not converge to ~2.0"
        assert all(g == 0.0 for g in gammas[-10:]), (
            f"engine did not stop: last gammas {gammas[-10:]}"
        )

    def test_converges_and_stops_for_gain_ki_loops(self):
        """Same landscape expressed over Ki directly (law inverts gamma)."""
        from smart_pid_core.domain.services.rl_engine import RLEngine

        def mae_frac(ki):
            return min(0.5, abs(math.log(ki / 2.0)) * 0.08)

        engine = RLEngine()
        ki = 20.0
        gammas = []
        for _ in range(120):
            d = run_cycle(
                engine, ki, make_stats(mae_frac=mae_frac(ki)),
                integral_type="GAIN_KI",
            )
            gammas.append(d.gamma)
            ki = d.new_ki
            assert ki < 100.0

        assert 1.0 <= ki <= 4.0, f"Ki={ki} did not converge to ~2.0"
        assert all(g == 0.0 for g in gammas[-10:])

    def test_flat_reward_holds_quickly_without_drifting(self):
        """Anti-runaway: constant KPIs must park the search, not ratchet Ti."""
        from smart_pid_core.domain.services.rl_engine import RLEngine

        engine = RLEngine()
        ki = 20.0
        ti0 = ki  # TIME_TI: the actuated value is Ti itself
        budget = (
            2 * (RLEngine._DWELL_DECISIONS + 1) * RLEngine._HOLD_AFTER_FLATS + 2
        )
        entered_hold_at = None
        for i in range(budget):
            d = run_cycle(engine, ki, make_stats(mae_frac=0.01))
            ki = d.new_ki
            if "converged" in d.reasoning:
                entered_hold_at = i
                break
        assert entered_hold_at is not None, f"no hold within {budget} cycles"
        # After entering hold every decision stays gamma=0.
        for _ in range(3):
            d = run_cycle(engine, ki, make_stats(mae_frac=0.01))
            assert d.gamma == 0.0
        assert abs(ki - ti0) < 0.5 * ti0


class TestJudgment:
    def test_worse_reward_flips_direction_and_shrinks_step(self):
        from smart_pid_core.domain.services.rl_engine import RLEngine

        engine = RLEngine()
        d1 = run_cycle(engine, 10.0, make_stats(mae_frac=0.05))
        assert d1.gamma > 0.0
        run_cycle(engine, d1.new_ki, make_stats(mae_frac=0.05))  # settling
        # The probe made things measurably worse.
        d2 = run_cycle(engine, d1.new_ki, make_stats(mae_frac=0.20))
        assert d2.gamma < 0.0, "direction must flip on worsening reward"
        assert abs(d2.gamma) < abs(d1.gamma), "step must shrink on worsening"

    def test_better_reward_grows_step_and_keeps_direction(self):
        from smart_pid_core.domain.services.rl_engine import RLEngine

        engine = RLEngine()
        d1 = run_cycle(engine, 10.0, make_stats(mae_frac=0.20))
        run_cycle(engine, d1.new_ki, make_stats(mae_frac=0.20))  # settling
        d2 = run_cycle(engine, d1.new_ki, make_stats(mae_frac=0.05))
        assert d2.gamma > 0.0
        assert abs(d2.gamma) > abs(d1.gamma)

    def test_applied_false_freezes_the_search(self):
        """Suggestions are not measurements: nothing arms, nothing moves."""
        from smart_pid_core.domain.services.rl_engine import RLEngine

        engine = RLEngine()
        suggestions = []
        for _ in range(5):
            d = run_cycle(engine, 10.0, make_stats(mae_frac=0.05), applied=False)
            suggestions.append(d)
            assert engine._pending_judge is False
            assert engine._dwell == 0
            assert engine._expected_ki is None
        # Same suggestion every time — no judgment ever consumed the probes.
        for d in suggestions[1:]:
            assert d.gamma == suggestions[0].gamma
            assert d.new_ki == suggestions[0].new_ki
        # Even a worsening reward cannot flip the direction: nothing was armed.
        d = run_cycle(engine, 10.0, make_stats(mae_frac=0.40), applied=False)
        assert d.gamma == suggestions[0].gamma

    def test_external_retune_soft_resets_the_search(self):
        from smart_pid_core.domain.services.rl_engine import RLEngine

        engine = RLEngine()
        d1 = run_cycle(engine, 10.0, make_stats(mae_frac=0.05))
        run_cycle(engine, d1.new_ki, make_stats(mae_frac=0.04))  # settling
        d_probe = run_cycle(engine, d1.new_ki, make_stats(mae_frac=0.03))
        assert d_probe.gamma != 0.0
        # Operator moves Ti 50% behind the search's back.
        moved_ki = d_probe.new_ki * 1.5
        d = run_cycle(engine, moved_ki, make_stats(mae_frac=0.03))
        assert "external" in d.reasoning
        # Fresh probe from the reset: initial step, no stale judgment.
        assert abs(d.gamma) == pytest.approx(RLEngine._STEP_INIT)
        assert engine._pending_judge is True
        assert engine._r_before is not None


class TestOscillationEmergency:
    def test_high_osc_damps_immediately_even_in_hold(self):
        from smart_pid_core.domain.services.rl_engine import RLEngine

        engine = RLEngine()
        engine._holding = True
        engine._hold_reward = 0.0
        d = run_cycle(engine, 10.0, make_stats(mae_frac=0.01, osc=0.8))
        assert d.gamma == pytest.approx(-0.8)
        assert "osc emergency" in d.reasoning
        assert engine._direction == -1
        assert engine._holding is False
        # Ti rose (integral weakened) on this decision: TIME_TI inverts gamma.
        assert d.new_ki > 10.0


class TestHoldLifecycle:
    def _drive_into_hold(self, engine, ki):
        from smart_pid_core.domain.services.rl_engine import RLEngine

        stats = make_stats(mae_frac=0.01)
        budget = (
            2 * (RLEngine._DWELL_DECISIONS + 1) * RLEngine._HOLD_AFTER_FLATS + 2
        )
        for _ in range(budget):
            d = run_cycle(engine, ki, stats)
            ki = d.new_ki
            if engine._holding:
                return ki
        raise AssertionError("engine never entered hold")

    def test_hold_returns_zero_gamma_while_kpis_stable(self):
        from smart_pid_core.domain.services.rl_engine import RLEngine

        engine = RLEngine()
        ki = self._drive_into_hold(engine, 20.0)
        for _ in range(3):
            d = run_cycle(engine, ki, make_stats(mae_frac=0.01))
            assert d.gamma == 0.0
            assert "holding" in d.reasoning

    def test_sustained_degradation_restarts_the_search(self):
        from smart_pid_core.domain.services.rl_engine import RLEngine

        engine = RLEngine()
        ki = self._drive_into_hold(engine, 20.0)
        # Reward far below hold_reward for the debounce window.
        gammas = []
        for _ in range(RLEngine._RESTART_DEBOUNCE + 2):
            d = run_cycle(engine, ki, make_stats(mae_frac=0.45))
            gammas.append(d.gamma)
        assert any(g != 0.0 for g in gammas), "hold never re-armed the search"

    def test_clamp_noop_at_limit_counts_flats_and_holds(self):
        from smart_pid_core.domain.services.rl_engine import RLEngine

        engine = RLEngine()
        ki = 100.0  # sitting on limit_max
        # TIME_TI: gamma=-1 raises Ti, i.e. pushes past the limit.
        engine._direction = -1
        stats = make_stats(mae_frac=0.01)
        saw_hold = False
        for _ in range(RLEngine._HOLD_AFTER_FLATS + 1):
            d = run_cycle(engine, ki, stats, limit_max=100.0)
            assert d.new_ki == 100.0  # never overshoots the limit
            assert d.gamma == 0.0
            saw_hold = saw_hold or engine._holding
        assert saw_hold


class TestObjectiveChange:
    def test_objective_change_resets_the_search(self):
        from smart_pid_core.domain.services.rl_engine import RLEngine

        engine = RLEngine()
        ki = 20.0
        stats = make_stats(mae_frac=0.01)
        budget = (
            2 * (RLEngine._DWELL_DECISIONS + 1) * RLEngine._HOLD_AFTER_FLATS + 2
        )
        for _ in range(budget):
            d = run_cycle(engine, ki, stats)
            ki = d.new_ki
            if engine._holding:
                break
        assert engine._holding
        d = run_cycle(
            engine, ki, stats, objective=ControlObjective.DISTURBANCE_REJECTION
        )
        # Hold dropped, step restored, and the same decision probes again.
        assert engine._holding is False
        assert engine._gamma_step == pytest.approx(RLEngine._STEP_INIT)
        assert d.gamma != 0.0


class TestPersistence:
    def test_save_load_v3_round_trip(self, tmp_path):
        from smart_pid_core.domain.services.rl_engine import RLEngine

        engine = RLEngine()
        d1 = run_cycle(engine, 10.0, make_stats(mae_frac=0.05))
        run_cycle(engine, d1.new_ki, make_stats(mae_frac=0.05))  # settling
        run_cycle(engine, d1.new_ki, make_stats(mae_frac=0.20))  # judged worse
        engine._holding = True
        engine._hold_reward = 0.42

        state = engine.save_state(tmp_path)
        assert state["version"] == 3
        assert "replay_buffer" not in state

        engine2 = RLEngine()
        engine2.load_state(state, tmp_path)
        assert engine2._direction == engine._direction
        assert engine2._gamma_step == pytest.approx(engine._gamma_step)
        assert engine2._holding is True
        assert engine2._hold_reward == pytest.approx(0.42)
        assert engine2.step_count == engine.step_count
        assert engine2._last_objective == ControlObjective.SP_TRACKING

    def test_load_state_discards_version_2_state(self, tmp_path, caplog):
        from smart_pid_core.domain.services.rl_engine import RLEngine

        engine = RLEngine()
        old_state = {
            "version": 2,
            "algorithm": "SAC",
            "model_path": "",
            "is_trained": True,
            "step_count": 10,
            "reward_steps": 5,
            "total_reward": 1.0,
            "replay_buffer": [],
            "fallback": {"integral": 0.0, "error_signs": [], "recent_errors": []},
        }
        with caplog.at_level("INFO"):
            engine.load_state(old_state, tmp_path)
        # Untouched: defaults survived.
        assert engine._direction == 1
        assert engine.step_count == 0
        assert engine._holding is False
        assert "rl_state_version_mismatch" in caplog.text


class TestReset:
    def test_reset_clears_search_state(self):
        from smart_pid_core.domain.services.rl_engine import RLEngine

        engine = RLEngine()
        d1 = run_cycle(engine, 10.0, make_stats(mae_frac=0.05))
        run_cycle(engine, d1.new_ki, make_stats(mae_frac=0.05))  # settling
        run_cycle(engine, d1.new_ki, make_stats(mae_frac=0.20))  # judged worse
        engine.reset()
        assert engine.step_count == 0
        assert engine._direction == 1
        assert engine._gamma_step == pytest.approx(RLEngine._STEP_INIT)
        assert engine._holding is False
        assert engine._pending_judge is False
        assert engine._expected_ki is None
        assert engine._last_objective is None


class TestComputeRewardFromStats:
    """Windowed-KPI reward: objective weights, gates, clamp (unchanged)."""

    def _stats(self, **overrides):
        base = {
            "sample_count": 50,
            "mean_abs_error": 1.0,
            "osc": 0.1,
            "tv_per_sample": 2.0,
            "recent_pk_pk_error": 1.0,
        }
        base.update(overrides)
        return base

    def test_sample_count_too_small_returns_none(self):
        from smart_pid_core.domain.services.rl_engine import compute_reward_from_stats

        stats = self._stats(sample_count=5)
        reward = compute_reward_from_stats(
            stats, span=100.0, objective=ControlObjective.SP_TRACKING
        )
        assert reward is None

    def test_zero_span_returns_none(self):
        from smart_pid_core.domain.services.rl_engine import compute_reward_from_stats

        stats = self._stats()
        reward = compute_reward_from_stats(
            stats, span=0.0, objective=ControlObjective.SP_TRACKING
        )
        assert reward is None

    @pytest.mark.parametrize(
        "objective",
        [
            ControlObjective.SP_TRACKING,
            ControlObjective.DISTURBANCE_REJECTION,
            ControlObjective.SURGE_LEVEL,
        ],
    )
    def test_worse_kpis_give_strictly_lower_reward(self, objective):
        from smart_pid_core.domain.services.rl_engine import compute_reward_from_stats

        good = self._stats(mean_abs_error=0.1, osc=0.0, tv_per_sample=0.5)
        bad = self._stats(mean_abs_error=20.0, osc=0.9, tv_per_sample=40.0)
        r_good = compute_reward_from_stats(good, span=100.0, objective=objective)
        r_bad = compute_reward_from_stats(bad, span=100.0, objective=objective)
        assert r_good is not None
        assert r_bad is not None
        assert r_bad < r_good

    def test_reward_clamped_to_minus5_plus2(self):
        from smart_pid_core.domain.services.rl_engine import compute_reward_from_stats

        awful = self._stats(mean_abs_error=500.0, osc=1.0, tv_per_sample=500.0)
        r = compute_reward_from_stats(
            awful, span=100.0, objective=ControlObjective.SP_TRACKING
        )
        assert r == pytest.approx(-5.0)
