"""Regenerate the front-end contract fixtures from the real engine and snapshot.

    python -m gowhere.web.mock

Commute uses FixedRouter (fixed minutes, no network, no real destination), so the
fixtures are reproducible for a given snapshot. The Where to Lepak fixtures come from the
ingestion fixtures (tests/fixtures/lepak) run through the real pipeline, with
FixedEventRouter for travel times and a parking service that cannot reach DataMall.
"""
import json
from datetime import datetime

from gowhere import config
from gowhere.scoring.engine import FactorChoice, ScoringEngine
from gowhere.scoring.registry import default_strategies
from gowhere.snapshot import Snapshot
from gowhere.web.view_models import results_view

FIXTURE_DIR = config.ROOT / "tests" / "fixtures"
EXAMPLE_POSTAL = "000000"   # placeholder; FixedRouter never looks it up


class FixedRouter:
    """A CommuteRouter stand-in returning fixed minutes per area."""

    def __init__(self, minutes):
        self._minutes = minutes

    def locate(self, postal):
        return (1.3, 103.8)

    def minutes(self, origins, postal, mode):
        return {a: self._minutes.get(a) for a in origins}


def _choices(facility_type):
    return {
        "public_transport": FactorChoice(8),
        "housing_affordability": FactorChoice(7, {"flat_type": "4 ROOM", "budget_min": 400_000,
                                                  "budget_max": 700_000,
                                                  "min_remaining_lease_years": 60}),
        "amenities": FactorChoice(5, {"amenity_types": ["supermarket", "hawker_centre", "cafe"]}),
        "greenery": FactorChoice(4),
        "healthcare": FactorChoice(5, {"facility_type": facility_type}),
        "commute": FactorChoice(6, {"destination_postal": EXAMPLE_POSTAL, "mode": "pt"}),
    }


SCENARIOS = {
    # Changi: small-area note, far-from-rail note, and too few resales -> Housing dropped.
    # Tengah: far-from-rail note. GP option -> CHAS note. Cafes -> OpenStreetMap note.
    "mock_results.json": (["CHANGI", "TAMPINES", "PASIR RIS", "TENGAH"], "gp",
                          {"CHANGI": 38.0, "TAMPINES": 44.5, "PASIR RIS": 51.2, "TENGAH": 66.8}),
    # All six factors scored, so the housing-window note appears.
    "mock_results_all_scored.json": (["PUNGGOL", "TAMPINES", "BEDOK", "PASIR RIS"], "polyclinic",
                                     {"PUNGGOL": 54.7, "TAMPINES": 43.9, "BEDOK": 39.6,
                                      "PASIR RIS": 51.2}),
}


class FixedEventRouter:
    """An EventRouter stand-in: fixed minutes per event title (None = unroutable, or
    ("walk", minutes) for a walking fallback), with the recorded OneMap route for the
    mode supplying summary and geometry. Counts calls."""

    def __init__(self, minutes, default=30.0):
        self._minutes, self._default = minutes, default
        self.calls = 0
        from gowhere.lepak.routing import parse_route
        routes = json.loads((FIXTURE_DIR / "lepak" / "onemap_routes.json").read_text())
        self._routes = {m: parse_route(routes[m], m) for m in ("pt", "drive", "walk")}

    def route_many(self, origin, events, mode, now):
        self.calls += 1
        out = {}
        for e in events:
            m = self._minutes.get(e["title"], self._default)
            used = mode
            if isinstance(m, tuple):
                used, m = m
            out[e["id"]] = None if m is None else {**self._routes[used], "minutes": m}
        return out


LEPAK_NOW = datetime(2026, 9, 30, 12, 0)     # the ingestion fixtures' "now" (a Wednesday)
LEPAK_ORIGIN = (1.3521, 103.8198)            # an arbitrary central point, not a user's
LEPAK_MINUTES = {"Anime Earth": 22.4, "Free Yukata Experience": 22.4,
                 "Seoul Anthem K-pop Party": 18.9, "Halloween Horror Nights 14: Fear Unlocked": 41.0,
                 "JisuLife Global Brand Experience Store": ("walk", 9.0),
                 "BellyGom Summer Day Out Party": None}


def lepak_events():
    """The ingestion fixtures, stored as of LEPAK_NOW (13 events)."""
    from gowhere.etl.reference import load_venue_aliases
    from gowhere.ingest.run import FilePostSource, Ingestor
    from gowhere.lepak.store import EventStore
    from gowhere.services.location import LocationService
    from tests.fakes import RecordedLlm, RecordedSearch
    fx = FIXTURE_DIR / "lepak"
    load = lambda n: json.loads((fx / n).read_text(encoding="utf-8"))
    store = EventStore(":memory:")
    Ingestor(store, RecordedLlm(load("extractions.json")),
             LocationService(RecordedSearch(load("onemap_search.json")),
                             aliases=load_venue_aliases())).run(
        FilePostSource(fx / "posts.json"), config.LEPAK_CHANNELS, now=LEPAK_NOW)
    return store


def build_lepak():
    from gowhere.lepak.parking import ParkingService
    from gowhere.lepak.search import search
    from gowhere.web import lepak_views

    class NoDataMall:
        def carpark_availability(self):
            from gowhere.adapters.http import HttpError
            raise HttpError("LTA_DATAMALL_KEY is not set")

    events = lepak_events().events(LEPAK_NOW)
    cats = ["Arts & Culture", "Music & Performances", "Family & Kids", "Sales & Pop-ups"]
    pt = search(events, LEPAK_ORIGIN, cats, "month", "pt", 45,
                FixedEventRouter(LEPAK_MINUTES), LEPAK_NOW)
    saved = {"request": {"categories": cats, "date_option": "month", "mode": "pt",
                         "max_minutes": 45}, "search": pt}
    drive = search(events, LEPAK_ORIGIN, cats, "month", "drive", 45,
                   FixedEventRouter(LEPAK_MINUTES), LEPAK_NOW, parking=ParkingService(NoDataMall()))
    anime = next(r for r in drive["results"] if r["title"] == "Anime Earth")
    from flask import Flask
    app = Flask(__name__)
    from gowhere.web.routes import bp
    app.register_blueprint(bp)
    with app.test_request_context():
        return {"mock_lepak_results.json": lepak_views.results_view(saved, "travel", None, 1, LEPAK_NOW),
                "mock_lepak_event.json": lepak_views.event_view(anime, "drive", LEPAK_NOW)}


def build(snapshot=None):
    snapshot = snapshot or Snapshot()
    out = {}
    for name, (areas, facility, minutes) in SCENARIOS.items():
        engine = ScoringEngine(default_strategies(FixedRouter(minutes)), snapshot)
        out[name] = results_view(engine.compare(areas, _choices(facility)), snapshot)
    return out


def main():
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    for name, view in {**build(), **build_lepak()}.items():
        (FIXTURE_DIR / name).write_text(json.dumps(view, indent=1, ensure_ascii=False) + "\n")
        print(f"wrote tests/fixtures/{name}")


if __name__ == "__main__":
    main()
