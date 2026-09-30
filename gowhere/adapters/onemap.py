"""Adapter for OneMap (SLA): address search and walking routes.

Search needs no token. Routing needs ONEMAP_TOKEN (generated from a OneMap account).
OneMap documents 250 calls/min, but token-less search was measured on 30 Sep 2026 to
return HTTP 429 at 2 req/s and none at 1 req/s, so without a token we pace at 1.1 s.
"""
import os
import time

import requests

from gowhere.adapters.http import HttpError, RateLimiter, get_json

SEARCH_URL = "https://www.onemap.gov.sg/api/common/elastic/search"
ROUTE_URL = "https://www.onemap.gov.sg/api/public/routingsvc/route"


TOKEN_INTERVAL_S = 0.3        # 200/min, under the documented 250/min
ANONYMOUS_INTERVAL_S = 1.1    # measured limit for token-less search is ~1 req/s


class OneMapAdapter:
    def __init__(self, session=None, token=None, min_interval_s=None, sleep=time.sleep):
        self.session = session or requests.Session()
        self.token = token if token is not None else os.getenv("ONEMAP_TOKEN")
        if min_interval_s is None:
            min_interval_s = TOKEN_INTERVAL_S if self.token else ANONYMOUS_INTERVAL_S
        self.limiter = RateLimiter(min_interval_s, sleep=sleep)
        self._sleep = sleep

    def _auth(self):
        return {"Authorization": self.token} if self.token else None

    def search(self, query, page=1):
        """Raw search response. Callers decide which result (if any) is the right one."""
        return get_json(self.session, SEARCH_URL,
                        params={"searchVal": query, "returnGeom": "Y",
                                "getAddrDetails": "Y", "pageNum": page},
                        headers=self._auth(), limiter=self.limiter, sleep=self._sleep)

    def walking_route(self, start, end):
        """Raw walking-route response between two (lat, lon) points."""
        if not self.token:
            raise HttpError("ONEMAP_TOKEN is not set; routing requires a OneMap account token")
        return get_json(self.session, ROUTE_URL,
                        params={"start": f"{start[0]},{start[1]}",
                                "end": f"{end[0]},{end[1]}", "routeType": "walk"},
                        headers=self._auth(), limiter=self.limiter, sleep=self._sleep)
