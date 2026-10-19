"""Google ratings (DECISIONS.md section 29): the daily cap, key redaction, name checks,
the sort and the screens. A fake session stands in for Google; nothing here calls it."""
import html
import logging
from datetime import date, datetime

import pytest

from gowhere.adapters.google_places import (DETAILS_FIELDS, DailyCap, GooglePlacesAdapter,
                                            PlacesError)
from gowhere.eat import google_ids, ratings
from gowhere.eat.search import sort_and_filter

KEY = "AIzaTESTKEY0123456789abcdefghij"


class Resp:
    def __init__(self, status=200, body=None):
        self.status_code, self._body = status, body or {}

    def json(self):
        return self._body


class FakeSession:
    def __init__(self, reply=None, raises=None):
        self.reply, self.raises, self.calls = reply or Resp(), raises, []

    def request(self, method, url, headers=None, json=None, timeout=None):
        self.calls.append({"method": method, "url": url, "headers": headers, "json": json})
        if self.raises:
            raise self.raises
        return self.reply


DETAILS = Resp(body={"id": "g1", "displayName": {"text": "Newton Food Centre"}, "rating": 4.2,
                     "userRatingCount": 1234, "googleMapsUri": "https://maps.google.com/?cid=1"})


# ---- the daily cap ----

def test_daily_cap_counts_and_resets_each_singapore_day():
    day = [datetime(2026, 10, 19, 23, 0)]
    cap = DailyCap(2, clock=lambda: day[0])
    assert [cap.take(), cap.take(), cap.take()] == [True, True, False]
    assert cap.used == 2
    day[0] = datetime(2026, 10, 20, 0, 1)
    assert cap.used == 0 and cap.take()


def test_once_the_cap_is_spent_google_is_not_called_at_all():
    session = FakeSession(DETAILS)
    adapter = GooglePlacesAdapter(key=KEY, session=session, daily_cap=3)
    answers = [adapter.details("g1") for _ in range(5)]
    assert [a is not None for a in answers] == [True, True, True, False, False]
    assert len(session.calls) == 3                       # the 4th and 5th never left


def test_the_default_cap_stays_inside_googles_free_tier():
    from gowhere import config
    assert config.GOOGLE_DAILY_CAP * 31 <= 1000         # Place Details Enterprise: 1,000 free


# ---- the calls ----

def test_details_asks_for_the_rating_fields_with_the_key_in_a_header():
    session = FakeSession(DETAILS)
    got = GooglePlacesAdapter(key=KEY, session=session).details("g1")
    assert got == {"rating": 4.2, "count": 1234, "name": "Newton Food Centre",
                   "maps_url": "https://maps.google.com/?cid=1"}
    call = session.calls[0]
    assert call["headers"] == {"X-Goog-Api-Key": KEY, "X-Goog-FieldMask": DETAILS_FIELDS}
    assert KEY not in call["url"]


def test_find_place_id_asks_for_the_id_only():
    session = FakeSession(Resp(body={"places": [{"id": "g42"}]}))
    assert GooglePlacesAdapter(key=KEY, session=session).find_place_id("Maxwell", 1.28, 103.84) == "g42"
    call = session.calls[0]
    assert call["headers"]["X-Goog-FieldMask"] == "places.id"     # IDs Only: free SKU
    assert call["json"]["locationBias"]["circle"]["radius"] == 100.0


def test_no_key_means_no_ratings_and_a_clear_offline_error():
    adapter = GooglePlacesAdapter(key="", session=FakeSession(DETAILS))
    assert adapter.details("g1") is None and adapter.session.calls == []
    with pytest.raises(PlacesError, match="GOOGLE_MAPS_API_KEY is not set"):
        adapter.find_place_id("x", 1.3, 103.8)


def test_the_key_never_reaches_error_text_or_logs(caplog):
    import requests
    leaky = requests.ConnectionError(f"failed for https://x/?key={KEY}")
    adapter = GooglePlacesAdapter(key=KEY, session=FakeSession(raises=leaky))
    with caplog.at_level(logging.DEBUG):
        assert adapter.details("g1") is None                       # swallowed, logged
        with pytest.raises(PlacesError) as err:
            adapter.find_place_id("x", 1.3, 103.8)
    assert KEY not in str(err.value) and "[redacted]" in str(err.value)
    assert err.value.__cause__ is None
    assert KEY not in caplog.text


# ---- attaching ratings to results ----

class FakeAdapter:
    configured = True

    def __init__(self, answers):
        self.answers, self.asked = answers, []

    def details(self, place_id):
        self.asked.append(place_id)
        return self.answers.get(place_id)


def test_ratings_are_kept_only_when_googles_name_matches_ours():
    results = [{"name": "Newton Food Centre", "google_place_id": "g1"},
               {"name": "Ah Hock Fried Oyster", "google_place_id": "g2"},     # wrong place
               {"name": "Kopi Corner", "google_place_id": "g3"},              # no rating
               {"name": "No Id Cafe", "google_place_id": None}]
    adapter = FakeAdapter({
        "g1": {"rating": 4.2, "count": 1234, "name": "Newton Food Centre", "maps_url": "u1"},
        "g2": {"rating": 4.9, "count": 50, "name": "Marina Bay Sands", "maps_url": "u2"},
        "g3": {"rating": None, "count": 0, "name": "Kopi Corner", "maps_url": "u3"}})
    ratings.attach(results, adapter)
    assert results[0]["rating"] == {"value": 4.2, "count": 1234, "maps_url": "u1"}
    assert [r["rating"] for r in results[1:]] == [None, None, None]
    assert sorted(adapter.asked) == ["g1", "g2", "g3"]            # no call without an ID


def test_without_an_adapter_nothing_is_asked():
    results = [{"name": "A", "google_place_id": "g1"}]
    assert ratings.attach(results, None) == 0 and results[0]["rating"] is None


def test_highest_rated_sort_puts_unrated_after_rated_not_at_the_bottom_by_score():
    row = lambda name, minutes, rating=None: {"name": name, "minutes": minutes, "distance_m": minutes,
                                              "destination": False, "stalls": None, "cuisines": ["Chinese"],
                                              "open": {"open": None},
                                              "rating": rating and {"value": rating[0], "count": rating[1]}}
    rows = [row("Unrated near", 1), row("Good", 9, (4.6, 100)), row("Better", 7, (4.6, 900)),
            row("Okay", 3, (3.9, 50))]
    order = [r["name"] for r in sort_and_filter(rows, "rated")[0]]
    assert order == ["Better", "Good", "Okay", "Unrated near"]


# ---- offline place-ID resolution ----

def test_resolve_skips_known_places_and_stops_cleanly_on_error():
    places = [{"name": n, "lat": 1.3, "lon": 103.8, "source_url": f"u{i}"}
              for i, n in enumerate(["A", "B", "C"])]

    class Adapter:
        def __init__(self):
            self.asked = []

        def find_place_id(self, name, lat, lon):
            self.asked.append(name)
            if name == "C":
                raise PlacesError("HTTP 429")
            return f"id-{name}"
    a = Adapter()
    ids = google_ids.resolve(places, a, known={"u0": "id-A"}, sleep=lambda s: None)
    assert ids == {"u0": "id-A", "u1": "id-B"} and a.asked == ["B", "C"]


# ---- the screens ----

def test_results_show_ratings_with_google_attribution_and_the_rated_sort(tmp_path):
    from tests.test_eat import ALL_TIERS, MONDAY_NOON, POSTAL, Locations, Router, OSM, HAWKERS
    from gowhere.eat import build as eat_build
    from tests.test_geo_spatial import AREAS
    places, _ = eat_build.build(OSM, HAWKERS, AREAS)
    for p in places:
        p["google_place_id"] = "g-" + p["name"]
    path = tmp_path / "eat.db"
    eat_build.write(path, places, {"cuisine_listed_pct": "80.0", "hours_known_pct": "16.7",
                                   "osm_data_as_of": "2026-10-19", "hawker_data_as_of": "2026-09-30"})
    answers = {"g-Ramen One": {"rating": 4.4, "count": 321, "name": "Ramen One", "maps_url": "https://maps.google.com/?cid=9"}}
    from gowhere.web import create_app
    app = create_app({"SECRET_KEY": "t", "TESTING": True, "EAT_PATH": path,
                      "EVENTS_PATH": tmp_path / "e.db", "LOCATION_FACTORY": Locations,
                      "EVENT_ROUTER_FACTORY": Router, "NOW": lambda: MONDAY_NOON,
                      "RATINGS_FACTORY": lambda: FakeAdapter(answers)})
    c = app.test_client()
    form = {"tiers": ALL_TIERS, "when": "now", "mode": "walk", "max_minutes": "30",
            "origin": "postal", "postal": POSTAL}
    assert c.post("/eat", data=form).status_code == 303
    page = html.unescape(c.get("/eat/results").get_data(as_text=True))
    assert "★ 4.4" in page and "321 reviews" in page
    assert '<span class="google-attribution">Google Maps</span>' in page
    assert "https://maps.google.com/?cid=9" in page
    assert "Highest rated" in page and "not a low one" in page
    first = html.unescape(c.get("/eat/results?sort=rated").get_data(as_text=True))
    assert first.index("Ramen One") < first.index("Starbucks")

    app.config["RATINGS_FACTORY"] = lambda: None                # no key / no ratings
    c.post("/eat", data=form)
    plain = c.get("/eat/results?sort=rated").get_data(as_text=True)
    assert "Highest rated" not in plain and "google-attribution" not in plain
