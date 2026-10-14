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
    assert "(straight-line estimate, no route available)" in page and "listed last" in page
    assert "https://t.me/sgwhereto/4497" in page


def test_sorting_chips_and_paging_call_nothing(app, client):
    client.post("/lepak", data=form(mode="drive"))
    router, datamall = app.routers[-1], app.extensions["gowhere"]["parking"].adapter
    before = (router.calls, datamall.calls, len(FakeLocations.calls))
    for query in ("?sort=soonest", "?sort=recent", "?hide=Family+%26+Kids",
                  "?hide=Arts+%26+Culture&hide=Sales+%26+Pop-ups&sort=soonest&page=2",
                  "?page=7", "?sort=bogus", "?hide=Not+a+category"):
        assert client.get("/lepak/results" + query).status_code == 200
    assert (router.calls, datamall.calls, len(FakeLocations.calls)) == before


def test_category_chips_hide_independently(client):
    """FR 2.4.2: hide one category and keep the rest; each chip toggles on its own."""
    client.post("/lepak", data=form())
    page = client.get("/lepak/results?hide=Family+%26+Kids").get_data(as_text=True)
    assert "Free Yukata Experience" not in page and "Anime Earth" in page
    assert "Seoul Anthem K-pop Party" in page
    both = client.get("/lepak/results?hide=Family+%26+Kids&hide=Arts+%26+Culture").get_data(as_text=True)
    assert "Anime Earth" not in both and "Seoul Anthem K-pop Party" in both
    # The Family & Kids chip on that page shows it again, keeping Arts & Culture hidden.
    import html, re
    chip = re.search(r'<a class="pill" href="([^"]+)"\s+aria-pressed="false">Family', page)
    assert chip and "hide=" not in html.unescape(chip.group(1))


def test_returning_from_an_event_restores_the_results_view(client):
    """FR 2.5.3: sort order, hidden categories and page come back."""
    import html, re
    client.post("/lepak", data=form())
    client.get("/lepak/results?sort=soonest&hide=Family+%26+Kids")
    events = EventStore(client.application.config["EVENTS_PATH"]).events(LEPAK_NOW)
    anime = next(e for e in events if e["title"] == "Anime Earth")
    detail = client.get(f"/lepak/events/{anime['id']}").get_data(as_text=True)
    back = html.unescape(re.search(r'href="([^"]*/lepak/results[^"]*)">Back', detail).group(1))
    assert "sort=soonest" in back and "hide=Family+%26+Kids" in back and "page=1" in back


def test_freshness_line_and_stale_warning(app, client):
    """FR 2.3.4: how long ago events were updated; a warning past 24 hours."""
    from datetime import timedelta
    client.post("/lepak", data=form())
    page = client.get("/lepak/results").get_data(as_text=True)
    assert "Events last updated just now." in page and "more than 24 hours" not in page
    app.config["NOW"] = lambda: LEPAK_NOW + timedelta(hours=25)
    page = client.get("/lepak/results").get_data(as_text=True)
    assert "Events last updated 25 hours ago." in page
    assert "Events have not been updated for more than 24 hours" in page


def test_a_failed_run_does_not_count_as_an_update(tmp_path):
    from datetime import datetime
    store = EventStore(tmp_path / "e.db")
    store.record_run(datetime(2026, 10, 1, 9), datetime(2026, 10, 1, 9, 5), {"posts_seen": 3})
    store.record_run(datetime(2026, 10, 2, 9), datetime(2026, 10, 2, 9, 5), {"llm_failures": 1})
    assert store.last_updated() == datetime(2026, 10, 1, 9, 5)
    assert EventStore(tmp_path / "none.db").last_updated() is None


def test_paging(client, monkeypatch):
    monkeypatch.setattr("gowhere.lepak.search.PAGE_SIZE", 4)     # 9 fixture events -> 3 pages
    client.post("/lepak", data=form())
    page = client.get("/lepak/results").get_data(as_text=True)
    assert page.count("<article>") == 4 and "Page 1 of 3" in page
    assert client.get("/lepak/results?page=3").get_data(as_text=True).count("<article>") == 1


@pytest.mark.parametrize("over, message", [
    ({"categories": []}, "Choose 1 to 4 categories"),
    ({"categories": ["Arts & Culture", "Music & Performances", "Family & Kids",
                     "Sales & Pop-ups", "Community"]}, "Choose 1 to 4 categories"),
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


@pytest.mark.parametrize("postal, status, text", [
    ("560123", 303, None),
    ("238801", 400, "we can only look up HDB block postal codes, and this one isn&#39;t one"),
])
def test_offline_postal_codes(app, client, postal, status, text):
    from gowhere.services.location import LocationService
    from tests.fakes import RecordedSearch
    app.config["LOCATION_FACTORY"] = lambda: LocationService(
        RecordedSearch({}, fail=True), offline_postal={"560123": (1.37, 103.85)}.get)
    r = client.post("/lepak", data=form(postal=postal))
    assert r.status_code == status
    if text:
        page = r.get_data(as_text=True)
        assert text in page and "couldn&#39;t find that postal code" not in page


def test_one_category_is_enough(client):
    assert client.post("/lepak", data=form(categories=["Community"])).status_code == 303


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
    assert '"kind": "start"' in page and "Directions" in page   # FR 2.5.2: start marker, steps
    # Straight to the page with no search: the event, without travel time or route.
    fresh = client.application.test_client().get(f"/lepak/events/{anime['id']}")
    assert fresh.status_code == 200 and "min by" not in fresh.get_data(as_text=True)
    assert client.get("/lepak/events/9999").status_code == 404


def test_unroutable_event_map_still_shows_where_you_start(client):
    """Offline or unroutable: venue and start, so the straight-line estimate has two
    points on the map rather than one pin on a blank background."""
    client.post("/lepak", data=form())
    events = EventStore(client.application.config["EVENTS_PATH"]).events(LEPAK_NOW)
    bellygom = next(e for e in events if e["title"] == "BellyGom Summer Day Out Party")
    page = client.get(f"/lepak/events/{bellygom['id']}").get_data(as_text=True)
    assert "straight-line estimate" in page
    assert '"kind": "start"' in page and '"kind": "venue"' in page
    assert '"kind": "route"' not in page and "Directions" not in page


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


def test_travel_wording_says_what_each_figure_is():
    from gowhere.web.lepak_views import travel_text
    walked = {"route": {"minutes": 6.2, "mode": "walk"}}
    assert travel_text(walked, "pt") == ("6 min on foot (walking route: no public transport "
                                         "route was found for this short trip)")
    assert travel_text({"route": {"minutes": 6.2, "mode": "pt"}}, "pt") == "6 min by public transport"
    assert travel_text({"route": None, "distance_m": 2449.0}, "pt") == (
        "About 2.4 km away (straight-line estimate, no route available)")
    assert travel_text({"route": None, "distance_m": 384.0}, "drive").startswith("About 380 m away")


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
        def wrapper(*a, **kw):
            captured[name] = fn(*a, **kw)
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
