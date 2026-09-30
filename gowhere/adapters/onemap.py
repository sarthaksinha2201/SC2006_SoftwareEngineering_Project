"""Adapter for OneMap (SLA): address search and walking routes.

Search needs no token. Routing needs ONEMAP_TOKEN (generated from a OneMap account).
OneMap documents 250 calls/min, but token-less search was measured on 30 Sep 2026 to
return HTTP 429 at 2 req/s and none at 1 req/s, so without a token we pace at 1.1 s.
"""
import logging
import os
import time

import requests

from gowhere.adapters.http import HttpError, RateLimiter, get_json

SEARCH_URL = "https://www.onemap.gov.sg/api/common/elastic/search"
ROUTE_URL = "https://www.onemap.gov.sg/api/public/routingsvc/route"
THEME_URL = "https://www.onemap.gov.sg/api/public/themesvc/retrieveTheme"


# urllib3 logs every request URL, query string included, at DEBUG. Commute requests carry
# a user's destination, which must never reach a log (Security NFR), so its request
# logging is held at INFO whatever the application's log level.
logging.getLogger("urllib3").setLevel(logging.INFO)

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

    def search(self, query, page=1, redact=False):
        """Raw search response. Callers decide which result (if any) is the right one."""
        return get_json(self.session, SEARCH_URL,
                        params={"searchVal": query, "returnGeom": "Y",
                                "getAddrDetails": "Y", "pageNum": page},
                        headers=self._auth(), limiter=self.limiter, sleep=self._sleep,
                        redact=redact)

    def theme(self, query_name):
        """Raw OneMap theme (a government layer such as MOH hospitals). Needs a token."""
        if not self.token:
            raise HttpError("ONEMAP_TOKEN is not set; themes require a OneMap account token")
        return get_json(self.session, THEME_URL, params={"queryName": query_name},
                        headers=self._auth(), limiter=self.limiter, sleep=self._sleep)

    def route(self, start, end, route_type, extra=None, redact=False, retries=4):
        """Raw route response between two (lat, lon) points ('walk', 'drive', 'pt')."""
        if not self.token:
            raise HttpError("ONEMAP_TOKEN is not set; routing requires a OneMap account token")
        return get_json(self.session, ROUTE_URL,
                        params={"start": f"{start[0]},{start[1]}", "end": f"{end[0]},{end[1]}",
                                "routeType": route_type, **(extra or {})},
                        headers=self._auth(), limiter=self.limiter, sleep=self._sleep,
                        redact=redact, retries=retries)

    def walking_route(self, start, end):
        return self.route(start, end, "walk")

    def transit_route(self, start, end, departure, redact=False, retries=4):
        """Public transport itineraries departing at `departure` (a datetime)."""
        return self.route(start, end, "pt", {
            "date": departure.strftime("%m-%d-%Y"), "time": departure.strftime("%H:%M:%S"),
            "mode": "TRANSIT", "maxWalkDistance": 1000, "numItineraries": 3},
            redact=redact, retries=retries)

    def drive_route(self, start, end, redact=False, retries=4):
        return self.route(start, end, "drive", redact=redact, retries=retries)
