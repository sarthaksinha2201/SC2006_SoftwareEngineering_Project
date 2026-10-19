"""Adapter for Google Places API (New): place IDs offline, ratings at request time
(DECISIONS.md sections 27 and 29).

Two calls, priced differently (Google Maps Platform pricing, read 19 Oct 2026):
  - find_place_id: Text Search asking only for `places.id`. That is the
    "Text Search Essentials (IDs Only)" SKU: no charge, unlimited. Used offline by
    gowhere.eat.google_ids, and the result is stored in eat.db. Google's Places
    policies allow the place ID, and only the place ID, to be stored indefinitely.
  - details: Place Details asking for rating, userRatingCount, displayName and
    googleMapsUri. `rating` puts it in the "Place Details Enterprise" SKU: 1,000 free a
    month, then US$20 per 1,000. Nothing it returns is written anywhere; it lives only in
    the requesting user's session memory and expires with it.

**The daily cap.** Every details call is counted against `daily_cap` (per Singapore
calendar day, per process) BEFORE it is sent. Once the cap is reached, details() returns
None without calling Google, and the app shows places without ratings. The default
(config.GOOGLE_DAILY_CAP) keeps within the free 1,000 a month. The Google Cloud console
quota and budget alert are the second line; this is the one the code controls.

The key comes from GOOGLE_MAPS_API_KEY in .env. It is sent in a header, never a URL, and
scrubbed from any error text.
"""
import logging
import os
import threading
from datetime import datetime, timedelta, timezone

import requests

from gowhere import config

log = logging.getLogger(__name__)

SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
DETAILS_URL = "https://places.googleapis.com/v1/places/{place_id}"
DETAILS_FIELDS = "id,displayName,rating,userRatingCount,googleMapsUri"
SGT = timezone(timedelta(hours=8))


class PlacesError(Exception):
    """A Google call failed. The message never contains the key."""


def _scrub(text, key):
    return text.replace(key, "[redacted]") if key else text


class DailyCap:
    """At most `limit` uses per Singapore calendar day. Thread-safe."""

    def __init__(self, limit, clock=lambda: datetime.now(SGT)):
        self.limit, self._clock = limit, clock
        self._day, self._used = None, 0
        self._lock = threading.Lock()

    def take(self):
        """True if a use was granted (and counted), False if today's cap is spent."""
        with self._lock:
            today = self._clock().date()
            if today != self._day:
                self._day, self._used = today, 0
            if self._used >= self.limit:
                return False
            self._used += 1
            return True

    @property
    def used(self):
        with self._lock:
            return self._used if self._day == self._clock().date() else 0


class GooglePlacesAdapter:
    def __init__(self, key=None, session=None, daily_cap=None, timeout_s=8, cap=None):
        self.key = key if key is not None else os.getenv("GOOGLE_MAPS_API_KEY")
        self.session = session or requests.Session()
        self.timeout_s = timeout_s
        self.cap = cap or DailyCap(config.GOOGLE_DAILY_CAP if daily_cap is None else daily_cap)

    @property
    def configured(self):
        return bool(self.key)

    def _call(self, method, url, fields, body=None):
        if not self.key:
            raise PlacesError("GOOGLE_MAPS_API_KEY is not set")
        headers = {"X-Goog-Api-Key": self.key, "X-Goog-FieldMask": fields}
        try:
            resp = self.session.request(method, url, headers=headers, json=body,
                                        timeout=self.timeout_s)
        except requests.RequestException as e:
            raise PlacesError(_scrub(f"{type(e).__name__}: {e}", self.key)) from None
        if resp.status_code != 200:
            raise PlacesError(_scrub(f"HTTP {resp.status_code}", self.key))
        try:
            return resp.json()
        except ValueError:
            raise PlacesError("reply was not JSON") from None

    def find_place_id(self, name, lat, lon, radius_m=100):
        """The Google place ID of the best match for `name` near (lat, lon), or None.
        IDs Only: free. Offline use only (gowhere.eat.google_ids)."""
        body = {"textQuery": name, "pageSize": 1,
                "locationBias": {"circle": {"center": {"latitude": lat, "longitude": lon},
                                            "radius": float(radius_m)}}}
        places = self._call("POST", SEARCH_URL, "places.id", body).get("places") or []
        return places[0]["id"] if places else None

    def details(self, place_id):
        """{rating, count, name, maps_url} or None when the cap is spent or the call
        fails. Raises nothing: a missing rating must never break a search."""
        if not self.configured:
            return None
        if not self.cap.take():
            log.info("Google Places daily cap of %d reached; showing places without ratings",
                     self.cap.limit)
            return None
        try:
            d = self._call("GET", DETAILS_URL.format(place_id=place_id), DETAILS_FIELDS)
        except PlacesError as e:
            log.warning("Google Places details failed: %s", e)
            return None
        if d.get("rating") is None:
            return {"rating": None, "count": 0, "name": (d.get("displayName") or {}).get("text"),
                    "maps_url": d.get("googleMapsUri")}
        return {"rating": float(d["rating"]), "count": int(d.get("userRatingCount") or 0),
                "name": (d.get("displayName") or {}).get("text"),
                "maps_url": d.get("googleMapsUri")}


_shared = None
_shared_lock = threading.Lock()


def shared_places():
    """One adapter per process, so the daily cap counts every user's calls together."""
    global _shared
    with _shared_lock:
        if _shared is None:
            _shared = GooglePlacesAdapter()
        return _shared
