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
from gowhere.adapters.onemap import REQUEST_TIME, OneMapAdapter, warn_if_all_failed
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


def _place(name):
    if not name or name.lower() in ("origin", "destination"):
        return None
    return name.title().replace("Mrt", "MRT").replace("Lrt", "LRT")


def _metres(m):
    m = float(m or 0)
    return f"{round0(m / 10) * 10:.0f} m" if m < 1000 else f"{m / 1000:.1f} km"


def _pt_step(leg):
    """One public transport leg as a sentence, or None if OneMap gave too little."""
    mode, to, frm = leg.get("mode"), _place((leg.get("to") or {}).get("name")), \
        _place((leg.get("from") or {}).get("name"))
    if mode == "WALK":
        raw_to = ((leg.get("to") or {}).get("name") or "").lower()
        where = to or ("your destination" if raw_to == "destination" else None)
        return f"Walk {_metres(leg.get('distance'))}" + (f" to {where}" if where else "")
    stops = len(leg.get("intermediateStops") or []) + 1
    what = {"SUBWAY": f"the {_leg_text(leg)}", "BUS": f"bus {leg.get('route')}",
            "TRAM": f"the {_leg_text(leg)}"}.get(mode, _leg_text(leg))
    if not (frm and to):
        return f"Take {what}"
    return f"Take {what} from {frm} to {to} ({stops} stop{'s' if stops != 1 else ''})"


_TURNS = {"left": "Turn left onto", "right": "Turn right onto", "slight left": "Bear left onto",
          "slight right": "Bear right onto", "sharp left": "Turn sharp left onto",
          "sharp right": "Turn sharp right onto", "straight": "Continue onto",
          "continue": "Continue onto"}


def _road_step(instr):
    """One drive or walk instruction, OneMap's [direction, road, metres, ...] row."""
    direction, road, metres = str(instr[0]), str(instr[1] or "").title(), instr[2]
    if direction.lower() in ("destination", "arrive") or not road and not metres:
        return None
    if direction.lower() == "head":
        return f"Head along {road} for {_metres(metres)}" if road else f"Head off for {_metres(metres)}"
    verb = _TURNS.get(direction.lower(), direction.capitalize())
    if not road:        # "Turn left onto" with no road reads wrong: drop the "onto"
        return f"{verb.removesuffix(' onto')} for {_metres(metres)}"
    return f"{verb} {road} ({_metres(metres)})"


def steps_from(response, mode, legs=None):
    """Step-by-step directions (FR 2.5.2). Defensive: anything malformed is skipped,
    so a change in OneMap's reply loses steps, never the route."""
    out = []
    try:
        if mode == "pt":
            out = [_pt_step(leg) for leg in legs or []]
        else:
            out = [_road_step(i) for i in response.get("route_instructions") or []
                   if isinstance(i, (list, tuple)) and len(i) >= 3]
    except (KeyError, TypeError, ValueError, IndexError, AttributeError):
        return []
    return [s for s in out if s]


def parse_route(response, mode):
    """{minutes, mode, summary, steps, geometry (GeoJSON LineString, lon/lat)} or None."""
    if mode == "pt":
        itineraries = (response.get("plan") or {}).get("itineraries") or []
        if not itineraries:
            return None
        best = min(itineraries, key=lambda it: it["duration"])
        legs = best.get("legs") or []
        points = [p for leg in legs for p in decode_polyline((leg.get("legGeometry") or {}).get("points", ""))]
        return {"minutes": best["duration"] / 60, "mode": "pt",
                "summary": " → ".join(_leg_text(leg) for leg in legs),
                "steps": steps_from(response, "pt", legs),
                "geometry": _line(points)}
    summary = response.get("route_summary") or {}
    if summary.get("total_time") is None:
        return None
    km = summary.get("total_distance", 0) / 1000
    return {"minutes": summary["total_time"] / 60, "mode": mode,
            "summary": f"{'Drive' if mode == 'drive' else 'Walk'} {km:.1f} km",
            "steps": steps_from(response, mode),
            "geometry": _line(decode_polyline(response.get("route_geometry") or ""))}


class EventRouter:
    """Routes one user's starting point to many events, in parallel. One per session."""

    def __init__(self, adapter=None, max_workers=MAX_WORKERS):
        self.adapter = adapter or OneMapAdapter(min_interval_s=0, **REQUEST_TIME)
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
            out = {e["id"]: r for e, r in zip(events, routes)}
        warn_if_all_failed(out.values(), "event")
        return out
