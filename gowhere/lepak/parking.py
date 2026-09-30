"""Parking near an event (UC-3, drive mode only).

Car lots available within PARKING_RADIUS_M of the venue, from LTA DataMall's live
carpark availability. The whole dataset is fetched at most once per CACHE_S for all
users (it is public data), so a busy results page costs one DataMall call, not one per
event. Any failure (no key, DataMall down, a malformed reply) gives the same answer,
"Parking information unavailable", and never stops the results from showing.
"""
import threading
import time

from gowhere.adapters.datamall import DataMallAdapter
from gowhere.adapters.http import HttpError
from gowhere.etl.geo import haversine_m

PARKING_RADIUS_M = 500.0
CACHE_S = 120
MAX_LISTED = 3
UNAVAILABLE = "Parking information unavailable"


def _carparks(records):
    out = []
    for r in records:
        try:
            if r.get("LotType") != "C":           # car lots only, not motorcycles or HGVs
                continue
            lat, lon = (float(x) for x in r["Location"].split())
            out.append({"name": r.get("Development") or r.get("CarParkID"), "lat": lat,
                        "lon": lon, "lots": int(r["AvailableLots"])})
        except (AttributeError, KeyError, TypeError, ValueError):
            continue                              # one bad record should not hide the rest
    return out


class ParkingService:
    def __init__(self, adapter=None, clock=time.monotonic, cache_s=CACHE_S):
        self.adapter = adapter or DataMallAdapter()
        self.clock, self.cache_s = clock, cache_s
        self._cached, self._fetched_at = None, None
        self._lock = threading.Lock()

    def _all(self):
        """Every car carpark, from cache if fresh; None when DataMall is unavailable."""
        with self._lock:
            if self._fetched_at is not None and self.clock() - self._fetched_at < self.cache_s:
                return self._cached
            try:
                records = self.adapter.carpark_availability()
                self._cached = _carparks(records) if isinstance(records, list) else None
            except (HttpError, AttributeError, TypeError, ValueError):
                self._cached = None
            self._fetched_at = self.clock()    # failures are cached too: no retry storm
            return self._cached

    def near(self, lat, lon):
        """{available, text, carparks: [{name, lots, distance_m}]} for one venue."""
        carparks = self._all()
        if carparks is None:
            return {"available": False, "text": UNAVAILABLE, "carparks": []}
        nearby = sorted(({"name": c["name"], "lots": c["lots"],
                          "distance_m": haversine_m(lat, lon, c["lat"], c["lon"])}
                         for c in carparks), key=lambda c: c["distance_m"])
        nearby = [c for c in nearby if c["distance_m"] <= PARKING_RADIUS_M]
        if not nearby:
            text = f"No carparks with live availability within {PARKING_RADIUS_M:.0f} m"
        else:
            total = sum(c["lots"] for c in nearby)
            text = (f"{total:,} car lots free in {len(nearby)} "
                    f"{'carpark' if len(nearby) == 1 else 'carparks'} within {PARKING_RADIUS_M:.0f} m")
        return {"available": True, "text": text, "carparks": nearby[:MAX_LISTED]}
