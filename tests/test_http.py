import pytest
import requests

from gowhere.adapters.datagov import DataGovAdapter
from gowhere.adapters.http import HttpError, RateLimiter, get_json
from gowhere.adapters.onemap import OneMapAdapter


class Resp:
    def __init__(self, status, body=None):
        self.status_code, self._body, self.text = status, body, str(body)

    def json(self):
        return self._body


class FakeSession:
    def __init__(self, responses):
        self.responses, self.calls = list(responses), []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append((url, params, headers))
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def no_sleep(_):
    pass


def test_retries_429_then_succeeds():
    s = FakeSession([Resp(429), requests.ConnectionError("down"), Resp(201, {"ok": 1})])
    assert get_json(s, "u", sleep=no_sleep) == {"ok": 1}
    assert len(s.calls) == 3


def test_non_retryable_status_raises_immediately():
    s = FakeSession([Resp(404, "nope")])
    with pytest.raises(HttpError) as e:
        get_json(s, "u", sleep=no_sleep)
    assert e.value.status == 404 and len(s.calls) == 1


def test_gives_up_after_retries():
    s = FakeSession([Resp(503)] * 3)
    with pytest.raises(HttpError):
        get_json(s, "u", retries=2, sleep=no_sleep)


def test_rate_limiter_waits_remaining_interval():
    now, slept = [100.0], []
    limiter = RateLimiter(1.0, clock=lambda: now[0], sleep=slept.append)
    limiter.wait()
    now[0] += 0.25
    limiter.wait()
    assert slept == [pytest.approx(0.75)]


def test_datastore_paginates_until_total():
    page = lambda recs: Resp(200, {"success": True, "result": {"total": 3, "records": recs}})
    s = FakeSession([page([1, 2]), page([3])])
    pages = DataGovAdapter(session=s, sleep=no_sleep).datastore_pages("rid", page_size=2)
    assert len(pages) == 2 and s.calls[1][1]["offset"] == 2


def test_onemap_routing_requires_token():
    with pytest.raises(HttpError):
        OneMapAdapter(session=FakeSession([]), token="", sleep=no_sleep).walking_route((1, 2), (3, 4))


def test_onemap_paces_slower_without_token():
    assert OneMapAdapter(session=FakeSession([]), token="").limiter.min_interval_s > \
        OneMapAdapter(session=FakeSession([]), token="t").limiter.min_interval_s


def test_backoff_is_jittered_exponential():
    slept = []
    s = FakeSession([Resp(429), Resp(429), Resp(200, {"ok": 1})])
    get_json(s, "u", backoff_s=2.0, sleep=slept.append, jitter=iter([0.0, 1.0]).__next__)
    assert slept == [1.0, 6.0]        # 2 s x 0.5, then 4 s x 1.5


# ---- OneMap token renewal ----------------------------------------------------------

import base64 as _b64
import json as _json
import logging as _logging

from gowhere.adapters.onemap import TokenSource


def _jwt(exp):
    body = _b64.urlsafe_b64encode(_json.dumps({"exp": exp}).encode()).decode().rstrip("=")
    return f"h.{body}.s"


class TokenSession:
    def __init__(self, tokens, status=200):
        self.tokens, self.status, self.posts = list(tokens), status, []

    def post(self, url, json=None, timeout=None):
        self.posts.append(json)
        body = {"access_token": self.tokens.pop(0)} if self.status == 200 else {"error": json["email"]}
        return Resp(self.status, body)


def test_token_is_fetched_once_and_renewed_near_expiry():
    now = [1_000_000]
    session = TokenSession([_jwt(1_000_000 + 3 * 86400), _jwt(1_300_000 + 3 * 86400)])
    src = TokenSource("me@example.com", "pw", session=session, clock=lambda: now[0])
    first = src.get()
    assert src.get() == first and len(session.posts) == 1          # cached while valid
    now[0] = 1_000_000 + 3 * 86400 - 300                            # 5 min before expiry
    assert src.get() != first and len(session.posts) == 2


def test_a_401_renews_the_token_and_retries_once():
    tokens = TokenSource("me@example.com", "pw", session=TokenSession([_jwt(9e9), _jwt(9e9 + 1)]))
    s = FakeSession([Resp(401, {"message": "Unauthorized"}), Resp(200, {"ok": 1})])
    adapter = OneMapAdapter(session=s, tokens=tokens, min_interval_s=0, sleep=no_sleep)
    assert adapter.walking_route((1, 2), (3, 4)) == {"ok": 1}
    assert s.calls[0][2]["Authorization"] != s.calls[1][2]["Authorization"]


def test_failed_token_request_never_echoes_the_login():
    src = TokenSource("me@example.com", "secret-pw", session=TokenSession([], status=403))
    with pytest.raises(HttpError) as e:
        src.get()
    assert "me@example.com" not in str(e.value) and "secret-pw" not in str(e.value)


def test_expired_static_token_is_used_but_warned_about_once(caplog):
    caplog.set_level(_logging.WARNING)
    src = TokenSource(static=_jwt(1_000), clock=lambda: 2_000)
    assert src.get() == _jwt(1_000) and src.get() == _jwt(1_000)
    assert caplog.text.count("ONEMAP_TOKEN expired") == 1 and "ONEMAP_EMAIL" in caplog.text
