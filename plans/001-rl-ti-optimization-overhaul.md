# Plan 001: Make the RL engine safely and effectively optimize the PID integral term (Ti/Ki)

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**:
> `git diff --stat b7fbcc3..HEAD -- packages/smart_pid_core/src/smart_pid_core/domain/services/rl_engine.py packages/smart_pid_core/src/smart_pid_core/application/workers/ai_worker.py tests/core/unit/test_rl_engine.py`
> If any of these files changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: L
- **Risk**: MED (touches the live loop-tuning path; mitigations: fallback policy preserved, clamps unchanged, conservative gating before the neural policy is allowed to act)
- **Depends on**: none
- **Category**: bug + perf (control performance)
- **Planned at**: commit `b7fbcc3`, 2026-07-28

## STATUS UPDATE (2026-07-28, post-execution)

**Executed and reviewed.** Implementation committed at `56f132c` on branch
`advisor/001-rl-ti-optimization` in worktree
`.worktrees/advisor-001-rl-ti-optimization` (created from `b7fbcc3` on the
now-superseded `feat/windows-installers` line — see note below). Reviewed
by the advisor: scope exactly 4 in-scope files, 65/65 RL unit tests pass
independently re-run, ruff 0 errors in changed files, mypy 23 errors vs 32
baseline (improved), all grep-based done criteria independently confirmed.
See `plans/README.md` for the full verdict and E2E validation status.

**Note on repo state**: this file was recreated verbatim after the main
working tree was switched to `main` (commit `ef6a41f`, "complete web
frontend rewrite" merge) by work outside this session, which removed the
untracked `plans/` directory as a side effect. Content below is unchanged
from the original — restored from this session's own record of what was
written. The implementation worktree (`advisor/001-rl-ti-optimization`,
based on the old `feat/windows-installers` tip `b7fbcc3`) was unaffected
and remains intact; its diff applies cleanly regardless of what the main
branch tip is, since it touches only `rl_engine.py`, `ai_worker.py`,
`test_rl_engine.py`, and `CLAUDE.md`, none of which are part of the web
frontend rewrite.

## Why this matters

Smart PID's RL engine exists to adjust the PID integral term online (Ti when
`integral_type=TIME_TI`, Ki when `GAIN_KI`) so each loop converges to good
performance without manual retuning. Today that promise is broken in three
independent ways:

1. **The neural policy can never train successfully, and the failure makes it
   *worse* than doing nothing.** `RLEngine._train_sac()` calls
   `model.train(...)` directly. stable-baselines3 (`>=2.3`) never assigns
   `self._logger` in `BaseAlgorithm.__init__` — it is only assigned inside
   `set_logger()` or `_setup_learn()` (which only `learn()` calls). So the
   first `train()` call raises `AttributeError` on the `self.logger` property,
   the exception is swallowed at DEBUG level in `_try_online_train()`, **but
   `self._model` has already been created by `_init_sb3_model()`** — so from
   that step onward `compute_gamma()` takes actions from a *randomly
   initialized, never-trained* SAC network instead of the sensible fallback
   heuristic. Ti then random-walks at ±Sv% per AI cycle, bounded only by
   `limit_min`/`limit_max`.
2. **The reward signal is a point sample, not loop performance.** Reward is
   computed from one instantaneous `(error, delta_error, co)` sample every AI
   period (3×TSS seconds). Everything that happens between decisions —
   oscillation, valve travel, IAE — is invisible (aliasing). Meanwhile the
   AIWorker already receives windowed KPIs (IAE, oscillation score, total
   variation, …) from the StatsWorker in `self._latest_stats` and uses them
   for the Fuzzy engine, but never passes them to the RL engine.
3. **Assorted correctness bugs**: cross-loop shared state in the surge-level
   reward (function attribute shared by all controllers/threads), an
   observation vector that omits the very parameter being actuated (Ti) —
   breaking the Markov property, an invalid PPO training path (dead code:
   `AIWorker` hardcodes SAC), the `rl_learning_rate` config field silently
   ignored, and RL state written to disk on *every* AI cycle.

After this plan lands: the SAC policy trains without error, is only allowed to
drive Ti after it has demonstrably trained, learns from windowed loop KPIs
instead of aliased point samples, and each fix is pinned by a unit test that
runs without stable-baselines3 installed.

## Current state

### Architecture (how the integral term is adjusted end-to-end)

```
TELEMETRY.{cid} ─► AIWorker (thread, every 3×TSS s, only AUTO/CAS/RCAS modes)
                      │  ai_worker.py:263-278 calls RLEngine.compute_gamma(...)
                      ▼
                 AIDecision(gamma, new_ki, reasoning)
                      │  published as ACTION.AI.{cid} + LOG.AI.{cid}
                      ▼
      DDC loops: pid_worker.py:533-551 → pid_params.reset = new_ki
      SUPERVISORY loops: io_worker.py:237-265 → opcua.write_pid_params(ti=new_ki)
```

- `new_ki` holds the **integral term value** — Ti (integral time) or Ki
  (integral gain) depending on `Controller.integral_type`. `PIDParams.reset`
  is Ti in seconds/repeat (`packages/smart_pid_domain/src/smart_pid_domain/models/controller.py:47`).
- Update law (`rl_engine.py:485-488`): `new_val = ki_current * (1 + effective_gamma * Sv)`,
  where `effective_gamma = gamma` for GAIN_KI and `-gamma` for TIME_TI, `Sv`
  is `ProcessSpeed.speed_factor` (0.08–0.50), clamped to
  `[ai_config.limit_min, ai_config.limit_max]`. **Do not change this law or
  the clamps** — the Fuzzy engine and the web UI share these semantics.

### Relevant files

- `packages/smart_pid_core/src/smart_pid_core/domain/services/rl_engine.py`
  (785 lines) — everything RL: reward functions (module level, lines 54–182),
  `_FallbackPolicy` (185–272), `RLEngine` (275–779). Pure domain service;
  sb3/gymnasium/numpy imported lazily only.
- `packages/smart_pid_core/src/smart_pid_core/application/workers/ai_worker.py`
  — per-controller worker thread; creates the engine (79–108), calls it
  (263–278), publishes results (284–314), persists RL state every cycle (317),
  drains `STATS.{cid}` into `self._latest_stats` (439–455).
- `packages/smart_pid_core/src/smart_pid_core/application/workers/stats_worker.py:86-108`
  — the STATS payload dict (consumed already by the Fuzzy path).
- `tests/core/unit/test_rl_engine.py` (614 lines) — unit tests, all designed
  to run **without** stable-baselines3 installed.

### Key excerpts (as of b7fbcc3)

`rl_engine.py:449-458` — the model-vs-fallback branch (no quality gate,
deterministic):

```python
        # Get action from model or fallback
        if self._model is not None:
            import numpy as np

            obs_array = np.array(observation, dtype=np.float32)
            action, _ = self._model.predict(obs_array, deterministic=True)
```

`rl_engine.py:524-531` — training failure swallowed at DEBUG:

```python
    def _try_online_train(self) -> None:
        """Attempt online training with collected experience."""
        if not self._check_sb3():
            return

        try:
            self._online_train_sb3()
        except Exception:
            logger.debug("rl_online_train_failed", exc_info=True)
```

`rl_engine.py` `_online_train_sb3` (lines 533–556) — initializes the model
*before* training can succeed, and never calls `set_logger`:

```python
        if self._model is None:
            self._init_sb3_model()
        ...
        if self._algorithm == "SAC":
            self._train_sac(buffer_list, np)
        else:
            self._train_ppo(buffer_list, np)
        self._is_trained = True
```

`rl_engine.py:643-660` — hardcoded learning rate (AIConfig.rl_learning_rate
exists but is never wired in):

```python
                self._model = SAC(
                    "MlpPolicy",
                    env,
                    learning_rate=3e-4,
                    buffer_size=10_000,
                    batch_size=self._train_batch_size,
                    verbose=0,
                )
```

`rl_engine.py:160-172` — surge reward stores state on the **module-level
function object**, shared by every controller and thread in the process:

```python
    stability = 0.0
    if prev_co is not None:
        co_change = abs(co - prev_co) / 100.0
        stability = 1.5 * math.exp(-8.0 * co_change)
        if hasattr(compute_reward_surge_level, "_prev_delta_co"):
            prev_delta = compute_reward_surge_level._prev_delta_co
            curr_delta = co - prev_co
            if prev_delta * curr_delta < 0:  # sign changed = reversal
                stability -= 0.5
        compute_reward_surge_level._prev_delta_co = co - prev_co
```

`rl_engine.py:343-360` — observation is `[error, delta_error, co, integral_val]`
normalized to [-1, 1]; the current Ti/Ki value is **not** in the observation,
so identical observations produce wildly different Ti outcomes depending on
the current Ti (non-Markov).

`ai_worker.py:99-107` — engine creation pokes privates and drops
`rl_learning_rate`:

```python
        elif self._ai_config.engine == AIEngine.RL:
            from smart_pid_core.domain.services.rl_engine import RLEngine

            engine = RLEngine(algorithm="SAC")
            # Apply per-controller RL config from ai_config
            engine._fallback._kp = self._ai_config.rl_fallback_kp
            engine._fallback._kd = self._ai_config.rl_fallback_kd
            engine._train_interval = self._ai_config.rl_train_interval
            return engine
```

`ai_worker.py:263-278` — the RL call site (note `self._latest_stats` is
available on the instance but not passed):

```python
                    decision = self._engine.compute_gamma(
                        error=error,
                        delta_error=delta_error,
                        ki_current=self._ki_current,
                        span=self._controller.pv_scale.span,
                        co=self._last_co,
                        integral_val=self._last_integral,
                        objective=self._ai_config.objective,
                        speed=self._controller.process_speed,
                        limit_min=self._ai_config.limit_min,
                        limit_max=self._ai_config.limit_max,
                        integral_type=self._integral_type,
                    )
```

`ai_worker.py:316-317` — state persisted after **every** AI cycle:

```python
                # Persist RL state after each AI cycle
                self._save_rl_state()
```

`stats_worker.py:86-108` — the STATS payload the AIWorker already caches in
`self._latest_stats` (all floats; error stats in engineering units, CO stats
in % of output):

```python
        return {
            "controller_id": self.controller_id,
            "iae": calc.iae, "itae": calc.itae, "ise": calc.ise,
            "mse": calc.mse, "std_dev": calc.std_dev,
            "total_variation": calc.total_variation,
            "variability_sp": calc.variability_sp,
            "variability_range": calc.variability_range,
            "mean_abs_error": calc.mean_abs_error,
            "pk_pk_error": calc.pk_pk_error,
            "reversals": calc.reversals,
            "zero_crossings": calc.zero_crossings,
            "recent_pk_pk_error": calc.recent_pk_pk_error,
            "recent_reversals": calc.recent_reversals,
            "tv_per_sample": calc.tv_per_sample,
            "osc": calc.osc_score(),
            "sample_count": calc.sample_count,
        }
```

`osc` is a 0..1 oscillation score; `tv_per_sample` is mean |ΔCO| per sample in
% of output span; `mean_abs_error` is in engineering units (divide by span).

### Facts about the environment

- stable-baselines3 is an **optional extra** (`packages/smart_pid_core/pyproject.toml:40-43`,
  extra name `ai`) and is NOT installed by the default `uv sync --all-packages`.
  In the current dev venv `import stable_baselines3` fails. All existing unit
  tests, and all tests you add, MUST pass without sb3 installed.
- sb3 fact used by Step 6 (verified against DLR-RM/stable-baselines3 source,
  `stable_baselines3/common/base_class.py`): `BaseAlgorithm.__init__` declares
  `_logger: Logger` as a class annotation but never assigns it; `set_logger()`
  and `_setup_learn()` are the only assignment sites; the `logger` property
  does a bare `return self._logger`. Therefore calling `model.train(...)`
  without a prior `model.set_logger(...)` raises `AttributeError`. The fix is
  `from stable_baselines3.common.utils import configure_logger` then
  `model.set_logger(configure_logger(verbose=0))` right after constructing
  the model.
- `AIWorker` hardcodes `RLEngine(algorithm="SAC")` — the PPO branches in
  `rl_engine.py` (`_train_ppo`, PPO imports in `_init_sb3_model`/`load_model`)
  are unreachable in production. The PPO training code is also mathematically
  invalid (fills an on-policy RolloutBuffer with off-policy transitions and
  `log_prob=0.0`), so it must be deleted, not fixed.
- Wire contract that MUST NOT change: `AIDecision` fields
  (`gamma`, `new_ki`, `reasoning`, `membership_values`) and the ACTION.AI /
  LOG.AI msgpack payload keys built in `ai_worker.py:285-314`. Nothing in the
  REST API reads RLEngine internals (verified: no references in
  `adapters/inbound/api/routers/ai.py`).

### Repo conventions to match

- Python 3.13, Ruff line-length 100, mypy strict, hexagonal: `domain/` never
  imports from `application/` or `adapters/` — `rl_engine.py` must stay a pure
  domain service with lazy sb3/numpy imports inside methods.
- Frozen dataclasses for decision objects (see `AIDecision`, `AIDecisionV2` in
  `fuzzy_engine_v2.py:107-113`).
- Tests: plain pytest classes grouped by behavior (see
  `tests/core/unit/test_rl_engine.py` class structure: `TestRLEngineInit`,
  `TestFallbackPolicy`, `TestRewardFunctions`, …). Match that structure.
- Reasoning strings follow the Fuzzy pattern of embedding the parameter
  transition, e.g. `"Ti: 10.0000 -> 9.5500"` (see `rl_engine.py:490-493` and
  `fuzzy_engine_v2.py:353-357`). Keep that format — the web UI displays it.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Sync deps (no sb3) | `uv sync --all-packages` | exit 0 |
| RL unit tests | `uv run pytest tests/core/unit/test_rl_engine.py -v` | all pass |
| Full test suite | `uv run pytest tests/ -v` | all pass |
| Lint | `uv run --with ruff ruff check packages/smart_pid_core tests` | exit 0 |
| Typecheck (scoped) | `uv run mypy packages/smart_pid_core/src/smart_pid_core/domain/services/rl_engine.py packages/smart_pid_core/src/smart_pid_core/application/workers/ai_worker.py` | no NEW errors vs baseline (record baseline before Step 1) |

Note (Flatpak VS Code environments): the `uv` binary may live at
`/home/luciano/.var/app/com.visualstudio.code/bin/uv`.

## Scope

**In scope** (the only files you should modify):

- `packages/smart_pid_core/src/smart_pid_core/domain/services/rl_engine.py`
- `packages/smart_pid_core/src/smart_pid_core/application/workers/ai_worker.py`
- `tests/core/unit/test_rl_engine.py`
- `tests/core/unit/test_ai_worker.py` — only if it exists and only where a
  changed constructor signature breaks it
- `CLAUDE.md` — the "RL Engine (Phase 5)" section only (Step 9)

**Out of scope** (do NOT touch, even though they look related):

- `fuzzy_engine_v2.py`, `pid_engine.py`, `pid_worker.py`, `io_worker.py`,
  `stats_worker.py`, `stats_calculator.py` — consumers/peers; contracts stay.
- `smart_pid_domain` package — no new enums/fields. `AIConfig` already has
  every knob this plan needs.
- The ACTION.AI / LOG.AI payload shape, `AIDecision` field set, and the
  Ki/Ti update law `ki * (1 + effective_gamma * Sv)` with its clamps.
- The web frontend (`smart_pid_web`) and REST API routers.
- `pyproject.toml` files — the `ai` extra stays optional.

## Git workflow

- Branch: `advisor/001-rl-ti-optimization` from current HEAD.
- Conventional commits, one per step or logical unit, scope `core`, e.g.
  `fix(core): isolate surge-level reward state per RLEngine instance`
  (matches history: `fix(core): fall back to signal.signal on Windows…`).
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 0: Baseline

Run, and record output for later comparison:

1. `uv sync --all-packages`
2. `uv run pytest tests/core/unit/test_rl_engine.py -v` → note the pass count (all pass).
3. The scoped mypy command from the table → save its error list (may be non-empty; that is the baseline).

**Verify**: both commands exit as expected; baseline recorded in your notes.

### Step 1: Delete the PPO path

In `rl_engine.py`:

- Delete `_train_ppo` entirely.
- In `_online_train_sb3` (lines 533–556): remove the `if self._algorithm == "SAC" … else _train_ppo` branch; call `self._train_sac(...)` unconditionally.
- In `_init_sb3_model` (608–663): remove the PPO branch; keep only SAC.
- In `load_model` (675–693): remove the PPO branch.
- In `__init__`: coerce unknown algorithms —
  `if algorithm != "SAC": logger.warning("rl_unsupported_algorithm %s, using SAC", algorithm); algorithm = "SAC"`.
- If any test in `test_rl_engine.py` references PPO, delete or update it to SAC.

**Verify**: `grep -n "PPO\|_train_ppo\|rollout" packages/smart_pid_core/src/smart_pid_core/domain/services/rl_engine.py` → no matches. RL unit tests pass.

### Step 2: Fix the surge-level shared-state bug

In `rl_engine.py`:

- Change `compute_reward_surge_level` signature to
  `(error, delta_error, co, prev_co, step, prev_delta_co: float | None = None) -> float`.
  Replace the `hasattr(compute_reward_surge_level, "_prev_delta_co")` block
  with a plain read of the `prev_delta_co` parameter (reversal penalty when
  `prev_delta_co * (co - prev_co) < 0`). The function becomes pure.
- Add `self._prev_delta_co: float | None = None` to `RLEngine.__init__`; in
  `RLEngine.compute_reward` pass it to the surge function and afterwards
  update it: `if self._prev_co is not None: self._prev_delta_co = co - self._prev_co`.
  Reset it in `RLEngine.reset()`.
- Update the surge-level tests in `TestRewardFunctions` to pass
  `prev_delta_co` explicitly, and add one test proving two `RLEngine`
  instances no longer contaminate each other (construct two engines, drive
  reversals through one, assert the other's surge reward is unaffected).

**Verify**: `grep -n "_prev_delta_co" packages/smart_pid_core/src/smart_pid_core/domain/services/rl_engine.py` → only instance-attribute uses (`self._prev_delta_co`), no function-attribute writes. RL unit tests pass.

### Step 3: Make time-escalation event-relative

Currently `compute_reward` passes the lifetime `self._step_count` as `step`
into the sp-tracking/DR reward functions; their time weights
(`min(1 + step*0.02, 3)` at line ~72, `min((step+1)*0.03, 5)` at ~127) hit
their caps within the first ~170 cycles of the process lifetime and stay
maxed forever — "ITAE escalation" degenerates into a constant.

In `RLEngine`:

- Add `self._steps_in_error = 0` to `__init__` and `reset()`.
- In `compute_gamma`, after computing the normalized observation: if
  `abs(observation[0]) >= 0.01` increment `self._steps_in_error`, else reset
  it to 0.
- In `compute_reward`, pass `self._steps_in_error` (not `self._step_count`)
  as the `step` argument to the reward functions. Leave the reward-function
  bodies unchanged.

Add a test: drive `compute_gamma` with a large error for 5 cycles, then a
near-zero error for 1 cycle, then large again — assert (via
`engine._steps_in_error`) the counter reset at the near-zero step.

**Verify**: RL unit tests pass, including the new one.

### Step 4: Add the actuated parameter to the observation (Markov fix)

In `rl_engine.py`:

- Change `OBS_DIM` from 4 to 5.
- Extend `_normalize_observation` with two parameters: `ki_current: float`,
  `limit_min: float`, `limit_max: float` (callers have all three). Compute a
  log-scale position of the integral parameter inside its allowed band:

  ```python
  if limit_min > 0 and limit_max > limit_min:
      ratio = math.log(max(ki_current, limit_min) / limit_min)
      ti_norm = 2.0 * ratio / math.log(limit_max / limit_min) - 1.0
      ti_norm = max(-1.0, min(1.0, ti_norm))
  else:
      ti_norm = 0.0
  ```

  Append `ti_norm` as the 5th element. Log scale because the band is
  multiplicative (defaults 0.1–100 = 3 decades) and the action is
  multiplicative.
- Update the module docstring comment at lines 31–33 to describe the 5-dim
  observation.
- **Stale-model guard**: in `compute_gamma`, wrap the
  `self._model.predict(...)` call in `try/except Exception`; on failure, log
  `logger.warning("rl_model_predict_failed — discarding model", exc_info=True)`,
  set `self._model = None`, and fall through to the fallback policy for this
  and subsequent steps. This protects against a persisted 4-dim model being
  loaded against the new 5-dim observation space (and any future shape drift).
- Update `TestObservationNormalization` for the new signature and 5th element
  (existing assertions like `obs[3] == pytest.approx(0.5)` for
  `integral_val=50` stay valid — index 3 is unchanged). Add cases:
  `ki_current == limit_min` → `obs[4] == -1.0`; `ki_current == limit_max` →
  `obs[4] == 1.0`; geometric midpoint (`sqrt(limit_min*limit_max)`) →
  `obs[4] == pytest.approx(0.0)`; `limit_min == 0` → `obs[4] == 0.0`.
- Add a test for the predict guard: set `engine._model` to a stub object
  whose `predict` raises `ValueError`; call `compute_gamma`; assert the
  decision is produced (fallback), and `engine._model is None` afterwards.

**Verify**: RL unit tests pass. `grep -n "OBS_DIM = 5" …/rl_engine.py` → one match.

### Step 5: Reward from windowed loop KPIs (with versioned state)

This is the core performance change: reward the agent for what the loop did
over the whole interval since its last action, not for one sample.

In `rl_engine.py`:

1. Add a module-level function (near the other reward functions):

   ```python
   def compute_reward_from_stats(
       stats: dict,
       span: float,
       objective: ControlObjective,
   ) -> float | None:
       """Windowed reward from StatsWorker KPIs. None when stats unusable."""
   ```

   Behavior:
   - Return `None` if `stats.get("sample_count", 0) < 10` or `span <= 0`
     (caller falls back to the instantaneous reward).
   - Normalize: `mae_n = stats["mean_abs_error"] / span`,
     `osc = stats["osc"]` (already 0..1), `tv_s = stats["tv_per_sample"] / 100.0`,
     `pkpk_n = stats.get("recent_pk_pk_error", 0.0) / span`. Use `.get(key, 0.0)`
     for every stats key — payloads may predate newer fields.
   - Per objective (import `ControlObjective` lazily inside, matching
     `compute_reward`'s existing style):
     - `SP_TRACKING`: `r = -2.0*mae_n - 0.8*osc - 0.3*tv_s + (0.5 if mae_n < 0.005 else 0.0)`
     - `DISTURBANCE_REJECTION`: `r = -2.5*mae_n - 1.0*osc - 0.1*tv_s + (0.5 if mae_n < 0.005 else 0.0)`
     - `SURGE_LEVEL`: `excess = max(0.0, mae_n - 0.02)` (2% deadband, same
       constant as `_SURGE_DEADBAND`); `r = 1.5*math.exp(-8.0*tv_s) - 3.0*excess*excess - 0.3*osc`
   - Clamp the result to `[-5.0, 2.0]` so reward scale stays comparable to the
     instantaneous functions already in the replay buffer design.
   - These weights are initial engineering estimates mirroring the intent
     table at `rl_engine.py:41-47`; keep them as named local constants with a
     one-line comment each.

2. Add `stats: dict | None = None` as a keyword parameter to `compute_gamma`.
   In the reward block (currently lines 437–447): first try
   `compute_reward_from_stats(stats, span, objective)` when `stats` is not
   `None`; if it returns `None`, use the existing `self.compute_reward(...)`
   path unchanged.

3. **Version the persisted state** (reward scale and OBS_DIM changed, so old
   replay buffers and models would poison training):
   - `save_state`: add `"version": 2` to the returned dict.
   - `load_state`: if `state.get("version") != 2`, log
     `logger.info("rl_state_version_mismatch — discarding persisted RL state")`
     and return immediately (fresh start; counters, buffer, model all reset).

In `ai_worker.py`, RL branch (lines 263–278): pass `stats=self._latest_stats`
to `compute_gamma`.

Tests (new class `TestStatsReward`):
- Each objective: build a stats dict (e.g. span=100, `mean_abs_error=5.0`,
  `osc=0.4`, `tv_per_sample=2.0`, `sample_count=50`) and assert a *worse* dict
  (higher mae/osc/tv) yields strictly lower reward than a better one.
- `sample_count=5` → returns `None`.
- `span=0` → returns `None`.
- `compute_gamma(..., stats=good_stats)` populates the replay buffer using the
  stats reward (assert reward value in `engine._replay_buffer[-1][2]` matches
  `compute_reward_from_stats` output for the same inputs).
- `load_state` with a version-1 dict (no `"version"` key, non-empty
  `replay_buffer`) leaves the engine's buffer empty.

**Verify**: RL unit tests pass, including the new class.

### Step 6: Fix online training and gate the neural policy

In `rl_engine.py`:

1. `__init__` gains keyword parameters (with defaults preserving current
   behavior): `learning_rate: float = 3e-4`, `fallback_kp: float = 0.6`,
   `fallback_kd: float = 0.2`, `train_interval: int = 32`. Use them:
   `self._fallback = _FallbackPolicy(kp=fallback_kp, kd=fallback_kd)`,
   `self._train_interval = train_interval`, `self._learning_rate = learning_rate`.
   Also add `self._train_success_count = 0` and `self._train_fail_logged = False`.
2. `_init_sb3_model`: use `learning_rate=self._learning_rate`, and immediately
   after constructing the SAC model:

   ```python
   from stable_baselines3.common.utils import configure_logger
   self._model.set_logger(configure_logger(verbose=0))
   ```

   (This is the documented sb3 requirement for calling `train()` outside
   `learn()`; without it the first `train()` raises `AttributeError` on the
   unset `_logger`.)
3. `_online_train_sb3`: after `self._train_sac(...)` succeeds, increment
   `self._train_success_count` (keep `self._is_trained = True`).
4. `_try_online_train`: on exception, log at WARNING the first time
   (`if not self._train_fail_logged: logger.warning("rl_online_train_failed", exc_info=True); self._train_fail_logged = True`),
   DEBUG afterwards. Silent-at-DEBUG-forever is what hid this bug.
5. **Policy gate** in `compute_gamma`: replace the branch condition
   `if self._model is not None:` with `if self._policy_ready():` where:

   ```python
   _MIN_TRAINS_BEFORE_POLICY = 3

   def _policy_ready(self) -> bool:
       """Neural policy may act only after real training has happened."""
       return self._model is not None and (
           self._train_success_count >= self._MIN_TRAINS_BEFORE_POLICY
           or (self._is_trained and self._train_success_count == 0)  # loaded from disk
       )
   ```

   The second clause covers models restored by `load_model`/`load_state`
   (v2 states only, per Step 5) — those were already trained in a previous
   run. An initialized-but-untrained model must never drive the loop.
6. Exploration: change `deterministic=True` to `deterministic=False` in the
   `predict` call. SAC's squashed-Gaussian policy is bounded in [-1, 1], the
   gamma is additionally clamped, and Sv (≤0.5) plus the limit clamps bound
   the per-cycle Ti change — stochastic actions are safe here and are what
   makes the collected experience informative. Append `trained={n}` (the
   success count) to the RL reasoning string so operators can see policy
   maturity in the AI log.

In `ai_worker.py` `_create_engine` (lines 99–107): construct via the new
parameters and stop poking privates:

```python
engine = RLEngine(
    algorithm="SAC",
    learning_rate=self._ai_config.rl_learning_rate,
    fallback_kp=self._ai_config.rl_fallback_kp,
    fallback_kd=self._ai_config.rl_fallback_kd,
    train_interval=self._ai_config.rl_train_interval,
)
```

Tests (new class `TestPolicyGate`, no sb3 required — use stubs):
- Engine with `_model` set to a stub whose `predict` returns `[0.5]`, and
  `_train_success_count = 0`, `_is_trained = False` → `compute_gamma` uses the
  fallback (reasoning starts with `"RL(fallback)"`).
- Same stub with `_train_success_count = 3` → reasoning starts with `"RL(SAC)"`.
- Stub with `_is_trained = True`, `_train_success_count = 0` (loaded-model
  case) → model used.
- Constructor params propagate: `RLEngine(fallback_kp=0.9, train_interval=7)`
  → `engine._fallback._kp == 0.9`, `engine._train_interval == 7`.
- `_try_online_train` failure path: monkeypatch `_online_train_sb3` to raise,
  call twice via forced conditions, assert one WARNING then DEBUG (use
  `caplog`).

**Verify**: RL unit tests pass. `grep -n "deterministic=True" …/rl_engine.py` → no matches. `grep -n "engine._fallback._kp" …/ai_worker.py` → no matches.

### Step 7: Stop writing RL state on every cycle

In `ai_worker.py`:

- Add `self._cycles_since_save = 0` in `__init__`.
- Replace the unconditional `self._save_rl_state()` at line 316–317 with:
  save only every 10th cycle (`self._cycles_since_save >= 10` → save and
  reset the counter). `stop()` already saves unconditionally (line 133) —
  keep that; it covers shutdown.

**Verify**: `uv run pytest tests/ -v -k ai_worker` → pass (if AI-worker tests
exist); full RL unit tests pass.

### Step 8: Full-suite gates

1. `uv run pytest tests/ -v` → all pass.
2. `uv run --with ruff ruff check packages/smart_pid_core tests` → exit 0.
3. Scoped mypy command → no NEW errors vs the Step 0 baseline.
4. Optional (only if the operator wants live proof and allows installing the
   extra in a scratch venv): `uv sync --all-packages --extra ai`, then run the
   backend with the simulator and an RL loop configured; expect
   `rl_model_initialized`, no `rl_online_train_failed`, and
   `rl_online_train algo=SAC` DEBUG lines after ~128+32 AI cycles. This is a
   smoke check, not a gate — do not leave the extra installed unless asked.

### Step 9: Documentation

- `CLAUDE.md`, section "RL Engine (Phase 5 — otimizacao de Ki via
  Reinforcement Learning)" (lines 93–103): update to state — SAC only (PPO
  removed); observation is 5-dim `[error, delta_error, CO, integral_val,
  ti_norm]`; reward comes from StatsWorker window KPIs when available with
  instantaneous fallback; the neural policy only acts after 3 successful
  online training rounds (fallback P+D heuristic before that); sb3 is the
  optional `ai` extra — without it the fallback heuristic runs and a WARNING
  is logged… **only add the warning claim if you implemented it** (it is NOT
  part of this plan's steps; do not implement extra behavior for the doc).
- Append a short completion summary to `.claude/docs/estado-atual.md`
  (repo rule: what was done, decisions, files touched).
- Update this plan's row in `plans/README.md` to DONE.

**Verify**: `grep -n "PPO" CLAUDE.md` → no stale claim that PPO is supported.

## Test plan

All in `tests/core/unit/test_rl_engine.py`, all runnable **without** sb3,
modeled structurally on the existing classes there:

- `TestRewardFunctions` (updated): surge signature with explicit
  `prev_delta_co`; cross-engine isolation test.
- `TestStatsReward` (new): per-objective ordering, `None` on short window /
  zero span, replay-buffer wiring, v1-state discard.
- `TestPolicyGate` (new): untrained-model blocked, trained/loaded allowed,
  constructor param propagation, WARNING-once on train failure.
- `TestObservationNormalization` (updated): 5th element bounds/midpoint,
  predict-failure guard discards model.
- Steps-in-error reset test (Step 3).
- Everything in the existing file must still pass (the fallback-policy and
  speed-factor tests pin behavior this plan must not change).

Verification: `uv run pytest tests/core/unit/test_rl_engine.py -v` → all pass,
including ≥10 new tests.

## Done criteria

Machine-checkable. ALL must hold:

- [x] `uv run pytest tests/ -v` exits 0 — **DEVIATION, documented**: 37
      pre-existing failures + 3 errors confirmed via baseline comparison
      (none touch scope files; see plans/README.md verdict).
- [x] `uv run --with ruff ruff check packages/smart_pid_core tests` exits 0
      on the 4 changed files (0 errors); 14 pre-existing errors elsewhere,
      unrelated to this change.
- [x] Scoped mypy: 23 errors vs 32 baseline — improved, no new errors.
- [x] `grep -rn "PPO" packages/smart_pid_core/src/smart_pid_core/domain/services/rl_engine.py` → no matches
- [x] `grep -n "compute_reward_surge_level._prev_delta_co" packages/smart_pid_core/src/smart_pid_core/domain/services/rl_engine.py` → no matches
- [x] `grep -n "deterministic=True" packages/smart_pid_core/src/smart_pid_core/domain/services/rl_engine.py` → no matches
- [x] `grep -n "set_logger" packages/smart_pid_core/src/smart_pid_core/domain/services/rl_engine.py` → ≥1 match
- [x] `grep -n "stats=self._latest_stats" packages/smart_pid_core/src/smart_pid_core/application/workers/ai_worker.py` → 2 matches (1 pre-existing Fuzzy call, 1 new RL wiring — both legitimate)
- [x] `grep -n '"version": 2' packages/smart_pid_core/src/smart_pid_core/domain/services/rl_engine.py` → 1 match
- [x] `git status` shows no modified files outside the in-scope list (in the implementation worktree)
- [ ] `plans/README.md` status row updated — pending final E2E sign-off

## STOP conditions

Stop and report back (do not improvise) if:

- The drift check shows `rl_engine.py`, `ai_worker.py`, or
  `test_rl_engine.py` diverged from the excerpts above.
- Any existing test that pins the Ki/Ti update law, speed factors, or
  fallback-policy behavior fails and the fix would require changing that
  behavior (they are contracts, not collateral).
- You find a consumer of `ACTION.AI` / `LOG.AI` that reads a field this plan
  would alter — the payload shape must not change.
- Making unit tests pass appears to require stable-baselines3 installed —
  the design requires sb3-free tests; needing sb3 means a lazy-import
  boundary was broken.
- The scoped mypy run shows new errors you cannot resolve without touching
  out-of-scope files.

## Maintenance notes

- **Reward weights** in `compute_reward_from_stats` are initial estimates.
  The right way to tune them later is against the simulator
  (`SPID_SIMULATOR_ENABLED`) comparing IAE/TV trajectories per objective —
  deferred deliberately; do not block this plan on weight optimality.
- **Policy-quality regression guard** (comparing model vs fallback average
  reward and auto-reverting) was considered and deferred — the gate + Sv
  bound + limit clamps are the safety envelope for now. Revisit if field data
  shows a trained policy degrading loops.
- If `StatsWorker` payload keys change, `compute_reward_from_stats` degrades
  gracefully via `.get(..., 0.0)` but silently — a reviewer touching
  `stats_worker.py` should re-check the key list here.
- If OBS_DIM changes again, the predict-guard (Step 4) plus state version
  bump is the established migration pattern.
- Reviewer focus: Step 6's gate logic (`_policy_ready`) and the Step 5 reward
  normalization (units: `mean_abs_error` EU vs span; `tv_per_sample` % CO).
