"""Runtime, set-based control over which log levels the daemon emits.

The daemon used to only support a single threshold (``SPID_LOG_LEVEL``): pick
INFO and everything at INFO or above floods the file sink; pick WARNING and
INFO diagnostics an operator still wants are gone too. ``LogLevelController``
replaces the threshold with an explicit set so an operator can, for example,
keep WARNING and ERROR while turning INFO off.
"""
from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Sequence

#: The five stdlib level names, ordered by increasing severity.
LOG_LEVEL_NAMES: tuple[str, ...] = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")

_LEVEL_NUMBERS: dict[str, int] = {name: getattr(logging, name) for name in LOG_LEVEL_NAMES}
_STANDARD_NUMBERS: tuple[int, ...] = tuple(_LEVEL_NUMBERS.values())


def _bucket_for(levelno: int) -> int:
    """Map a (possibly non-standard) level number to its enabled/disabled bucket.

    A library that defines an in-between level (e.g. 25) must still be
    controllable by the nearest standard checkbox rather than falling
    through every filter unnoticed, so it maps to the highest standard level
    at or below it. A level below DEBUG maps to DEBUG.
    """
    at_or_below = [lvl for lvl in _STANDARD_NUMBERS if lvl <= levelno]
    return max(at_or_below) if at_or_below else _STANDARD_NUMBERS[0]


def _normalize(names: Iterable[str]) -> tuple[str, ...]:
    """Uppercase, de-duplicate and severity-order *names*; reject unknown ones."""
    requested = {name.upper() for name in names}
    unknown = requested - set(LOG_LEVEL_NAMES)
    if unknown:
        raise ValueError(f"Unknown log level name(s): {', '.join(sorted(unknown))}")
    return tuple(name for name in LOG_LEVEL_NAMES if name in requested)


def _numbers_for(names: tuple[str, ...]) -> frozenset[int]:
    return frozenset(_LEVEL_NUMBERS[name] for name in names)


def _root_level_for(names: tuple[str, ...]) -> int:
    """Floor for the root logger: the minimum enabled level, or above CRITICAL
    when nothing is enabled so no record is even constructed.
    """
    if not names:
        return logging.CRITICAL + 1
    return min(_LEVEL_NUMBERS[name] for name in names)


def levels_at_or_above(threshold: int) -> tuple[str, ...]:
    """The standard level names whose numeric value is >= *threshold*.

    Used to derive the initial checkbox selection from the legacy
    ``SPID_LOG_LEVEL`` threshold, preserving today's behaviour until an
    operator makes an explicit choice.
    """
    return tuple(name for name in LOG_LEVEL_NAMES if _LEVEL_NUMBERS[name] >= threshold)


class LevelSetFilter(logging.Filter):
    """Passes a record only when its severity bucket is in the enabled set."""

    def __init__(self, enabled: frozenset[int]) -> None:
        super().__init__()
        self._enabled = enabled

    def update_enabled(self, enabled: frozenset[int]) -> None:
        """Atomically swap the enabled set (new object, never mutated in place)
        so a concurrent :meth:`filter` call never observes a half-built set.
        """
        self._enabled = enabled

    def filter(self, record: logging.LogRecord) -> bool:
        return _bucket_for(record.levelno) in self._enabled


class LogLevelController:
    """Owns the set of currently-enabled log levels and applies it live.

    One :class:`LevelSetFilter` is attached to every handler passed in, so a
    single selection applies identically to stdout and the rotating file
    sink. The selection is a SET, not a threshold: checking WARNING and
    ERROR without INFO emits exactly those two, not "WARNING and above".
    """

    def __init__(
        self,
        handlers: Sequence[logging.Handler],
        initial: Iterable[str],
        on_change: Callable[[tuple[str, ...]], None] | None = None,
    ) -> None:
        self._handlers = tuple(handlers)
        self._on_change = on_change
        self._levels = _normalize(initial)
        self._filter = LevelSetFilter(_numbers_for(self._levels))
        for handler in self._handlers:
            handler.addFilter(self._filter)
        logging.getLogger().setLevel(_root_level_for(self._levels))

    @property
    def levels(self) -> tuple[str, ...]:
        return self._levels

    def set_levels(self, names: Iterable[str]) -> tuple[str, ...]:
        """Replace the enabled set. Raises ``ValueError`` and leaves the
        previous selection intact when *names* contains an unknown level.
        """
        normalized = _normalize(names)
        self._filter.update_enabled(_numbers_for(normalized))
        self._levels = normalized
        logging.getLogger().setLevel(_root_level_for(normalized))
        if self._on_change is not None:
            self._on_change(normalized)
        return normalized
