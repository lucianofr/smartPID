"""Unit tests for FuzzyEngineV2's InferenceTrace capture (`last_trace`) and
the `/ai/fuzzy` endpoint's domain/saturation guard.

Uses real engine instances throughout; the engine itself is never mocked.
"""
from __future__ import annotations

import pytest

from smart_pid_core.adapters.inbound.api.routers.ai import (
    _fuzzy_trace_response,
    _mfset_domain,
)
from smart_pid_core.domain.services.fuzzy_engine_v2 import (
    MF_E_MAX_DR,
    MF_EFF,
    MF_IAE,
    MF_OSC,
    MF_OVS,
    OUTPUT_CENTERS,
    RULES,
    FuzzyEngineV2,
    FuzzyEngineV2Dispatcher,
    FuzzyEngineV2DisturbanceRejection,
    FuzzyEngineV2SurgeLevel,
    _fuzzify,
    _rule_strength,
    _run_rules,
)
from smart_pid_domain.enums import ControlObjective


class TestRuleStrengthAgreesWithRunRules:
    """`_rule_strength` must be the exact per-rule term `_run_rules` maxes
    over when aggregating multiple rules onto the same output level."""

    def test_max_over_matching_rules_equals_output_strength(self):
        # iae=0.9 -> HIGH only; osc=0.1 -> STABLE only; ovs=0.0 -> NONE only.
        # eff=0.35 sits in the SMOOTH/MODERATE overlap, so R1's two "R"
        # legs (SMOOTH, MODERATE) both fire with different strengths while
        # R6's two "R" legs (gated on iae=MED) stay at zero.
        input_mfs = {
            "iae": _fuzzify(0.9, MF_IAE),
            "osc": _fuzzify(0.1, MF_OSC),
            "eff": _fuzzify(0.35, MF_EFF),
            "ovs": _fuzzify(0.0, MF_OVS),
        }
        _, output_strengths = _run_rules(input_mfs, RULES, OUTPUT_CENTERS)

        r_strengths = [
            _rule_strength(condition, input_mfs)
            for condition, out_lvl in RULES
            if out_lvl == "R"
        ]
        assert len(r_strengths) == 4  # R1 (SMOOTH, MODERATE) + R6 (SMOOTH, MODERATE)
        assert r_strengths[0] == pytest.approx(0.25, abs=1e-6)       # R1/SMOOTH
        assert r_strengths[1] == pytest.approx(1.0 / 6.0, abs=1e-6)  # R1/MODERATE
        assert r_strengths[2] == 0.0                                  # R6/SMOOTH (iae != MED)
        assert r_strengths[3] == 0.0                                  # R6/MODERATE (iae != MED)

        assert output_strengths["R"] == pytest.approx(max(r_strengths))
        assert output_strengths["R"] == pytest.approx(0.25, abs=1e-6)


class TestKnownRuleFiring:
    """Drive FuzzyEngineV2 so a specific, index-identified rule fires and a
    sibling rule does not — verified through the router's DTO mapping."""

    def test_ovs_high_rule_fires_and_ovs_mod_rule_does_not(self):
        # RULES[0] = ({"ovs": "HIGH"}, "AM")  -- depends only on "ovs"
        # RULES[1] = ({"ovs": "MOD"},  "A")   -- depends only on "ovs"
        assert RULES[0][0] == {"ovs": "HIGH"}
        assert RULES[0][1] == "AM"
        assert RULES[1][0] == {"ovs": "MOD"}
        assert RULES[1][1] == "A"

        engine = FuzzyEngineV2()
        # ovs=0.5 sits deep in MF_OVS's HIGH plateau (onset 0.30) and well
        # past MOD's upper shoulder (0.22): HIGH=1.0, MOD=0.0 exactly.
        engine.infer(iae=0.0, osc=0.0, eff=0.0, ovs=0.5)
        trace = engine.last_trace
        assert trace is not None

        resp = _fuzzy_trace_response(1, ControlObjective.SP_TRACKING, trace)

        rule_0 = resp.rules[0]
        rule_1 = resp.rules[1]
        assert rule_0.index == 0
        assert rule_0.fired is True
        assert rule_0.strength == pytest.approx(1.0)

        assert rule_1.index == 1
        assert rule_1.fired is False
        assert rule_1.strength == 0.0


class TestLastTraceLifecycle:
    def test_none_before_infer_populated_after(self):
        engine = FuzzyEngineV2()
        assert engine.last_trace is None
        engine.infer(iae=0.5, osc=0.1, eff=0.2, ovs=0.0)
        trace = engine.last_trace
        assert trace is not None
        assert trace.rules == RULES
        assert len(trace.rule_strengths) == len(trace.rules)

    def test_disturbance_rejection_last_trace(self):
        engine = FuzzyEngineV2DisturbanceRejection()
        assert engine.last_trace is None
        engine.infer(e_max=0.5, t_rec=2.0, osc=0.1)
        assert engine.last_trace is not None

    def test_surge_level_last_trace(self):
        engine = FuzzyEngineV2SurgeLevel()
        assert engine.last_trace is None
        engine.infer(pos=0.2, dpos=0.0, err=0.5, tv=0.1)
        assert engine.last_trace is not None

    def test_dispatcher_last_trace_delegates_to_engine(self):
        dispatcher = FuzzyEngineV2Dispatcher(ControlObjective.DISTURBANCE_REJECTION)
        assert dispatcher.last_trace is None
        dispatcher.engine.infer(e_max=0.5, t_rec=2.0, osc=0.1)
        assert dispatcher.last_trace is not None
        assert dispatcher.last_trace is dispatcher.engine.last_trace


class TestDomainSaturationGuard:
    """MF_*_DR MFSets pin an unbounded upper tail to a huge sentinel
    (_RIGHT_SAT = 1e9 in fuzzy_engine_v2.py); the router must exclude it
    from domain_max or the plot collapses to a vertical line."""

    def test_mfset_domain_excludes_right_sat_plateau(self):
        domain_min, domain_max = _mfset_domain(MF_E_MAX_DR)
        assert domain_min == pytest.approx(0.0)
        assert domain_max == pytest.approx(1.0)
        assert domain_max < 1.0e6

    def test_disturbance_rejection_trace_domains_are_finite(self):
        engine = FuzzyEngineV2DisturbanceRejection()
        engine.infer(e_max=1.5, t_rec=13.2, osc=0.42)
        trace = engine.last_trace
        assert trace is not None
        for name in ("e_max", "t_rec", "osc"):
            lo, hi = _mfset_domain(trace.mfsets[name])
            assert hi < 1.0e6, f"{name}: domain_max={hi} not saturation-guarded"
            assert hi > lo

        resp = _fuzzy_trace_response(1, ControlObjective.DISTURBANCE_REJECTION, trace)
        for input_trace in resp.inputs:
            assert input_trace.domain_max < 1.0e6
            assert input_trace.domain_min <= input_trace.value <= input_trace.domain_max
