"""Where to Eat (DECISIONS.md sections 25 and 25a): opening hours, cuisine groups, the
offline build, the search and the screens. No network: places come from small fixtures
built through the same gowhere.eat.build path as data/eat.db."""
import html
import logging
import re
from datetime import datetime

import pytest

from gowhere.eat import build as eat_build
from gowhere.eat.cuisines import CUISINES, NOT_LISTED, groups_for, is_kopitiam
from gowhere.eat.hours import parse, status
from gowhere.eat.search import (DESTINATION_SLOTS, NOT_LISTED_SLOTS, ROUTE_BUDGET,
                                InvalidSearch, meal_time, nearest_within_reach, search,
                                sort_and_filter)
from gowhere.eat.store import PlaceStore
from tests.test_geo_spatial import AREAS

MONDAY_NOON = datetime(2026, 10, 19, 12, 0)


# ---- opening hours ----

@pytest.mark.parametrize("hours, when, open_, text", [
    ("Mo-Su 10:00-22:00", MONDAY_NOON, True, "Open until 10 pm"),
    ("Mo-Su 10:00-22:00", datetime(2026, 10, 19, 23, 0), False, "Closed, opens tomorrow 10 am"),
    ("24/7", MONDAY_NOON, True, "Open 24 hours"),
    ("18:00-02:00", datetime(2026, 10, 20, 1, 0), True, "Open until 2 am"),     # Tuesday 1 am
    ("Mo-Su 12:00-14:30, 18:00-22:30", datetime(2026, 10, 19, 16, 0), False, "Closed, opens 6 pm"),
    # comma-joined rules, and a later rule replacing an earlier one for its days
    ("Mo-Fr 07:30-19:30, Sa 07:30-14:00, Su off", datetime(2026, 10, 24, 15, 0), False,
     "Closed, opens Mon 7:30 am"),                       # Saturday afternoon, past Sunday off
    ("Mo-Su 10:00-22:00; Mo off", MONDAY_NOON, False, "Closed, opens tomorrow 10 am"),
    ("Sa,Su 10:00-22:00", MONDAY_NOON, False, "Closed, opens Sat 10 am"),
    ("Su-Th,PH 07:00-02:00; Fr-Sa 24/7", datetime(2026, 10, 24, 1, 0), True, "Open 24 hours"),
])
def test_opening_hours(hours, when, open_, text):
    assert status(hours, when) == {"open": open_, "text": text}


@pytest.mark.parametrize("hours", [None, "", '"varies by stall"', "Mo-Su 08:30-22:00; Mo[1] off",
                                   "Closed on weekends and Public Holidays", "Mo-Fr 25:00-26:00"])
def test_hours_outside_the_understood_subset_are_unknown_never_guessed(hours):
    assert parse(hours) is None
    assert status(hours, MONDAY_NOON) == {"open": None, "text": "Opening hours unknown"}


# ---- cuisine groups ----

def test_cuisine_groups():
    assert len(CUISINES) == 8 and "Seafood" not in CUISINES          # §25a
    assert groups_for("chinese;seafood") == ["Chinese"]
    assert groups_for("seafood") == []                              # not assumed Western
    assert groups_for("ramen;korean") == ["Japanese & Korean"]
    assert groups_for("Coffee_Shop") == ["Cafés & Desserts"]        # Starbucks, not kopitiams
    assert groups_for(None) == [] and groups_for("") == []


def test_kopitiams_are_found_by_name():
    assert is_kopitiam("Kim San Leng Kopitiam") and is_kopitiam("Hup Seng Eating House")
    assert is_kopitiam("Ah Huat Coffee Shop") and not is_kopitiam("Starbucks")


# ---- the offline build ----

def node(id_, lat, lon, **tags):
    return {"type": "node", "id": id_, "lat": lat, "lon": lon, "tags": tags}


def hawker(name, lon, lat, stalls, status="Existing"):
    return {"geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {"NAME": name, "STATUS": status, "NUMBER_OF_COOKED_FOOD_STALLS": stalls,
                           "ADDRESSBLOCKHOUSENUMBER": "1", "ADDRESSSTREETNAME": "Kopi Road",
                           "ADDRESSPOSTALCODE": "123456"}}


# WEST spans lon 103.70-103.80, EAST 103.80-103.90 (tests/test_geo_spatial.AREAS).
OSM = [
    node(1, 1.3500, 103.7500, amenity="restaurant", name="Ramen One", cuisine="ramen",
         opening_hours="Mo-Su 11:00-22:00", **{"addr:street": "West Street", "addr:housenumber": "5"}),
    node(2, 1.3502, 103.7502, amenity="cafe", name="Starbucks", cuisine="coffee_shop"),
    node(3, 1.3504, 103.7504, amenity="restaurant", name="Mystery Bistro"),          # no cuisine
    node(4, 1.3506, 103.7506, amenity="cafe", name="Kim San Leng Kopitiam"),
    node(5, 1.3600, 103.8500, amenity="food_court", name="East Food Centre"),       # = NEA centre
    node(6, 1.3800, 103.8800, amenity="food_court", name="Mall Food Court"),
    node(7, 1.3508, 103.7508, amenity="fast_food"),                                  # unnamed
    node(8, 1.2000, 103.9900, amenity="restaurant", name="Johor Place"),            # outside
]
HAWKERS = [hawker("East Food Centre", 103.8501, 1.3601, 80),
           hawker("Future Centre", 103.8600, 1.3700, 50, status="Under Construction")]


@pytest.fixture(scope="module")
def built():
    return eat_build.build(OSM, HAWKERS, AREAS)


def test_build_counts_every_drop(built):
    places, counts = built
    assert counts == {"osm_elements": 8, "hawker_centres": 1, "osm_outside_singapore": 1,
                      "osm_unnamed": 1, "osm_same_as_hawker_centre": 1, "places": 6}
    assert "Johor Place" not in {p["name"] for p in places}


def test_a_hawker_centre_is_one_entry_with_its_stall_count(built):
    places, _ = built
    centre = next(p for p in places if p["kind"] == "hawker_centre")
    assert centre["name"] == "East Food Centre" and centre["stalls"] == 80
    assert centre["destination"] == 1 and centre["source"] == "nea"
    assert centre["cuisines"] == ["Local & Hawker"] and centre["price_tier"] == "budget"
    assert sum(p["name"] == "East Food Centre" for p in places) == 1       # OSM copy dropped


def test_price_tier_and_cuisine_from_venue_type(built):
    by = {p["name"]: p for p in built[0]}
    assert by["Ramen One"]["price_tier"] == "restaurant"
    assert by["Ramen One"]["address"] == "5 West Street"
    assert by["Starbucks"]["price_tier"] == "casual"
    assert by["Starbucks"]["cuisines"] == ["Cafés & Desserts"]
    assert by["Kim San Leng Kopitiam"]["price_tier"] == "budget"
    assert by["Kim San Leng Kopitiam"]["cuisines"] == ["Local & Hawker"]
    assert by["Mystery Bistro"]["cuisines"] == []                            # shown as not listed
    assert by["Mall Food Court"]["destination"] == 1 and by["Mall Food Court"]["stalls"] is None
    assert by["Ramen One"]["source_url"] == "https://www.openstreetmap.org/node/1"


def test_coverage_is_measured_not_assumed(built):
    cov = eat_build.coverage(built[0])
    # OSM places: Ramen One, Starbucks, Kopitiam (by name), Mall Food Court listed; Bistro not.
    assert cov == {"cuisine_listed_pct": "80.0", "hours_known_pct": "16.7"}


@pytest.fixture
def store(built, tmp_path):
    path = tmp_path / "eat.db"
    eat_build.write(path, built[0], {"cuisine_listed_pct": "80.0", "hours_known_pct": "16.7",
                                     "osm_data_as_of": "2026-10-19",
                                     "hawker_data_as_of": "2026-09-30"})
    return PlaceStore.load(path), path


def test_write_and_load_round_trip(store):
    s, _ = store
    assert len(s.places) == 6 and s.meta["osm_data_as_of"] == "2026-10-19"
    p = s.get(s.places[0]["id"])
    assert isinstance(p["cuisines"], list) and isinstance(p["destination"], bool)


# ---- the Wikipedia "notable" badge ----

def test_notable_matches_only_an_article_that_names_the_place_itself():
    from gowhere.eat.notable import match, own_name
    assert own_name("LiHO - Seletar Mall") == "LiHO" and own_name("Ajisen @ AMK Hub") == "Ajisen"
    assert own_name("Maxwell Food Centre (Kim Hua Market)") == "Maxwell Food Centre"
    places = [{"name": "Maxwell Food Centre (Kim Hua Market)", "lat": 1.2803, "lon": 103.8447},
              {"name": "LiHO - Seletar Mall", "lat": 1.3916, "lon": 103.8760},
              {"name": "North Bridge Road Market", "lat": 1.3020, "lon": 103.8610},
              {"name": "Far Food Centre", "lat": 1.3500, "lon": 103.7500}]
    articles = [{"title": "Maxwell Food Centre", "lat": 1.2804, "lon": 103.8448},
                {"title": "Seletar Mall", "lat": 1.3917, "lon": 103.8761},        # the mall
                {"title": "North Bridge Road", "lat": 1.3021, "lon": 103.8611},   # the road
                {"title": "Far Food Centre", "lat": 1.3600, "lon": 103.7500}]     # 1.1 km off
    assert match(places, articles) == {0: "Maxwell Food Centre"}


def test_the_badge_says_notable_not_good(client):
    from gowhere.web import eat_views
    with client.application.test_request_context():
        c = eat_views.card({"id": 1, "name": "Newton Food Centre", "kind": "hawker_centre",
                            "stalls": 83, "price_tier": "budget", "cuisines": ["Local & Hawker"],
                            "address": None, "open": {"open": None, "text": "Opening hours unknown"},
                            "route": None, "distance_m": 100, "wikipedia_title": "Newton Food Centre"},
                           "pt")
    assert c["notable"]["url"] == "https://en.wikipedia.org/wiki/Newton_Food_Centre"
    assert "notable, not that the food is good" in c["notable"]["title"]


# ---- search ----

class Router:
    """Minutes = 1 + distance/100 m; anything named in `fail` is unroutable."""

    def __init__(self, fail=()):
        self.fail, self.calls = set(fail), []

    def route_many(self, origin, items, mode, now, departure=None):
        from gowhere.etl.geo import haversine_m
        self.calls.append({"n": len(items), "departure": departure})
        return {p["id"]: None if p["name"] in self.fail else
                {"minutes": 1 + haversine_m(*origin, p["lat"], p["lon"]) / 100, "mode": mode,
                 "summary": "Walk", "steps": [], "geometry": {"type": "LineString", "coordinates": []}}
                for p in items}


WEST = (1.3500, 103.7500)
ALL_TIERS = ["budget", "casual", "restaurant"]


def test_invalid_searches(store):
    places = store[0].places
    for args, message in [((["Seafood"], ALL_TIERS, "now", "pt", 15), "cuisines from the list"),
                          (([], [], "now", "pt", 15), "at least one kind"),
                          (([], ALL_TIERS, "brunch", "pt", 15), "when you want to eat"),
                          (([], ALL_TIERS, "now", "boat", 15), "travel mode"),
                          (([], ALL_TIERS, "now", "pt", 200), "5 to 90")]:
        with pytest.raises(InvalidSearch, match=message):
            search(places, WEST, *args, Router(), MONDAY_NOON)


def test_mealtime_is_the_next_one():
    assert meal_time("now", MONDAY_NOON) == MONDAY_NOON
    assert meal_time("dinner", MONDAY_NOON) == datetime(2026, 10, 19, 19, 0)
    assert meal_time("breakfast", MONDAY_NOON) == datetime(2026, 10, 20, 8, 30)   # tomorrow


def test_search_routes_at_the_mealtime_and_judges_open_then(store):
    router = Router()
    found = search(store[0].places, WEST, [], ALL_TIERS, "dinner", "walk", 30, router, MONDAY_NOON)
    assert router.calls[0]["departure"] == datetime(2026, 10, 19, 19, 0)
    by = {r["name"]: r for r in found["results"]}
    assert by["Ramen One"]["open"] == {"open": True, "text": "Open until 10 pm"}
    assert by["Mystery Bistro"]["open"]["open"] is None
    assert set(by) == {"Ramen One", "Starbucks", "Mystery Bistro", "Kim San Leng Kopitiam"}


def test_chosen_cuisine_keeps_unlisted_places_labelled(store):
    found = search(store[0].places, WEST, ["Japanese & Korean"], ALL_TIERS, "now", "walk", 30,
                   Router(), MONDAY_NOON)
    assert {r["name"] for r in found["results"]} == {"Ramen One", "Mystery Bistro"}
    page, total, _ = sort_and_filter(found["results"], hidden=[NOT_LISTED])
    assert [r["name"] for r in page] == ["Ramen One"] and total == 1


def test_unroutable_places_are_kept_as_estimates_and_slow_ones_dropped(store):
    found = search(store[0].places, WEST, [], ["restaurant"], "now", "walk", 30,
                   Router(fail={"Mystery Bistro"}), MONDAY_NOON)
    by = {r["name"]: r for r in found["results"]}
    assert by["Mystery Bistro"]["route"] is None and by["Mystery Bistro"]["minutes"] is None
    page, _, _ = sort_and_filter(found["results"], "nearest")
    assert page[-1]["name"] == "Mystery Bistro"                      # listed last
    class Slow(Router):
        def route_many(self, *a, **kw):
            return {k: v and {**v, "minutes": v["minutes"] + 30}
                    for k, v in super().route_many(*a, **kw).items()}
    slow = search(store[0].places, WEST, [], ["restaurant"], "now", "walk", 5,
                  Slow(fail={"Mystery Bistro"}), MONDAY_NOON)
    assert [r["name"] for r in slow["results"]] == ["Mystery Bistro"]    # only the estimate


def _grid(n, destination_every=0, unlisted_every=0):
    out = []
    for i in range(n):
        out.append({"id": i, "name": f"P{i}", "lat": 1.35 + i * 0.0001, "lon": 103.75,
                    "destination": bool(destination_every and i % destination_every == 0),
                    "cuisines": [] if unlisted_every and i % unlisted_every == 0 else ["Chinese"],
                    "price_tier": "restaurant", "stalls": None, "opening_hours": None})
    return out


def test_route_budget_and_its_reservations():
    places = _grid(200, destination_every=50, unlisted_every=2)
    chosen, within = nearest_within_reach(places, WEST, "walk", 30, cuisines_chosen=True)
    assert within == 200 and len(chosen) == ROUTE_BUDGET
    assert sum(p["destination"] for p in chosen) == 4 <= DESTINATION_SLOTS    # all 4 kept
    assert sum(not p["cuisines"] for p in chosen) <= NOT_LISTED_SLOTS + 4     # + destinations
    nothing_chosen, _ = nearest_within_reach(places, WEST, "walk", 30)
    assert sum(not p["cuisines"] for p in nothing_chosen) > NOT_LISTED_SLOTS  # no cap when "any"


def test_sorts():
    rows = [{"name": "A", "minutes": 5, "distance_m": 100, "destination": False, "stalls": None,
             "open": {"open": None}, "cuisines": ["Chinese"]},
            {"name": "B", "minutes": 9, "distance_m": 300, "destination": True, "stalls": 80,
             "open": {"open": True}, "cuisines": ["Local & Hawker"]},
            {"name": "C", "minutes": 7, "distance_m": 200, "destination": False, "stalls": None,
             "open": {"open": False}, "cuisines": []}]
    order = lambda sort: [r["name"] for r in sort_and_filter(rows, sort)[0]]
    assert order("nearest") == ["A", "C", "B"]
    assert order("open") == ["B", "A", "C"]          # open, unknown, closed
    assert order("variety") == ["B", "A", "C"]       # most stalls first


def test_with_a_cuisine_chosen_unlisted_places_come_after_every_match():
    rows = [{"name": "Near unlisted", "minutes": 1, "distance_m": 50, "destination": False,
             "stalls": None, "open": {"open": True}, "cuisines": []},
            {"name": "Far match", "minutes": 9, "distance_m": 900, "destination": False,
             "stalls": None, "open": {"open": None}, "cuisines": ["Chinese"]}]
    names = lambda **kw: [r["name"] for r in sort_and_filter(rows, **kw)[0]]
    assert names(sort="nearest") == ["Near unlisted", "Far match"]          # "any cuisine"
    for sort in ("nearest", "open", "variety"):
        assert names(sort=sort, cuisine_filter=True) == ["Far match", "Near unlisted"]


# ---- the screens ----

POSTAL = "238801"


class Locations:
    def postal(self, code):
        return WEST


@pytest.fixture
def client(store, tmp_path):
    from gowhere.web import create_app
    app = create_app({"SECRET_KEY": "t", "TESTING": True, "EAT_PATH": store[1],
                      "EVENTS_PATH": tmp_path / "e.db", "LOCATION_FACTORY": Locations,
                      "EVENT_ROUTER_FACTORY": Router, "NOW": lambda: MONDAY_NOON})
    return app.test_client()


def form(**over):
    return {"cuisines": ["Japanese & Korean", "Local & Hawker"], "tiers": ALL_TIERS,
            "when": "lunch", "mode": "walk", "max_minutes": "30", "origin": "postal",
            "postal": POSTAL, **over}


def test_search_results_and_detail(client):
    r = client.post("/eat", data=form())
    assert r.status_code == 303 and r.headers["Location"].endswith("/eat/results")
    page = html.unescape(client.get("/eat/results").get_data(as_text=True))
    assert "places within 30 min by walking, for lunch today (12:30 pm)" in page
    assert "Cuisine is listed for 80% of places" in page                  # coverage stated
    assert page.count("<article>") == 3                    # Ramen, Kopitiam, Bistro (not listed)
    assert "Cuisine not listed" in page and "Opening hours unknown" in page
    pid = re.search(r"/eat/places/(\d+)", page).group(1)
    detail = html.unescape(client.get(f"/eat/places/{pid}").get_data(as_text=True))
    assert '"kind": "start"' in detail and "Back to results" in detail
    assert client.get("/eat/places/999999").status_code == 404


def test_sort_chips_and_paging_call_nothing(client):
    client.post("/eat", data=form())
    app = client.application
    before = len(app.extensions["gowhere"]["store"]._sessions)
    for q in ("?sort=open", "?sort=variety", "?hide=Cuisine+not+listed", "?page=9"):
        assert client.get("/eat/results" + q).status_code == 200
    page = client.get("/eat/results?hide=Cuisine+not+listed").get_data(as_text=True)
    assert page.count("<article>") == 2
    assert len(app.extensions["gowhere"]["store"]._sessions) == before


def test_errors_are_sentences_and_never_echo_the_postal_code(client):
    r = client.post("/eat", data=form(tiers=[]))
    assert r.status_code == 400 and "Choose at least one kind of place." in r.get_data(as_text=True)
    r = client.post("/eat", data=form(postal="12345"))
    assert r.status_code == 400 and "Enter a 6-digit Singapore postal code." in r.get_data(as_text=True)


def test_postal_code_never_in_url_cookie_or_logs(client, caplog):
    caplog.set_level(logging.DEBUG)
    r = client.post("/eat", data=form())
    assert POSTAL not in r.headers["Location"]
    cookie = r.headers.get("Set-Cookie", "")
    assert POSTAL not in cookie
    raw = cookie.split("=", 1)[1].split(";", 1)[0]
    app = client.application
    assert set(app.session_interface.get_signing_serializer(app).loads(raw)) == {"sid"}
    assert POSTAL not in client.get("/eat/results").get_data(as_text=True)
    assert POSTAL not in caplog.text


def test_home_and_nav_link_to_where_to_eat(client):
    page = client.get("/").get_data(as_text=True)
    assert page.count('href="/eat"') >= 2                # the nav link and the home card
