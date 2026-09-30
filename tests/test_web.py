"""Web app, end to end against a tiny six-factor snapshot built from fakes."""
import json
import logging

import pytest

from gowhere.config import ROOT
from gowhere.etl.build_snapshot import compute, write_snapshot
from gowhere.scoring.registry import default_strategies
from gowhere.web import create_app
from gowhere.web.mock import FixedRouter
from gowhere.web.view_models import dropped_messages, recommendation
from tests.fakes import FakeSources
from tests.test_geo_spatial import AREAS

POSTAL = "048583"
FIXTURES = ROOT / "tests" / "fixtures"


class AllSources(FakeSources):
    def __init__(self):
        pt = lambda lat, lon, name="x": {"name": name, "lat": lat, "lon": lon}
        super().__init__(
            exits=[{"station": "W MRT STATION", "exit_code": "A", "lat": 1.3505, "lon": 103.75}],
            parks=[{"name": "P", "geometry": {"type": "Polygon", "coordinates": [[
                [103.749, 1.349], [103.751, 1.349], [103.751, 1.351], [103.749, 1.351], [103.749, 1.349]]]}}],
            connectors=[{"name": "L", "geometry": {"type": "LineString",
                                                   "coordinates": [[103.85, 1.30], [103.85, 1.31]]}}],
            facilities={"gp": [pt(1.35, 103.752)], "polyclinic": [pt(1.35, 103.86)],
                        "hospital": [pt(1.36, 103.80)]})

    def resale(self):
        tx = lambda blk, street, price: {"month": "2026-01", "flat_type": "4 ROOM", "blk_no": blk,
                                         "street": street, "resale_price": price,
                                         "remaining_lease_months": 900}
        return (["2025-09", "2026-08"],
                [tx(str(i), "W", 500_000 + 10_000 * i) for i in range(12)]
                + [tx("1", "E", 500_000), tx("1", "E", 600_000)])

    def amenities(self):
        near_w = [{"name": "a", "lat": 1.3501, "lon": 103.7501}]
        return {"supermarket": near_w, "hawker_centre": near_w, "library": [], "mall": [],
                "gym": [], "cafe": near_w * 5}

    def amenities_as_of(self):
        return {"supermarket": "2024-06-06", "hawker_centre": "2026-03-13",
                "library": "2026-08-31", "osm": "2026-09-30"}

    def amenities_meta(self):
        return {"supermarket_licences": 1, "supermarkets_unlocated": 0}

    def facilities_as_of(self):
        return {"gp": "2021-09-26", "polyclinic": "2026-09-30", "hospital": "2026-09-30"}


class RecordingRouter(FixedRouter):
    calls = []

    def locate(self, postal):
        RecordingRouter.calls.append("locate")
        return super().locate(postal)

    def minutes(self, origins, postal, mode):
        RecordingRouter.calls.append("minutes")
        return super().minutes(origins, postal, mode)


@pytest.fixture
def app(tmp_path):
    blocks = [{"blk_no": str(i), "street": "W", "total_dwelling_units": 100} for i in range(12)]
    blocks.append({"blk_no": "1", "street": "E", "total_dwelling_units": 55})
    geocodes = ([{"blk_no": str(i), "street": "W", "status": "ok", "lat": 1.35,
                  "lon": 103.75 + i * 0.0005, "detail": ""} for i in range(12)]
                + [{"blk_no": "1", "street": "E", "status": "ok", "lat": 1.35, "lon": 103.85, "detail": ""}])
    sources, strategies = AllSources(), default_strategies(FixedRouter({}))
    out = compute(blocks, geocodes, AREAS, sources, strategies)
    meta = {"generated_at": "2026-09-30T09:00:00+00:00", "small_area_blocks": "10"}
    for s in strategies:
        meta.update(s.meta(sources))
    path = tmp_path / "snapshot.db"
    write_snapshot(path, out, AREAS, strategies, meta)
    RecordingRouter.calls = []
    return create_app({"SNAPSHOT_PATH": path, "SECRET_KEY": "test", "TESTING": True,
                       "ROUTER_FACTORY": lambda: RecordingRouter({"WEST": 30.0, "EAST": 50.0})})


@pytest.fixture
def client(app):
    return app.test_client()


def form(**over):
    data = {"areas": ["WEST", "EAST"], "include_public_transport": "1", "weight_public_transport": "5",
            "include_greenery": "1", "weight_greenery": "5"}
    data.update(over)
    return data


def test_pages_render(client):
    assert client.get("/").status_code == 200
    page = client.get("/live")
    assert page.status_code == 200 and b"West" in page.data and b"Empty" not in page.data
    for url in ("/lepak", "/lepak/results", "/lepak/events/42"):
        assert client.get(url).status_code == 501
    assert client.get("/nope").status_code == 404


def test_results_before_any_submission_redirects_to_setup(client):
    r = client.get("/live/results")
    assert r.status_code == 302 and r.headers["Location"].endswith("/live")


def test_submit_then_results(client):
    r = client.post("/live", data=form())
    assert r.status_code == 303 and r.headers["Location"].endswith("/live/results")
    page = client.get("/live/results").get_data(as_text=True)
    assert "ranks first" in page and "1st" in page and "2nd" in page
    assert "East — 55 flats across 1 block. Scores are based on a small number of blocks." in page


def test_dropped_factor_named_with_area_and_reason(client):
    client.post("/live", data=form(include_housing_affordability="1", weight_housing_affordability="5",
                                   flat_type="4 ROOM", budget_min="400000", budget_max="700000",
                                   min_remaining_lease_years=""))
    page = client.get("/live/results").get_data(as_text=True)
    assert ("Housing Affordability was left out because East had fewer than 10 matching resales."
            in page)


@pytest.mark.parametrize("over, message", [
    ({"areas": ["WEST"]}, "select 2 to 4"),
    ({"weight_greenery": "eleven"}, "whole number"),
    ({"weight_greenery": "11"}, "weight must be"),
    ({"include_housing_affordability": "1", "weight_housing_affordability": "5",
      "flat_type": "4 ROOM", "budget_min": "700000", "budget_max": "400000"},
     "budget minimum must not exceed"),
])
def test_invalid_submissions_rerender_setup_with_message(client, over, message):
    r = client.post("/live", data=form(**over))
    assert r.status_code == 400 and message in r.get_data(as_text=True)


def test_selection_time_check_warns_without_touching_commute(client):
    r = client.post("/live/check", data=form(
        include_housing_affordability="1", weight_housing_affordability="5", flat_type="4 ROOM",
        budget_min="400000", budget_max="700000", min_remaining_lease_years="",
        include_commute="1", weight_commute="5", destination_postal=POSTAL, mode="pt"))
    assert r.get_json()["warnings"] == [
        "Housing Affordability was left out because East had fewer than 10 matching resales."]
    assert RecordingRouter.calls == []          # Commute never checked, so OneMap never called
    r = client.post("/live/check", data=form(areas=["WEST"]))
    assert r.get_json()["incomplete"].startswith("select 2 to 4")


# ---- Security NFR: the destination postal code stays in server memory ----

def test_postal_code_never_in_url_cookie_or_logs(app, client, caplog):
    caplog.set_level(logging.DEBUG)
    r = client.post("/live", data=form(include_commute="1", weight_commute="5",
                                       destination_postal=POSTAL, mode="pt"))
    assert r.status_code == 303 and POSTAL not in r.headers["Location"]
    cookie = r.headers.get("Set-Cookie", "")
    assert POSTAL not in cookie
    raw = cookie.split("=", 1)[1].split(";", 1)[0]
    contents = app.session_interface.get_signing_serializer(app).loads(raw)
    assert set(contents) == {"sid"}             # the cookie holds only the opaque id
    results = client.get("/live/results").get_data(as_text=True)
    assert "30 min by public transport" in results and POSTAL not in results
    assert POSTAL not in caplog.text


# ---- the front-end contract ----

def _shape(v):
    """Structure of a JSON value: dict keys and list element shapes, not the values."""
    if isinstance(v, dict):
        return {k: _shape(x) for k, x in v.items() if k != "geometry"}
    if isinstance(v, list):
        return [_shape(v[0])] if v and isinstance(v[0], (dict, list)) else "list"
    return type(v).__name__


@pytest.mark.parametrize("name", ["mock_results.json", "mock_results_all_scored.json"])
def test_fixture_renders_in_the_results_template(app, name):
    view = json.loads((FIXTURES / name).read_text())
    with app.test_request_context():
        from flask import render_template
        html = render_template("live_results.html", view=view)
    assert view["recommendation"]["headline"] in html
    for area in view["areas"]:
        assert area["name"] in html


def test_fixture_matches_what_the_app_produces(client):
    """If the view model changes shape, this fails until the fixture is regenerated
    (python -m gowhere.web.mock) and the front end is told."""
    fixture = json.loads((FIXTURES / "mock_results_all_scored.json").read_text())
    client.post("/live", data=form())
    from gowhere.web import view_models
    live = {}
    original = view_models.results_view

    def capture(result, snapshot):
        live.update(original(result, snapshot))
        return live
    import gowhere.web.routes as routes
    routes.results_view = capture
    try:
        client.get("/live/results")
    finally:
        routes.results_view = original
    assert _shape(live)["areas"][0].keys() == _shape(fixture)["areas"][0].keys()
    assert _shape(live).keys() == _shape(fixture).keys()
    assert _shape(live)["recommendation"] == _shape(fixture)["recommendation"]


def test_contract_fixture_covers_the_required_cases():
    v = json.loads((FIXTURES / "mock_results.json").read_text())
    notes = [n for a in v["areas"] for n in a["notes"]]
    factor_notes = " ".join(n for f in v["factors"] for n in f["notes"])
    assert len(v["areas"]) == 4 and v["dropped"]
    assert any("small number of blocks" in n for n in notes)
    assert any("station-exit data" in n for n in notes)
    assert "Commute is timed" in factor_notes and "CHAS" in factor_notes
    scored = json.loads((FIXTURES / "mock_results_all_scored.json").read_text())
    assert len(scored["factors"]) == 6
    assert "resale transactions registered" in " ".join(n for f in scored["factors"] for n in f["notes"])


def test_view_model_wording():
    assert dropped_messages([{"label": "Commute", "missing_for": ["ANG MO KIO", "BEDOK"],
                              "reason": "could not be routed to your destination"}]) == [
        "Commute was left out because Ang Mo Kio and Bedok could not be routed to your destination."]
    result = {"explanation": {"winner": "A", "runner_up": "B", "factors": [
                  {"label": "X", "contribution": 12.0}, {"label": "Y", "contribution": -3.5}]},
              "areas": [{"rank": 1, "overall_display": 6.2}, {"rank": 1, "overall_display": 6.2}],
              "close_call": True}
    rec = recommendation(result)
    assert rec["headline"] == "A and B are joint first with 6.2 out of 10."
    assert rec["because"] == "" and "could swap them" in rec["close_call_text"]
    assert rec["reasons"][1] == {"label": "Y", "contribution": "3.5", "favours": "B"}
