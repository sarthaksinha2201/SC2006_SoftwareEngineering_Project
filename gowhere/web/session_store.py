"""Server-side, in-memory session state.

The browser's cookie holds only an opaque random session id (in Flask's signed session).
Everything personal, above all the commute destination postal code and the Where to
Lepak starting point (Security NFR), stays
in this process's memory and expires with the session. Nothing here is written to disk.

The store is per process, so the app must run as a single process (threads are fine),
which matches DECISIONS.md section 4: one always-on host.
"""
import secrets
import threading
import time

from gowhere.scoring.commute import CommuteRouter

SESSION_TTL_S = 2 * 60 * 60
MAX_SESSIONS = 5000


class SessionState:
    def __init__(self, router):
        self.router = router            # this session's CommuteRouter (route cache)
        self.last_request = None        # the most recent Where to Live form, parsed
        # Where to Lepak, created on first use: this session's postal-code lookups, its
        # event router, and its last search (starting point, form and results).
        self.locations = None
        self.event_router = None
        self.lepak = None
        self.touched = time.monotonic()


class SessionStore:
    def __init__(self, router_factory=CommuteRouter, ttl_s=SESSION_TTL_S,
                 clock=time.monotonic):
        self._router_factory, self._ttl, self._clock = router_factory, ttl_s, clock
        self._sessions, self._lock = {}, threading.Lock()

    def new_id(self):
        return secrets.token_urlsafe(24)

    def get(self, sid):
        """The state for sid, creating it if missing or expired."""
        with self._lock:
            self._expire()
            state = self._sessions.get(sid)
            if state is None:
                if len(self._sessions) >= MAX_SESSIONS:
                    oldest = min(self._sessions, key=lambda k: self._sessions[k].touched)
                    del self._sessions[oldest]
                state = self._sessions[sid] = SessionState(self._router_factory())
            state.touched = self._clock()
            return state

    def _expire(self):
        now = self._clock()
        for sid in [k for k, s in self._sessions.items() if now - s.touched > self._ttl]:
            del self._sessions[sid]

    def __len__(self):
        return len(self._sessions)
