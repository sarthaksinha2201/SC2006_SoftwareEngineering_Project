"""Shared HTTP plumbing for adapters: polite rate limiting and retry with backoff."""
import logging
import time

import requests

log = logging.getLogger(__name__)

RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class RateLimiter:
    """Enforces a minimum interval between consecutive calls."""

    def __init__(self, min_interval_s, clock=time.monotonic, sleep=time.sleep):
        self.min_interval_s = min_interval_s
        self._clock = clock
        self._sleep = sleep
        self._last = None

    def wait(self):
        if self._last is not None:
            remaining = self.min_interval_s - (self._clock() - self._last)
            if remaining > 0:
                self._sleep(remaining)
        self._last = self._clock()


class HttpError(Exception):
    """A request that still failed after retries. Carries the status for logging."""

    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


def get_json(session, url, params=None, headers=None, limiter=None,
             retries=4, backoff_s=2.0, timeout_s=30, sleep=time.sleep):
    """GET a JSON document, retrying transient failures with exponential backoff."""
    last_error = None
    for attempt in range(retries + 1):
        if limiter:
            limiter.wait()
        try:
            resp = session.get(url, params=params, headers=headers, timeout=timeout_s)
        except requests.RequestException as e:
            last_error = HttpError(f"{type(e).__name__}: {e}")
        else:
            if 200 <= resp.status_code < 300:
                try:
                    return resp.json()
                except ValueError:
                    raise HttpError("response was not JSON", status=resp.status_code)
            last_error = HttpError(f"HTTP {resp.status_code}: {resp.text[:200]}",
                                   status=resp.status_code)
            if resp.status_code not in RETRYABLE_STATUS:
                raise last_error
        if attempt < retries:
            delay = backoff_s * 2 ** attempt
            log.warning("retrying %s in %.0fs after %s", url, delay, last_error)
            sleep(delay)
    raise last_error
