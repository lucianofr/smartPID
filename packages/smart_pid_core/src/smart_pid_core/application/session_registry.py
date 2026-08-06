"""In-memory registry of the sessions that are logged in RIGHT NOW.

The JWT is stateless on purpose (``resolve_token_principal``), so the server
has no session table to list. This registry is the missing live view: it is
fed by the two places every authenticated caller already passes through —
the REST dependency ``get_current_user`` and the realtime WebSocket
handshake — and answers "who is connected, from which IP".

Liveness has two independent sources, because neither alone is honest:

* an OPEN realtime socket (``attach``/``detach``). Every page mounts
  ``RealtimeProvider``, so a socket is the strongest "this browser is on
  screen" signal there is, and it drops within a second of the tab closing.
  The web client sends no heartbeat, so this is a refcount, not a timestamp;
* ``last_seen``, refreshed by any authenticated REST call. This is the only
  signal a socket-less client (curl, an integration) produces, hence the
  idle TTL below.

Deliberately NOT persisted: "logged in" is a property of the running process.
A restart ends every socket it was serving, so replaying entries from disk
would resurrect sessions that no longer exist.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

# A socket-less client is considered gone after this much silence. Sized above
# the slowest client poll (STATS_POLL_MS / STATUS_POLL_MS on the web) so a
# working session is never pruned between two of its own requests.
DEFAULT_IDLE_TTL = timedelta(minutes=5)


@dataclass
class ActiveSession:
    """One (user, source IP) pair currently using the platform."""

    user_id: int
    username: str
    role: str
    ip: str
    """First activity observed for this pair — reset by a fresh login."""
    since: datetime
    last_seen: datetime
    """Open realtime sockets. > 0 means live regardless of ``last_seen``."""
    sockets: int = 0


class SessionRegistry:
    """Live sessions keyed by ``(user_id, ip)``.

    Collapsing every tab of one user at one IP into a single entry is
    deliberate: the panel answers "who is on the platform, from where", and
    three tabs are one operator. The cost is that ``drop`` (an explicit
    logout) also clears a *different* browser of the same user behind the same
    NAT address; that session reappears on its next request.

    Single asyncio loop serves both the REST routes and the WebSocket, so the
    plain dict needs no lock.
    """

    def __init__(self, idle_ttl: timedelta = DEFAULT_IDLE_TTL) -> None:
        self._sessions: dict[tuple[int, str], ActiveSession] = {}
        self._idle_ttl: timedelta = idle_ttl

    def _prune(self, now: datetime) -> None:
        """Drop socket-less rows past the idle TTL.

        Runs on write as well as on read: pruning only in ``list_active``
        would mean the map shrinks only while an admin has the panel open, so
        a daemon nobody is watching would hold every (user, address) pair seen
        since boot.
        """
        for key, session in list(self._sessions.items()):
            if session.sockets <= 0 and now - session.last_seen > self._idle_ttl:
                del self._sessions[key]

    def touch(self, *, user_id: int, username: str, role: str, ip: str) -> ActiveSession:
        """Upsert the session and mark it active now."""
        now = datetime.now(tz=UTC)
        self._prune(now)
        key = (user_id, ip)
        session = self._sessions.get(key)
        if session is None:
            session = ActiveSession(
                user_id=user_id, username=username, role=role, ip=ip,
                since=now, last_seen=now,
            )
            self._sessions[key] = session
            return session
        # The stored role is refreshed from the user row on every request, so
        # a promotion/demotion mid-session shows up here too.
        session.username = username
        session.role = role
        session.last_seen = now
        return session

    def record_login(self, *, user_id: int, username: str, role: str, ip: str) -> None:
        """Start a session at ``POST /auth/login`` — resets ``since``."""
        session = self.touch(user_id=user_id, username=username, role=role, ip=ip)
        session.since = session.last_seen

    def attach(self, *, user_id: int, username: str, role: str, ip: str) -> ActiveSession:
        """Register an open realtime socket. Returns the row to hand ``detach``."""
        session = self.touch(user_id=user_id, username=username, role=role, ip=ip)
        session.sockets += 1
        return session

    def detach(self, session: ActiveSession) -> None:
        """Release a closed realtime socket; the row then ages out on TTL.

        Takes the object ``attach`` returned rather than re-looking it up by
        ``(user_id, ip)``. The key is not stable across time: an explicit
        logout ``drop``s it and the next request or socket recreates it, so a
        socket closing late would otherwise take its count off a DIFFERENT,
        genuinely live session — leaving an open tab reporting no socket and
        ageing out under the idle TTL. A stale detach now only touches its own
        orphaned row, which nothing reads.
        """
        session.sockets = max(0, session.sockets - 1)
        session.last_seen = datetime.now(tz=UTC)

    def drop(self, *, user_id: int, ip: str) -> None:
        """Forget the session immediately (explicit logout)."""
        self._sessions.pop((user_id, ip), None)

    def list_active(self) -> list[ActiveSession]:
        """Live sessions, most recently active first. Prunes what expired."""
        now = datetime.now(tz=UTC)
        self._prune(now)
        return sorted(self._sessions.values(), key=lambda s: s.last_seen, reverse=True)
