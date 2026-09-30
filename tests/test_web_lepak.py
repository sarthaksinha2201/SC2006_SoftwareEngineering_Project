"""Where to Lepak screens end to end: search -> results -> detail, with the starting
point kept out of URLs, cookies and logs, and sorting/chips/paging making no external
calls. Events are the ingestion fixtures as of 30 Sep 2026 12:00."""
import json
import logging
import sqlite3

import pytest

from gowhere.adapters.http import HttpError
from gowhere.config import ROOT
from gowhere.lepak.parking import UNAVAILABLE, ParkingService
from gowhere.lepak.store import EventStore
from gowhere.web.mock import LEPAK_MINUTES, LEPAK_NOW, FixedEventRouter, lepak_events
from tests.test_web import app as live_app  # noqa: F401  (the Where to Live app fixture)

POSTAL = "048583"
ORIGIN = (1.3521, 103.8198)
FIXTURES = ROOT / "tests" / "fixtures"
CARPARKS = json.loads((FIXTURES / "lepak" / "datamall_carparks.json").read_text())


class FakeLocations:
    calls = []

    def postal(self, postal):
        FakeLocations.calls.append("postal")
        if postal == "000001":
            raise HttpError("simulated outage")
        return {POSTAL: ORIGIN}.get(postal)


class CountingDataMall:
    def __init__(self, records=None):
        self.records, self.calls = records, 0

    def carpark_availability(self):
        self.calls += 1
        if self.records is None:
            raise HttpError("LTA_DATAMALL_KEY is not set")
        return self.records


@pytest.fixture
def app(live_app, tmp_path):
    path = tmp_path / "events.db"
    target = sqlite3.connect(path)
    lepak_events().db.backup(target)
    target.close()
    routers = []

    def router_factory():
        routers.append(FixedEventRouter(LEPAK_MINUTES))
        return routers[-1]
    FakeLocations.calls = []
    live_app.config.update(EVENTS_PATH=path, LOCATION_FACTORY=FakeLocations,
                           EVENT_ROUTER_FACTORY=router_factory, NOW=lambda: LEPAK_NOW)
    live_app.extensions["gowhere"]["parking"] = ParkingService(CountingDataMall())
    live_app.routers = routers
    return live_app


@pytest.fixture
def client(app):
    return app.test_client()


def form(**over):
    data = {"categories": ["Arts & Culture", "Music & Performances", "Family & Kids",
                           "Sales & Pop-ups"],
            "date_option": "month", "origin": "postal", "postal": POSTAL, "mode": "pt",
            "max_minutes": "45"}
    data.update(over)
    return data


def test_search_page_renders(client):
    page = client.get("/lepak")
    assert page.status_code == 200 and b"Sales &amp; Pop-ups" in page.data


def test_search_then_results(client):
    r = client.post("/lepak", data=form())
    assert r.status_code == 303 and r.headers["Location"].endswith("/lepak/results")
    page = client.get("/lepak/results").get_data(as_text=True)
    assert "9 events within 45 min by public transport, next 30 days" in page
    assert "19 min by public transport" in page and "Seoul Anthem K-pop Party" in page
    assert page.index("Seoul Anthem") < page.index("Anime Earth")            # shortest first
    assert "Travel time unavailable" in page and "listed last" in page
    assert "https://t.me/sgwhereto/4497" in page


def test_sorting_chips_and_paging_call_nothing(app, client):
    client.post("/lepak", data=form(mode="drive"))
    router, datamall = app.routers[-1], app.extensions["gowhere"]["parking"].adapter
    before = (router.calls, datamall.calls, len(FakeLocations.calls))
    for query in ("?sort=soonest", "?sort=recent", "?category=Family+%26+Kids",
                  "?category=Arts+%26+Culture&sort=soonest&page=2", "?page=7", "?sort=bogus"):
        assert client.get("/lepak/results" + query).status_code == 200
    assert (router.calls, datamall.calls, len(FakeLocations.calls)) == before


def test_category_chip_filters(client):
    client.post("/lepak", data=form())
    page = client.get("/lepak/results?category=Family+%26+Kids").get_data(as_text=True)
    assert "Free Yukata Experience" in page and "Anime Earth" not in page


def test_paging(client, monkeypatch):
    monkeypatch.setattr("gowhere.lepak.search.PAGE_SIZE", 4)     # 9 fixture events -> 3 pages
    client.post("/lepak", data=form())
    page = client.get("/lepak/results").get_data(as_text=True)
    assert page.count("<article>") == 4 and "Page 1 of 3" in page
    assert client.get("/lepak/results?page=3").get_data(as_text=True).count("<article>") == 1


@pytest.mark.parametrize("over, message", [
    ({"categories": []}, "Choose 1 to 4 categories"),
    ({"postal": "12345"}, "6-digit"),
    ({"postal": "1234567"}, "6-digit"),
    ({"postal": "999999"}, "couldn&#39;t find that postal code"),
    ({"postal": "000001"}, "OneMap can&#39;t be reached"),
    ({"max_minutes": "soon"}, "whole number"),
    ({"origin": "here", "lat": "", "lon": ""}, "location isn&#39;t available"),
    ({"origin": "here", "lat": "51.5", "lon": "-0.12"}, "outside Singapore"),
])
def test_invalid_searches_rerender_with_message(client, over, message):
    r = client.post("/lepak", data=form(**over))
    assert r.status_code == 400 and message in r.get_data(as_text=True)


def test_too_many_asks_to_narrow_without_routing(app, client, monkeypatch):
    monkeypatch.setattr("gowhere.lepak.search.ROUTE_CAP", 3)
    r = client.post("/lepak", data=form())
    assert r.status_code == 400 and "Choose fewer categories" in r.get_data(as_text=True)
    assert all(router.calls == 0 for router in app.routers)


def test_device_location(client):
    r = client.post("/lepak", data=form(origin="here", lat="1.3521", lon="103.8198", postal=""))
    assert r.status_code == 303 and FakeLocations.calls == []


def test_drive_mode_parking_unavailable_results_still_shown(app, client):
    client.post("/lepak", data=form(mode="drive"))
    page = client.get("/lepak/results").get_data(as_text=True)
    assert page.count(UNAVAILABLE) == page.count("<article>") == 9
    assert "min by car" in page


def test_drive_mode_parking_when_datamall_answers(app, client):
    app.extensions["gowhere"]["parking"] = ParkingService(CountingDataMall(CARPARKS["value"]))
    client.post("/lepak", data=form(mode="drive"))
    page = client.get("/lepak/results").get_data(as_text=True)
    assert "589 car lots free in 3 carparks within 500 m" in page        # City Square Mall


def test_no_parking_line_outside_drive_mode(client):
    client.post("/lepak", data=form(mode="pt"))
    assert UNAVAILABLE not in client.get("/lepak/results").get_data(as_text=True)


def test_event_detail(client):
    client.post("/lepak", data=form())
    events = EventStore(client.application.config["EVENTS_PATH"]).events(LEPAK_NOW)
    anime = next(e for e in events if e["title"] == "Anime Earth")
    page = client.get(f"/lepak/events/{anime['id']}").get_data(as_text=True)
    assert "22 min by public transport" in page and "North South Line" in page
    assert '"kind": "route"' in page
    # Straight to the page with no search: the event, without travel time or route.
    fresh = client.application.test_client().get(f"/lepak/events/{anime['id']}")
    assert fresh.status_code == 200 and "min by" not in fresh.get_data(as_text=True)
    assert client.get("/lepak/events/9999").status_code == 404


def test_event_text_is_escaped(app, client):
    store = EventStore(app.config["EVENTS_PATH"])
    store.commit_batch([{"title": "<script>alert(1)</script>", "category": "Arts & Culture",
                         "start_at": "2026-10-03 10:00", "end_at": None, "ends_at": "2026-10-03 23:59",
                         "all_day": False, "venue": "<b>V</b>", "address": None,
                         "summary": "<img src=x onerror=alert(1)>", "source_url": "https://t.me/x/1",
                         "place_name": "V", "lat": 1.3521, "lon": 103.8198}], "x", 1, LEPAK_NOW)
    client.post("/lepak", data=form())
    page = client.get("/lepak/results").get_data(as_text=True)
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page and "<script>alert(1)" not in page
    assert "<img src=x" not in page and "<b>V</b>" not in page


# ---- Security NFR: the starting point stays in server memory ----

def test_starting_point_never_in_url_cookie_page_or_logs(app, client, caplog):
    caplog.set_level(logging.DEBUG)
    r = client.post("/lepak", data=form(mode="drive"))
    assert POSTAL not in r.headers["Location"]
    cookie = r.headers.get("Set-Cookie", "")
    raw = cookie.split("=", 1)[1].split(";", 1)[0]
    assert set(app.session_interface.get_signing_serializer(app).loads(raw)) == {"sid"}
    pages = [client.get(u).get_data(as_text=True)
             for u in ("/lepak/results", "/lepak/results?sort=soonest&page=1")]
    links = [line for p in pages for line in p.splitlines() if "href=" in line]
    assert not any(POSTAL in line or "1.3521" in line for line in links)
    assert POSTAL not in caplog.text and "103.8198" not in caplog.text
    r = client.post("/lepak", data=form(origin="here", lat="1.3521", lon="103.8198"))
    assert "1.3521" not in r.headers["Location"] and "103.8198" not in caplog.text


# ---- the front-end contract ----

def _shape(v):
    if isinstance(v, dict):
        return {k: _shape(x) for k, x in v.items() if k not in ("geometry", "map")}
    if isinstance(v, list):
        return [_shape(v[0])] if v and isinstance(v[0], (dict, list)) else "list"
    return type(v).__name__


@pytest.mark.parametrize("name, template", [("mock_lepak_results.json", "lepak_results.html"),
                                            ("mock_lepak_event.json", "event_detail.html")])
def test_lepak_fixtures_render(app, name, template):
    view = json.loads((FIXTURES / name).read_text())
    with app.test_request_context():
        from flask import render_template
        html = render_template(template, view=view)
    assert (view.get("heading") or view["title"]).replace("&", "&amp;") in html


def test_lepak_fixtures_match_what_the_app_produces(client):
    """Fails if the view model changes shape, until the fixtures are regenerated
    (python -m gowhere.web.mock) and the front end is told."""
    from gowhere.web import lepak_views
    import gowhere.web.routes as routes
    captured = {}
    original_results, original_event = lepak_views.results_view, lepak_views.event_view

    def cap(name, fn):
        def wrapper(*a):
            captured[name] = fn(*a)
            return captured[name]
        return wrapper
    routes.lepak_views.results_view = cap("results", original_results)
    routes.lepak_views.event_view = cap("event", original_event)
    try:
        client.post("/lepak", data=form(mode="drive"))
        client.get("/lepak/results")
        client.get(f"/lepak/events/{captured['results']['cards'][0]['id']}")
    finally:
        routes.lepak_views.results_view, routes.lepak_views.event_view = original_results, original_event
    fixture_results = json.loads((FIXTURES / "mock_lepak_results.json").read_text())
    fixture_event = json.loads((FIXTURES / "mock_lepak_event.json").read_text())
    assert _shape(captured["results"]).keys() == _shape(fixture_results).keys()
    assert _shape(captured["results"])["cards"][0].keys() == _shape(fixture_results)["cards"][0].keys()
    assert _shape(captured["event"]).keys() == _shape(fixture_event).keys()
