"""End-to-end tests: a real browser (Playwright, Chromium) drives the real app over HTTP.

The app runs in this process on a threaded Werkzeug server, with the real
snapshot (data/snapshot.db), the real place list (data/eat.db) and the Where to Lepak
ingestion fixtures as of 30 Sep 2026 12:00. Only the External Services are stood in for,
exactly as in the other tests: OneMap (postal lookup and routing), LTA DataMall and
Google Places. So these tests need no keys and no network, give the same answer every
run, and never spend the Google daily cap, even with a real key in .env.

The browser is kept off the internet too (`no_internet`): map tiles and anything else
outside the app are refused, so a test can only pass on what the app itself serves.

Not collected where pytest-playwright is not installed, so the unit test job is unchanged. To run:

    pip install pytest-playwright && python -m playwright install chromium
    python -m pytest tests/e2e              # add --headed to watch
"""
import re
import sqlite3
import threading

import importlib.util

import pytest
from werkzeug.serving import make_server

from gowhere.adapters.http import HttpError
from gowhere.lepak.parking import ParkingService
from gowhere.web import create_app
from gowhere.web.mock import (LEPAK_MINUTES, LEPAK_NOW, LEPAK_ORIGIN, FixedEventRouter,
                              FixedRouter, lepak_events)

if importlib.util.find_spec("pytest_playwright") is None:
    collect_ignore_glob = ["test_*.py"]

POSTAL = "048583"


class FakeLocations:
    """OneMap postal lookup: the one postal code the tests type, nothing else."""

    def postal(self, postal):
        return {POSTAL: LEPAK_ORIGIN}.get(postal)


class NoDataMall:
    def carpark_availability(self):
        raise HttpError("LTA_DATAMALL_KEY is not set")


@pytest.fixture(scope="session")
def app(tmp_path_factory):
    events = tmp_path_factory.mktemp("e2e") / "events.db"
    target = sqlite3.connect(events)
    lepak_events().db.backup(target)
    target.close()
    return create_app({
        "SECRET_KEY": "e2e",
        "EVENTS_PATH": events,
        "NOW": lambda: LEPAK_NOW,
        "ROUTER_FACTORY": lambda: FixedRouter({}),
        "LOCATION_FACTORY": FakeLocations,
        "EVENT_ROUTER_FACTORY": lambda: FixedEventRouter(LEPAK_MINUTES),
        "PARKING_FACTORY": lambda: ParkingService(NoDataMall()),
        "RATINGS_FACTORY": lambda: None,          # no Google calls
    })


@pytest.fixture(scope="session")
def base_url(app):
    """Overrides pytest-base-url's fixture, so tests can write page.goto("/live")."""
    server = make_server("127.0.0.1", 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


@pytest.fixture(autouse=True)
def no_internet(context, base_url):
    context.route(re.compile(r"^(?!" + re.escape(base_url) + r")"), lambda route: route.abort())
