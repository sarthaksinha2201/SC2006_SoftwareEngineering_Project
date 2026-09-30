"""Adapter for the OpenStreetMap Overpass API (bulk ETL download only; © OpenStreetMap
contributors, ODbL). The public server returns 504 when busy, which get_json retries."""
import time

import requests

from gowhere.adapters.http import RateLimiter, get_json

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
SINGAPORE_BBOX = (1.15, 103.59, 1.48, 104.10)   # south, west, north, east (includes some of Johor)


class OverpassAdapter:
    def __init__(self, session=None, sleep=time.sleep):
        self.session = session or requests.Session()
        # Overpass rejects the generic python-requests agent (HTTP 406); identify ourselves.
        self.session.headers["User-Agent"] = "GoWhere-SC2006-student-project"
        self.limiter = RateLimiter(10, sleep=sleep)
        self._sleep = sleep

    def query(self, overpass_ql):
        return get_json(self.session, OVERPASS_URL, params={"data": overpass_ql},
                        limiter=self.limiter, backoff_s=15, timeout_s=240, sleep=self._sleep)

    def amenities(self, selectors, bbox=SINGAPORE_BBOX):
        """Raw response for every element matching any selector, e.g. '["amenity"="cafe"]'.
        Ways and relations come back with a centre point."""
        box = ",".join(str(v) for v in bbox)
        body = "\n".join(f"  nwr{sel}({box});" for sel in selectors)
        return self.query(f"[out:json][timeout:180];\n(\n{body}\n);\nout center tags;")
