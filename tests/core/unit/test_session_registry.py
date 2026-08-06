"""Liveness rules of the in-memory session registry.

Time is advanced by backdating ``last_seen`` on the returned dataclass rather
than by injecting a clock: it exercises the real ``datetime.now`` path and
keeps the registry's constructor free of test-only seams.
"""
from __future__ import annotations

from datetime import timedelta

from smart_pid_core.application.session_registry import SessionRegistry

_TTL = timedelta(minutes=5)


def _registry() -> SessionRegistry:
    return SessionRegistry(idle_ttl=_TTL)


def test_touch_creates_then_updates_one_row() -> None:
    reg = _registry()
    first = reg.touch(user_id=1, username="admin", role="admin", ip="10.0.0.1")
    started = first.since
    second = reg.touch(user_id=1, username="admin", role="admin", ip="10.0.0.1")

    assert second is first
    assert second.since == started, "since marks the start of the session, not the last hit"
    assert len(reg.list_active()) == 1


def test_same_user_from_two_addresses_is_two_sessions() -> None:
    reg = _registry()
    reg.touch(user_id=1, username="admin", role="admin", ip="10.0.0.1")
    reg.touch(user_id=1, username="admin", role="admin", ip="203.0.113.9")

    assert {s.ip for s in reg.list_active()} == {"10.0.0.1", "203.0.113.9"}


def test_touch_refreshes_a_role_changed_mid_session() -> None:
    reg = _registry()
    reg.touch(user_id=2, username="op", role="user", ip="10.0.0.2")
    reg.touch(user_id=2, username="op", role="admin", ip="10.0.0.2")

    assert [s.role for s in reg.list_active()] == ["admin"]


def test_idle_session_without_a_socket_expires() -> None:
    reg = _registry()
    session = reg.touch(user_id=1, username="admin", role="admin", ip="10.0.0.1")
    session.last_seen -= _TTL + timedelta(seconds=1)

    assert reg.list_active() == []


def test_open_socket_keeps_a_silent_session_alive() -> None:
    reg = _registry()
    session = reg.touch(user_id=1, username="admin", role="admin", ip="10.0.0.1")
    reg.attach(user_id=1, username="admin", role="admin", ip="10.0.0.1")
    # A tab that only receives WS frames issues no REST call for hours.
    session.last_seen -= _TTL * 100

    assert [s.username for s in reg.list_active()] == ["admin"]
    assert session.sockets == 1


def test_last_socket_closing_hands_the_session_back_to_the_idle_timer() -> None:
    reg = _registry()
    tabs = [reg.attach(user_id=1, username="admin", role="admin", ip="10.0.0.1") for _ in range(2)]
    reg.detach(tabs[0])

    assert len(reg.list_active()) == 1, "one of two tabs closed — still connected"

    reg.detach(tabs[1])
    session = reg.list_active()[0]
    assert session.sockets == 0
    session.last_seen -= _TTL + timedelta(seconds=1)
    assert reg.list_active() == []


def test_detach_never_drives_the_refcount_negative() -> None:
    # A double disconnect must not leave a session that can never expire.
    reg = _registry()
    session = reg.attach(user_id=1, username="admin", role="admin", ip="10.0.0.1")
    reg.detach(session)
    reg.detach(session)

    assert reg.list_active()[0].sockets == 0


def test_a_late_detach_cannot_disconnect_the_session_that_replaced_it() -> None:
    # Sign out and straight back in from the same browser: `drop` removes the
    # key, the new login recreates it, and only THEN does the old socket
    # finally close. Decrementing by key would take that socket off the new,
    # genuinely open session — which would then report no connection and age
    # out under the idle TTL with a live tab on screen.
    reg = _registry()
    old = reg.attach(user_id=1, username="admin", role="admin", ip="10.0.0.1")
    reg.drop(user_id=1, ip="10.0.0.1")
    fresh = reg.attach(user_id=1, username="admin", role="admin", ip="10.0.0.1")

    reg.detach(old)

    assert fresh.sockets == 1
    fresh.last_seen -= _TTL * 100
    assert [s.username for s in reg.list_active()] == ["admin"]


def test_drop_ends_the_session_immediately() -> None:
    reg = _registry()
    reg.attach(user_id=1, username="admin", role="admin", ip="10.0.0.1")
    reg.drop(user_id=1, ip="10.0.0.1")

    assert reg.list_active() == []


def test_record_login_restarts_the_session_clock() -> None:
    reg = _registry()
    session = reg.touch(user_id=1, username="admin", role="admin", ip="10.0.0.1")
    session.since -= timedelta(hours=3)
    reg.record_login(user_id=1, username="admin", role="admin", ip="10.0.0.1")

    assert session.since == session.last_seen


def test_list_active_is_ordered_by_most_recent_activity() -> None:
    reg = _registry()
    older = reg.touch(user_id=1, username="admin", role="admin", ip="10.0.0.1")
    reg.touch(user_id=2, username="op", role="user", ip="10.0.0.2")
    older.last_seen -= timedelta(minutes=1)

    assert [s.username for s in reg.list_active()] == ["op", "admin"]
