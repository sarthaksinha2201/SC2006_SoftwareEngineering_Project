"""Travel time from a user's starting point to events (the RouteService side of the
shared services), through the existing OneMap routing adapter.

Privacy (Security NFR): the starting point is personal. It lives only in the caller's
session memory, every OneMap call is made with redact=True, and nothing here logs or
stores it. OneMap echoes the request coordinates in `requestParameters`; only the
duration, legs and geometry are kept from a response.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, time, timedelta

from gowhere.adapters.http import HttpError
from gowhere.adapters.onemap import OneMapAdapter
from gowhere.etl.geo import haversine_m
from gowhere.scoring.stats import round0

MODES = {"pt": "public transport", "drive": "car", "walk": "walking"}
ALL_DAY_DEPARTURE = time(10, 0)      # an all-day event on a future day: leave mid-morning
# OneMap returns no public transport itinerary for a short trip (measured: a venue at the
# starting point itself). Within this distance a failed public transport route is
# retried as a walk, which is what the trip would be. The route keeps mode "walk", so
# it is always labelled as a walking route, never shown as a public transport time.
WALK_FALLBACK_M = 1500.0
# 50 routes (the cap) must fit the 8-second target. Measured 30 Sep 2026: 40 public
# transport routes took 7.4 s with 8 workers and 3.1 s with 16, with no failures.
MAX_WORKERS = 16


def decode_polyline(encoded, precision=5):
    """[(lat, lon)] from a Google encoded polyline, the format OneMap returns."""
    coords, i, lat, lon, factor = [], 0, 0, 0, 10 ** precision
    while i < len(encoded):
        deltas = []
        for _ in range(2):
            shift = result = 0
            while True:
                b = ord(encoded[i]) - 63
                i += 1
                result |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break
            deltas.append(~(result >> 1) if result & 1 else result >> 1)
        lat, lon = lat + deltas[0], lon + deltas[1]
        coords.append((lat / factor, lon / factor))
    return coords


def departure_for(event, now):
    """When to leave: now for an event already running or starting today before now;
    otherwise its start time, or mid-morning on its first day if it has no time."""
    start = datetime.strptime(event["start_at"], "%Y-%m-%d %H:%M")
    if event["all_day"]:
        start = datetime.combine(start.date(), ALL_DAY_DEPARTURE)
    return max(start, now)


def _leg_text(leg):
    mode, minutes = leg.get("mode"), max(1, round0(leg.get("duration", 0) / 60))
    if mode == "WALK":
        return f"Walk {minutes} min"
    if mode == "SUBWAY":
        return (leg.get("routeLongName") or f"{leg.get('route')} line").title().replace("Mrt", "MRT")
    if mode == "BUS":
        return f"Bus {leg.get('route')}"
    if mode == "TRAM":
        return f"LRT {leg.get('route')}".strip()
    return mode.title() if mode else "Transfer"


def _line(points):
    return {"type": "LineString", "coordinates": [[lon, lat] for lat, lon in points]}


def parse_route(response, mode):
    """{minutes, summary, geometry (GeoJSON LineString, lon/lat)} or None."""
    if mode == "pt":
        itineraries = (response.get("plan") or {}).get("itineraries") or []
        if not itineraries:
            return None
        best = min(itineraries, key=lambda it: it["duration"])
        legs = best.get("legs") or []
        points = [p for leg in legs for p in decode_polyline((leg.get("legGeometry") or {}).get("points", ""))]
        return {"minutes": best["duration"] / 60, "mode": "pt",
                "summary": " → ".join(_leg_text(leg) for leg in legs),
                "geometry": _line(points)}
    summary = response.get("route_summary") or {}
    if summary.get("total_time") is None:
        return None
    km = summary.get("total_distance", 0) / 1000
    return {"minutes": summary["total_time"] / 60, "mode": mode,
            "summary": f"{'Drive' if mode == 'drive' else 'Walk'} {km:.1f} km",
            "geometry": _line(decode_polyline(response.get("route_geometry") or ""))}


class EventRouter:
    """Routes one user's starting point to many events, in parallel. One per session."""

    def __init__(self, adapter=None, max_workers=MAX_WORKERS):
        self.adapter = adapter or OneMapAdapter(min_interval_s=0)
        self.max_workers = max_workers

    def route(self, origin, destination, mode, departure):
        try:
            if mode == "pt":
                response = self.adapter.transit_route(origin, destination, departure,
                                                      redact=True, retries=1)
            else:
                response = self.adapter.route(origin, destination, mode, redact=True, retries=1)
            route = parse_route(response, mode)
        except (HttpError, KeyError, TypeError, ValueError, IndexError):
            route = None
        if route is None and mode == "pt" and haversine_m(*origin, *destination) <= WALK_FALLBACK_M:
            return self.route(origin, destination, "walk", departure)
        return route

    def route_many(self, origin, events, mode, now):
        """{event id: route or None}."""
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            routes = pool.map(lambda e: self.route(origin, (e["lat"], e["lon"]), mode,
                                                   departure_for(e, now)), events)
            return {e["id"]: r for e, r in zip(events, routes)}
