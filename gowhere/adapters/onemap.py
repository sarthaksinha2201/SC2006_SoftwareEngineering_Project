"""Adapter for OneMap (SLA): address search and walking routes.

Search needs no token. Routing and themes need one. A token's JWT says it expires after
3 days, though on 14 Oct OneMap still accepted the 30 Sep token (DECISIONS.md section 19),
so the claim is not reliably enforced either way. The adapter renews its own rather
than depend on that: with ONEMAP_EMAIL and ONEMAP_PASSWORD in .env (the OneMap account's
login) it fetches a token, renews it shortly before its stated expiry or when OneMap
answers 401, and shares it across every session. ONEMAP_TOKEN alone still works, for as
long as OneMap accepts it.
OneMap documents 250 calls/min, but token-less search was measured on 30 Sep 2026 to
return HTTP 429 at 2 req/s and none at 1 req/s, so without a token we pace at 1.1 s.
"""
import base64
import json
import logging
import os
import threading
import time

import requests

from gowhere.adapters.http import HttpError, RateLimiter, get_json

SEARCH_URL = "https://www.onemap.gov.sg/api/common/elastic/search"
ROUTE_URL = "https://www.onemap.gov.sg/api/public/routingsvc/route"
THEME_URL = "https://www.onemap.gov.sg/api/public/themesvc/retrieveTheme"
TOKEN_URL = "https://www.onemap.gov.sg/api/auth/post/getToken"
RENEW_BEFORE_S = 600          # renew a token this close to its expiry

log = logging.getLogger(__name__)


# urllib3 logs every request URL, query string included, at DEBUG. Commute requests carry
# a user's destination, which must never reach a log (Security NFR), so its request
# logging is held at INFO whatever the application's log level.
logging.getLogger("urllib3").setLevel(logging.INFO)

TOKEN_INTERVAL_S = 0.3        # 200/min, under the documented 250/min
ANONYMOUS_INTERVAL_S = 1.1    # measured limit for token-less search is ~1 req/s

# While a user waits (Commute, Where to Lepak), one retry and short timeouts. The ETL's
# defaults (4 retries, up to ~30 s of backoff, 30 s timeouts) made an offline comparison
# take 63 s in the 30 Sep rehearsal; with these it fails in seconds and degrades.
REQUEST_TIME = {"retries": 1, "timeout_s": 8}


def token_expiry(token):
    """The epoch second a OneMap token (a JWT) expires, or None if unreadable."""
    try:
        payload = token.split(".")[1]
        return int(json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))["exp"])
    except (AttributeError, IndexError, KeyError, TypeError, ValueError):
        return None


class TokenSource:
    """A OneMap token, renewed from the account login when it nears expiry. One is
    shared by every adapter in the process (see shared_tokens()), so a hundred user
    sessions cost one token request every 3 days, not a hundred."""

    def __init__(self, email=None, password=None, static=None, session=None, clock=time.time):
        self.email, self.password, self.static = email, password, static
        self.session = session or requests.Session()
        self.clock = clock
        self._token, self._lock, self._warned = None, threading.Lock(), False

    @property
    def configured(self):
        return bool(self.static or (self.email and self.password))

    def get(self, force_renew=False):
        """A token to send, or None when there is no way to get one."""
        with self._lock:
            if not (self.email and self.password):
                self._warn_if_expired()
                return self.static
            exp = token_expiry(self._token) if self._token else None
            if force_renew or exp is None or exp - self.clock() < RENEW_BEFORE_S:
                self._token = self._fetch()
            return self._token

    def _fetch(self):
        try:
            resp = self.session.post(TOKEN_URL, json={"email": self.email, "password": self.password},
                                     timeout=10)
        except requests.RequestException as e:
            raise HttpError(f"OneMap token request failed: {type(e).__name__}")
        if resp.status_code != 200:
            # Never echo the body: it may repeat the email address.
            raise HttpError(f"OneMap token request failed: HTTP {resp.status_code}",
                            status=resp.status_code)
        try:
            return resp.json()["access_token"]
        except (ValueError, KeyError, TypeError):
            raise HttpError("OneMap token response had no access_token")

    def _warn_if_expired(self):
        exp = token_expiry(self.static)
        if exp is not None and exp < self.clock() and not self._warned:
            self._warned = True
            log.warning("ONEMAP_TOKEN expired at %s UTC, so OneMap may refuse it. Set ONEMAP_EMAIL "
                        "and ONEMAP_PASSWORD in .env for automatic renewal.",
                        time.strftime("%Y-%m-%d %H:%M", time.gmtime(exp)))


_shared, _shared_lock = None, threading.Lock()


def shared_tokens():
    """The process-wide TokenSource, built from .env on first use."""
    global _shared
    with _shared_lock:
        if _shared is None:
            _shared = TokenSource(os.getenv("ONEMAP_EMAIL"), os.getenv("ONEMAP_PASSWORD"),
                                  os.getenv("ONEMAP_TOKEN"))
        return _shared


# Connections kept open per host: at least gowhere.lepak.routing.MAX_WORKERS, or parallel
# routing discards and reopens connections ("Connection pool is full", 14 Oct rehearsal).
POOL_MAXSIZE = 16


def _pooled_session():
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(pool_maxsize=POOL_MAXSIZE)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


class OneMapAdapter:
    def __init__(self, session=None, token=None, min_interval_s=None, sleep=time.sleep,
                 retries=4, timeout_s=30, tokens=None):
        self.session = session or _pooled_session()
        self.retries, self.timeout_s = retries, timeout_s
        # An explicit token (tests, one-off scripts) is used as given; otherwise the
        # shared, self-renewing source.
        self.tokens = (TokenSource(static=token) if token is not None
                       else tokens or shared_tokens())
        if min_interval_s is None:
            min_interval_s = TOKEN_INTERVAL_S if self.tokens.configured else ANONYMOUS_INTERVAL_S
        self.limiter = RateLimiter(min_interval_s, sleep=sleep)
        self._sleep = sleep

    @property
    def token(self):
        """Truthy when this adapter can authenticate (routing and themes need it)."""
        return self.tokens.configured

    def _auth(self, force_renew=False):
        tok = self.tokens.get(force_renew) if self.tokens.configured else None
        return {"Authorization": tok} if tok else None

    def _authed(self, url, params, redact, retries):
        """GET with the token; on 401, renew it once and retry (a token that expired
        between our check and OneMap's)."""
        call = lambda force: get_json(self.session, url, params=params,
                                      headers=self._auth(force), limiter=self.limiter,
                                      sleep=self._sleep, redact=redact, retries=retries,
                                      timeout_s=self.timeout_s)
        try:
            return call(False)
        except HttpError as e:
            if e.status == 401 and self.tokens.email and self.tokens.password:
                return call(True)
            raise

    def search(self, query, page=1, redact=False):
        """Raw search response. Callers decide which result (if any) is the right one."""
        return get_json(self.session, SEARCH_URL,
                        params={"searchVal": query, "returnGeom": "Y",
                                "getAddrDetails": "Y", "pageNum": page},
                        headers=self._auth(), limiter=self.limiter, sleep=self._sleep,
                        redact=redact, retries=self.retries, timeout_s=self.timeout_s)

    def theme(self, query_name):
        """Raw OneMap theme (a government layer such as MOH hospitals). Needs a token."""
        if not self.token:
            raise HttpError("no OneMap token: set ONEMAP_EMAIL and ONEMAP_PASSWORD (or ONEMAP_TOKEN)")
        return self._authed(THEME_URL, {"queryName": query_name}, False, self.retries)

    def route(self, start, end, route_type, extra=None, redact=False, retries=None):
        """Raw route response between two (lat, lon) points ('walk', 'drive', 'pt')."""
        if not self.token:
            raise HttpError("no OneMap token: set ONEMAP_EMAIL and ONEMAP_PASSWORD (or ONEMAP_TOKEN)")
        return self._authed(ROUTE_URL,
                            {"start": f"{start[0]},{start[1]}", "end": f"{end[0]},{end[1]}",
                             "routeType": route_type, **(extra or {})},
                            redact, self.retries if retries is None else retries)

    def walking_route(self, start, end):
        return self.route(start, end, "walk")

    def transit_route(self, start, end, departure, redact=False, retries=None):
        """Public transport itineraries departing at `departure` (a datetime)."""
        return self.route(start, end, "pt", {
            "date": departure.strftime("%m-%d-%Y"), "time": departure.strftime("%H:%M:%S"),
            "mode": "TRANSIT", "maxWalkDistance": 1000, "numItineraries": 3},
            redact=redact, retries=retries)

    def drive_route(self, start, end, redact=False, retries=None):
        return self.route(start, end, "drive", redact=redact, retries=retries)


def warn_if_all_failed(results, what):
    """One failed route is normal; every route in a request failing is not. It looks
    exactly like ordinary degradation to the user, which is how a total failure can go
    unnoticed, so say it in the log. Counts only: no places."""
    results = list(results)
    if results and all(r is None for r in results):
        log.warning("all %d %s routing calls failed in one request; is OneMap reachable "
                    "and the token valid?", len(results), what)
