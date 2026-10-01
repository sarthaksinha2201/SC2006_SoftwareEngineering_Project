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
