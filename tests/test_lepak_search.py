"""Where to Lepak search: date windows, the straight-line pre-filter, the 50-route cap,
sorting and chips, route parsing, and parking with its failure path."""
import json
from datetime import datetime
from types import SimpleNamespace

import pytest

from gowhere.lepak.categories import CATEGORIES

from gowhere.adapters.datamall import DataMallAdapter
from gowhere.adapters.http import HttpError
from gowhere.config import ROOT
from gowhere.etl.geo import haversine_m
from gowhere.lepak.parking import UNAVAILABLE, ParkingService
from gowhere.lepak.routing import EventRouter, decode_polyline, departure_for, parse_route
from gowhere.lepak.search import (ROUTE_CAP, TOP_SPEED_M_PER_MIN, InvalidSearch,
                                  date_window, search, sort_and_filter, validate)
from gowhere.web.mock import LEPAK_NOW, FixedEventRouter, lepak_events

FIXTURES = ROOT / "tests" / "fixtures" / "lepak"
ROUTES = json.loads((FIXTURES / "onemap_routes.json").read_text())
CARPARKS = json.loads((FIXTURES / "datamall_carparks.json").read_text())
NOW = LEPAK_NOW                                   # Wednesday 30 Sep 2026, 12:00
JUNCTION_8, CITY_SQUARE = (1.35048, 103.8487), (1.31142, 103.85662)
ARTS = ["Arts & Culture"]


def ev(i, lat=1.30, lon=103.85, category="Arts & Culture", start="2026-10-03 10:00",
       ends="2026-10-03 23:59", added="2026-09-30 12:00", title=None, all_day=False):
    return {"id": i, "title": title or f"Event {i}", "category": category, "start_at": start,
            "end_at": None, "ends_at": ends, "all_day": all_day, "lat": lat, "lon": lon,
            "added_at": added, "venue": "V", "address": None, "summary": "", "sources": []}


# ---- validation and dates -------------------------------------------------------

@pytest.mark.parametrize("cats, date, mode, minutes, message", [
    ([], "week", "pt", 30, "Choose 1 to 8"),
    # Above the maximum: only 8 categories exist, so a 9th value is made up (section 32).
    (list(CATEGORIES) + ["Nightlife"], "week", "pt", 30, "Choose 1 to 8"),
    (["Nightlife"], "week", "pt", 30, "from the list"),
    (ARTS, "someday", "pt", 30, "when"),
    (ARTS, "week", "cycle", 30, "travel mode"),
    (ARTS, "week", "pt", 4, "5 to 180"),
    (ARTS, "week", "pt", 181, "5 to 180"),
])
def test_invalid_searches(cats, date, mode, minutes, message):
    with pytest.raises(InvalidSearch, match=message):
        validate(cats, date, mode, minutes)


def test_boundaries_that_are_valid():
    validate(ARTS, "week", "pt", 5)
    validate(["Arts & Culture", "Community", "Family & Kids", "Food & Markets"], "week", "walk", 180)
    validate(list(CATEGORIES), "month", "pt", 30)             # all 8: the new maximum


@pytest.mark.parametrize("now, option, expected", [
    (NOW, "today", ("2026-09-30 12:00", "2026-09-30 23:59")),
    (NOW, "tomorrow", ("2026-10-01 00:00", "2026-10-01 23:59")),
    (NOW, "weekend", ("2026-10-03 00:00", "2026-10-04 23:59")),
    (datetime(2026, 10, 3, 15, 0), "weekend", ("2026-10-03 15:00", "2026-10-04 23:59")),
    (datetime(2026, 10, 4, 9, 0), "weekend", ("2026-10-04 09:00", "2026-10-04 23:59")),
    (NOW, "week", ("2026-09-30 12:00", "2026-10-07 23:59")),
    (NOW, "month", ("2026-09-30 12:00", "2026-10-30 23:59")),
])
def test_date_windows(now, option, expected):
    a, b = date_window(option, now)
    assert (f"{a:%Y-%m-%d %H:%M}", f"{b:%Y-%m-%d %H:%M}") == expected


def test_an_event_overlapping_the_window_counts():
    router = FixedEventRouter({})
    running = ev(1, start="2026-09-01 00:00", ends="2026-10-31 23:59")     # started earlier
    later = ev(2, start="2026-10-10 10:00", ends="2026-10-10 23:59")
    found = search([running, later], (1.30, 103.85), ARTS, "weekend", "pt", 30, router, NOW)
    assert [r["id"] for r in found["results"]] == [1]


def test_only_the_chosen_categories():
    events = [ev(1), ev(2, category="Community")]
    found = search(events, (1.30, 103.85), ARTS, "weekend", "pt", 30, FixedEventRouter({}), NOW)
    assert [r["id"] for r in found["results"]] == [1]


# ---- straight-line pre-filter and the cap ------------------------------------------

def test_top_speeds_are_upper_bounds_on_real_routes():
    """The pre-filter must never drop an event a real route would keep: every recorded
    route's straight-line speed is under the bound for its mode (walk 66 of 100 m/min,
    public transport 180 of 1000, drive 335 of 1500)."""
    straight = haversine_m(*JUNCTION_8, *CITY_SQUARE)
    for mode in ("pt", "drive", "walk"):
        minutes = parse_route(ROUTES[mode], mode)["minutes"]
        assert straight / minutes < TOP_SPEED_M_PER_MIN[mode], mode


def test_straight_line_filter_uses_the_mode():
    far = ev(1, lat=1.30 + 0.045)        # ~5 km north
    walk = search([far], (1.30, 103.85), ARTS, "weekend", "walk", 45, FixedEventRouter({}), NOW)
    pt = search([far], (1.30, 103.85), ARTS, "weekend", "pt", 45, FixedEventRouter({}), NOW)
    assert walk["results"] == [] and walk["counts"]["within_straight_line"] == 0
    assert [r["id"] for r in pt["results"]] == [1]


def test_above_the_cap_the_nearest_are_routed_and_the_rest_counted():
    """DECISIONS.md section 33: no refusal; the ROUTE_CAP nearest by straight line."""
    assert ROUTE_CAP == 25
    router = FixedEventRouter({})
    events = [ev(i, lat=1.30 + i * 0.001) for i in range(ROUTE_CAP + 5)]    # further each time
    found = search(events, (1.30, 103.85), ARTS, "weekend", "pt", 30, router, NOW)
    assert router.calls == 1
    assert sorted(r["id"] for r in found["results"]) == list(range(ROUTE_CAP))   # the nearest
    assert found["counts"]["within_straight_line"] == ROUTE_CAP + 5
    assert found["counts"]["timed"] == ROUTE_CAP


def test_the_cap_counts_after_the_straight_line_filter():
    events = [ev(i) for i in range(ROUTE_CAP)] + [ev(99, lat=1.45)]     # one far away
    found = search(events, (1.30, 103.85), ARTS, "weekend", "walk", 30, FixedEventRouter({}), NOW)
    assert found["counts"]["in_categories_and_dates"] == ROUTE_CAP + 1
    assert found["counts"]["within_straight_line"] == ROUTE_CAP


def test_over_the_limit_dropped_unroutable_kept_and_flagged():
    events = [ev(1, title="Near"), ev(2, title="Too far"), ev(3, title="Unroutable")]
    router = FixedEventRouter({"Near": 12.0, "Too far": 30.5, "Unroutable": None})
    found = search(events, (1.30, 103.85), ARTS, "weekend", "pt", 30, router, NOW)
    assert [(r["title"], r["minutes"]) for r in found["results"]] == [("Near", 12.0), ("Unroutable", None)]
    assert found["counts"]["routed"] == 2


# ---- sorting, chips and pages ---------------------------------------------------------

def _results():
    rows = [ev(i, start=f"2026-10-{10 - i % 5:02d} 10:00", added=f"2026-09-{10 + i:02d} 12:00",
               category="Community" if i % 3 == 0 else "Arts & Culture") for i in range(1, 16)]
    for i, r in enumerate(rows):
        r["minutes"] = None if i == 0 else float(40 - i)
    return rows


def test_sort_by_travel_puts_unroutable_last():
    page, total, pages = sort_and_filter(_results(), "travel", (), 2)
    assert (total, pages, len(page)) == (15, 2, 5)
    assert page[-1]["minutes"] is None
    first, _, _ = sort_and_filter(_results(), "travel", (), 1)
    assert [r["minutes"] for r in first][:3] == [26.0, 27.0, 28.0]


def test_sort_soonest_and_recent():
    soonest, _, _ = sort_and_filter(_results(), "soonest", (), 1)
    assert soonest[0]["start_at"] == "2026-10-06 10:00"
    recent, _, _ = sort_and_filter(_results(), "recent", (), 1)
    assert recent[0]["id"] == 15


def test_hidden_categories_and_page_clamping():
    page, total, pages = sort_and_filter(_results(), "travel", {"Arts & Culture"}, 9)
    assert total == 5 and pages == 1 and all(r["category"] == "Community" for r in page)
    page, total, _ = sort_and_filter(_results(), "travel", {"Community"}, 1)
    assert total == 10 and all(r["category"] == "Arts & Culture" for r in page)
    empty, total, pages = sort_and_filter([], "travel", (), 1)
    assert (empty, total, pages) == ([], 0, 1)


# ---- routing ---------------------------------------------------------------------

def test_parse_recorded_routes():
    pt = parse_route(ROUTES["pt"], "pt")
    fastest = min(it["duration"] for it in ROUTES["pt"]["plan"]["itineraries"])
    assert pt["minutes"] == fastest / 60
    assert pt["summary"] == "Walk 2 min → North South Line → Walk 2 min → Bus 141 → Walk 3 min"
    lon, lat = pt["geometry"]["coordinates"][0]
    assert haversine_m(lat, lon, *JUNCTION_8) < 50
    assert parse_route(ROUTES["drive"], "drive")["summary"] == "Drive 6.9 km"
    assert parse_route(ROUTES["walk"], "walk")["summary"] == "Walk 5.6 km"
    assert parse_route({"plan": {"itineraries": []}}, "pt") is None
    assert parse_route({"status_message": "error"}, "drive") is None


def test_decode_polyline():
    assert decode_polyline("_p~iF~ps|U_ulLnnqC_mqNvxq`@") == [(38.5, -120.2), (40.7, -120.95),
                                                             (43.252, -126.453)]


@pytest.mark.parametrize("event, expected", [
    ({"start_at": "2026-10-03 18:00", "all_day": False}, datetime(2026, 10, 3, 18, 0)),
    ({"start_at": "2026-10-03 00:00", "all_day": True}, datetime(2026, 10, 3, 10, 0)),
    ({"start_at": "2026-09-01 00:00", "all_day": True}, NOW),          # already running
    ({"start_at": "2026-09-30 09:00", "all_day": False}, NOW),
])
def test_departure(event, expected):
    assert departure_for(event, NOW) == expected


class _Adapter:
    def __init__(self, fail=False):
        self.fail, self.calls = fail, []

    def transit_route(self, start, end, departure, redact=False, retries=4):
        self.calls.append(("pt", redact))
        if self.fail:
            raise HttpError("HTTP 500")
        return ROUTES["pt"]

    def route(self, start, end, route_type, extra=None, redact=False, retries=4):
        self.calls.append((route_type, redact))
        if self.fail:
            raise HttpError("HTTP 500")
        return ROUTES[route_type]


def test_event_router_redacts_and_survives_failures():
    adapter = _Adapter()
    router = EventRouter(adapter)
    events = [ev(1), ev(2)]
    routes = router.route_many(JUNCTION_8, events, "pt", NOW)
    assert all(r["minutes"] > 0 for r in routes.values())
    router.route_many(JUNCTION_8, events, "drive", NOW)
    assert adapter.calls and all(redact for _, redact in adapter.calls)
    failing = EventRouter(_Adapter(fail=True)).route_many(JUNCTION_8, events, "walk", NOW)
    assert failing == {1: None, 2: None}


def test_every_route_failing_is_logged_once_with_the_count(caplog):
    events = [ev(1), ev(2), ev(3)]
    with caplog.at_level("WARNING", logger="gowhere.adapters.onemap"):
        EventRouter(_Adapter()).route_many(JUNCTION_8, events, "drive", NOW)
        assert caplog.records == []                       # all fine: silent

        class OneFails(_Adapter):
            def route(self, start, end, route_type, **kw):
                super().route(start, end, route_type, **kw)
                if len(self.calls) == 1:
                    raise HttpError("HTTP 500")
                return ROUTES[route_type]
        EventRouter(OneFails(), max_workers=1).route_many(JUNCTION_8, events, "drive", NOW)
        assert caplog.records == []                       # one failure is normal

        EventRouter(_Adapter(fail=True)).route_many(JUNCTION_8, events, "drive", NOW)
    assert [r.getMessage() for r in caplog.records] == [
        "all 3 event routing calls failed in one request; is OneMap reachable and the token valid?"]
    assert "1.3" not in caplog.text                        # counts only, no places


def test_short_trip_with_no_transit_itinerary_is_walked():
    class NoTransit(_Adapter):
        def transit_route(self, *a, **kw):
            self.calls.append(("pt", kw.get("redact")))
            return {"plan": {"itineraries": []}}
    adapter = NoTransit()
    near = EventRouter(adapter).route(JUNCTION_8, (1.3510, 103.8490), "pt", NOW)
    assert near["summary"] == "Walk 5.6 km" and near["mode"] == "walk"
    assert adapter.calls == [("pt", True), ("walk", True)]
    adapter.calls = []
    assert EventRouter(adapter).route(JUNCTION_8, CITY_SQUARE, "pt", NOW) is None   # 4.4 km
    assert adapter.calls == [("pt", True)]


# ---- parking ---------------------------------------------------------------------------

class _DataMall:
    def __init__(self, records=None, fail=None):
        self.records, self.fail, self.calls = records, fail, 0

    def carpark_availability(self):
        self.calls += 1
        if self.fail:
            raise self.fail
        return self.records


def test_parking_within_500m_car_lots_only():
    p = ParkingService(_DataMall(CARPARKS["value"])).near(*CITY_SQUARE)
    assert p["available"]
    assert p["text"] == "589 car lots free in 3 carparks within 500 m"
    assert [c["name"] for c in p["carparks"]] == ["City Square Mall", "Mustafa Centre",
                                                  "Farrer Park Hospital"]


def test_parking_none_nearby():
    p = ParkingService(_DataMall(CARPARKS["value"])).near(1.40, 103.70)
    assert p == {"available": True, "carparks": [],
                 "text": "No carparks with live availability within 500 m"}


@pytest.mark.parametrize("adapter", [
    DataMallAdapter(key=""),                              # nobody has registered for a key
    _DataMall(fail=HttpError("HTTP 503")),
    _DataMall(records="<html>maintenance</html>"),
    _DataMall(records=None),
])
def test_parking_failure_path(adapter):
    p = ParkingService(adapter).near(*CITY_SQUARE)
    assert p == {"available": False, "text": UNAVAILABLE, "carparks": []}


def test_parking_cached_for_two_minutes_for_everyone():
    t = [0.0]
    datamall = _DataMall(CARPARKS["value"])
    service = ParkingService(datamall, clock=lambda: t[0])
    service.near(*CITY_SQUARE)
    t[0] = 119.0
    service.near(1.26398, 103.81252)
    assert datamall.calls == 1
    t[0] = 121.0
    service.near(*CITY_SQUARE)
    assert datamall.calls == 2


def test_parking_failures_are_cached_too():
    t = [0.0]
    datamall = _DataMall(fail=HttpError("HTTP 503"))
    service = ParkingService(datamall, clock=lambda: t[0])
    service.near(*CITY_SQUARE)
    service.near(*CITY_SQUARE)
    assert datamall.calls == 1


def test_parking_only_in_drive_mode():
    events = [ev(1, lat=CITY_SQUARE[0], lon=CITY_SQUARE[1])]
    parking = ParkingService(_DataMall(CARPARKS["value"]))
    pt = search(events, JUNCTION_8, ARTS, "weekend", "pt", 45, FixedEventRouter({}), NOW, parking=parking)
    drive = search(events, JUNCTION_8, ARTS, "weekend", "drive", 45, FixedEventRouter({}), NOW, parking=parking)
    assert "parking" not in pt["results"][0]
    assert drive["results"][0]["parking"]["available"]


class _Session:
    def __init__(self, pages):
        self.pages, self.requests = pages, []

    def get(self, url, params=None, headers=None, timeout=None):
        self.requests.append((params, headers))
        body = {"value": self.pages[len(self.requests) - 1]}
        return SimpleNamespace(status_code=200, json=lambda: body, text="")


def test_datamall_adapter_pages_through_the_dataset():
    session = _Session([[{"CarParkID": str(i)} for i in range(500)], [{"CarParkID": "x"}] * 3])
    records = DataMallAdapter(session, key="k").carpark_availability()
    assert len(records) == 503
    assert [p["$skip"] for p, _ in session.requests] == [0, 500]
    assert all(h["AccountKey"] == "k" for _, h in session.requests)


def test_datamall_adapter_without_a_key_makes_no_request():
    session = _Session([])
    with pytest.raises(HttpError, match="LTA_DATAMALL_KEY"):
        DataMallAdapter(session, key="").carpark_availability()
    assert session.requests == []


# ---- on the ingestion fixtures ------------------------------------------------------

def test_fixture_events_search():
    events = lepak_events().events(NOW)
    found = search(events, CITY_SQUARE, ["Arts & Culture", "Family & Kids"], "weekend", "pt", 45,
                   FixedEventRouter({}), NOW)
    assert sorted(r["title"] for r in found["results"]) == [
        "Anime Earth", "BellyGom Summer Day Out Party", "Free Yukata Experience",
        "Mid-Autumn Light-Up"]


# ---- step-by-step directions (FR 2.5.2) ---------------------------------------------
# A sample in OneMap's documented shape (OpenTripPlanner legs for public transport;
# [direction, road, metres, ...] rows for drive and walk). Constructed, not recorded:
# the OneMap token had expired when this was written. Re-record when routing works.

STEP_SAMPLE_PT = {"plan": {"itineraries": [{"duration": 1500, "legs": [
    {"mode": "WALK", "distance": 92.4, "duration": 96, "from": {"name": "Origin"},
     "to": {"name": "BISHAN MRT STATION"}, "legGeometry": {"points": ""}},
    {"mode": "SUBWAY", "route": "NS", "routeLongName": "NORTH SOUTH LINE", "duration": 343,
     "from": {"name": "BISHAN MRT STATION"}, "to": {"name": "NOVENA MRT STATION"},
     "intermediateStops": [{"name": "BRADDELL"}, {"name": "TOA PAYOH"}], "legGeometry": {"points": ""}},
    {"mode": "BUS", "route": "141", "duration": 452, "from": {"name": "NOVENA STN"},
     "to": {"name": "OPP CITY SQ MALL"}, "intermediateStops": [], "legGeometry": {"points": ""}},
    {"mode": "WALK", "distance": 1216.7, "duration": 900, "from": {"name": "OPP CITY SQ MALL"},
     "to": {"name": "Destination"}, "legGeometry": {"points": ""}}]}]}}
STEP_SAMPLE_DRIVE = {"route_summary": {"total_time": 794, "total_distance": 6918},
                     "route_geometry": "", "route_instructions": [
    ["Head", "BISHAN PLACE", 120, "1.35,103.84", 20, "120m", "North", 0],
    ["Right", "BISHAN ROAD", 1450, "1.35,103.84", 150, "1.4km", "East", 90],
    ["Straight", "", 300, "1.34,103.85", 30, "300m", "South", 180],
    ["Destination", "", 0, "1.31,103.85", 0, "0m", "", 0]]}


def test_public_transport_steps():
    assert parse_route(STEP_SAMPLE_PT, "pt")["steps"] == [
        "Walk 90 m to Bishan MRT Station",
        "Take the North South Line from Bishan MRT Station to Novena MRT Station (3 stops)",
        "Take bus 141 from Novena Stn to Opp City Sq Mall (1 stop)",
        "Walk 1.2 km to your destination"]


def test_drive_steps():
    assert parse_route(STEP_SAMPLE_DRIVE, "drive")["steps"] == [
        "Head along Bishan Place for 120 m", "Turn right onto Bishan Road (1.4 km)",
        "Continue for 300 m"]


def test_malformed_directions_lose_steps_not_the_route():
    broken = {**STEP_SAMPLE_DRIVE, "route_instructions": [None, "x", ["Left"], 5]}
    route = parse_route(broken, "drive")
    assert route["steps"] == [] and route["minutes"] > 0
    recorded = parse_route(ROUTES["pt"], "pt")       # legs trimmed of stop names
    assert recorded["minutes"] > 0 and recorded["steps"][0] == "Walk 90 m"


def test_the_onemap_connection_pool_fits_the_routing_workers():
    """Smaller and parallel routing discards connections (seen in the 14 Oct rehearsal)."""
    from gowhere.adapters.onemap import POOL_MAXSIZE, OneMapAdapter
    from gowhere.lepak.routing import MAX_WORKERS
    assert POOL_MAXSIZE >= MAX_WORKERS
    adapter = OneMapAdapter(token="t").session.get_adapter("https://www.onemap.gov.sg/")
    assert adapter._pool_maxsize == POOL_MAXSIZE
