"""Commute: scoring scale, representative block, session caching, failure handling and
the privacy guarantee that a destination postal code never reaches logs or errors."""
import logging
import threading
from datetime import datetime

import pytest
import requests

from gowhere.adapters.http import HttpError
from gowhere.adapters.onemap import OneMapAdapter
from gowhere.etl.build_snapshot import compute, write_snapshot
from gowhere.scoring.commute import (SGT, CommuteRouter, CommuteScorer, commute_score,
                                     next_weekday_departure)
from gowhere.scoring.engine import FactorChoice, InvalidRequest, ScoringEngine
from gowhere.snapshot import Snapshot
from tests.fakes import FakeSources
from tests.test_geo_spatial import AREAS

POSTAL = "048583"   # destination used throughout; must never appear in logs or errors


@pytest.mark.parametrize("minutes, score", [
    (0, 10.0), (20, 10.0), (20.6, 9.9), (50, 5.0), (79.4, 0.1), (80, 0.0), (130, 0.0)])
def test_absolute_scale(minutes, score):
    assert commute_score(minutes) == pytest.approx(score)


def test_departure_is_next_weekday_0830_sgt():
    fri_evening = datetime(2026, 10, 2, 18, 0, tzinfo=SGT)
    assert next_weekday_departure(fri_evening) == datetime(2026, 10, 5, 8, 30, tzinfo=SGT)  # Monday
    tue_early = datetime(2026, 9, 29, 7, 0, tzinfo=SGT)
    assert next_weekday_departure(tue_early) == datetime(2026, 9, 29, 8, 30, tzinfo=SGT)


def test_representative_block_is_nearest_flat_weighted_centroid():
    blocks = [
        # centroid weighted 3:1 towards the east pair -> block 2 is nearest
        {"id": 1, "blk_no": "1", "street": "S", "lat": 1.30, "lon": 103.70,
         "planning_area": "A", "total_dwelling_units": 100},
        {"id": 2, "blk_no": "2", "street": "S", "lat": 1.30, "lon": 103.74,
         "planning_area": "A", "total_dwelling_units": 150},
        {"id": 3, "blk_no": "3", "street": "S", "lat": 1.30, "lon": 103.76,
         "planning_area": "A", "total_dwelling_units": 150},
    ]
    row = CommuteScorer(router=object()).precompute(blocks, None)["commute_origin"][0]
    assert row["block_id"] == 2   # centroid at lon 103.74 exactly


class FakeOneMap:
    """Counts calls; a route takes 600 s plus 120 s per 0.01 deg of latitude difference."""

    def __init__(self, known=(POSTAL,), fail_for=(), search_fails=False):
        self.known, self.fail_for, self.search_fails = set(known), set(fail_for), search_fails
        self.searches, self.routes, self.lock = 0, [], threading.Lock()

    def search(self, query, redact=False):
        self.searches += 1
        if self.search_fails:
            raise HttpError("ConnectionError")
        return {"results": [{"POSTAL": query, "LATITUDE": "1.28", "LONGITUDE": "103.85"}]
                if query in self.known else []}

    def transit_route(self, start, end, departure, redact=False, retries=4):
        assert redact
        with self.lock:
            self.routes.append(("pt", start))
        if start in self.fail_for:
            raise HttpError("HTTP 400", status=400)
        return {"plan": {"itineraries": [{"duration": abs(start[0] - end[0]) * 12000 + 600},
                                         {"duration": abs(start[0] - end[0]) * 12000 + 900}]}}

    def drive_route(self, start, end, redact=False, retries=4):
        assert redact
        with self.lock:
            self.routes.append(("drive", start))
        return {"route_summary": {"total_time": 900}}


@pytest.fixture
def snapshot(tmp_path):
    blocks = [{"blk_no": "1", "street": "WEST ST", "total_dwelling_units": 100},
              {"blk_no": "2", "street": "EAST ST", "total_dwelling_units": 100}]
    geocodes = [{"blk_no": "1", "street": "WEST ST", "status": "ok", "lat": 1.35, "lon": 103.75, "detail": ""},
                {"blk_no": "2", "street": "EAST ST", "status": "ok", "lat": 1.38, "lon": 103.85, "detail": ""}]
    strategy = CommuteScorer(router=object())
    out = compute(blocks, geocodes, AREAS, FakeSources(), [strategy])
    path = tmp_path / "s.db"
    write_snapshot(path, out, AREAS, [strategy], {"generated_at": "x"})
    return Snapshot(path)


def engine_for(snapshot, fake):
    router = CommuteRouter(adapter=fake, departure=datetime(2026, 10, 6, 8, 30, tzinfo=SGT))
    return ScoringEngine([CommuteScorer(router)], snapshot)


def choice(weight=5, postal=POSTAL, mode="pt"):
    return {"commute": FactorChoice(weight, {"destination_postal": postal, "mode": mode})}


def test_scores_minutes_and_summary(snapshot):
    r = engine_for(snapshot, FakeOneMap()).compare(["WEST", "EAST"], choice())
    by = {a["name"]: a for a in r["areas"]}
    # fastest itinerary: WEST 0.07 deg -> 840 + 600 s = 24 min -> 10 x 56/60
    #                    EAST 0.10 deg -> 1200 + 600 s = 30 min -> 10 x 50/60
    assert by["WEST"]["category"]["commute"] == pytest.approx(10 * 56 / 60)
    assert by["EAST"]["category"]["commute"] == pytest.approx(10 * 50 / 60)
    assert by["EAST"]["raw"]["commute"]["summary"] == "30 min by public transport from Blk 2 East Street"
    assert "8:30 am on a weekday" in r["factors"][0]["notes"][0]


def test_at_most_one_route_per_area_and_slider_changes_never_reroute(snapshot):
    fake = FakeOneMap()
    e = engine_for(snapshot, fake)
    e.compare(["WEST", "EAST"], choice(weight=5))
    assert (fake.searches, len(fake.routes)) == (1, 2)
    e.compare(["WEST", "EAST"], choice(weight=9))      # weight change
    assert (fake.searches, len(fake.routes)) == (1, 2)
    e.compare(["WEST", "EAST"], choice(mode="drive"))  # new mode: new routes
    assert len(fake.routes) == 4


def test_routing_failure_for_one_area_drops_commute_for_all(snapshot):
    from gowhere.scoring.engine import NoFactorsLeft
    fake = FakeOneMap(fail_for={(1.35, 103.75)})
    with pytest.raises(NoFactorsLeft) as err:
        engine_for(snapshot, fake).compare(["WEST", "EAST"], choice())
    assert err.value.dropped[0]["missing_for"] == ["WEST"]


def test_onemap_unreachable_makes_commute_unavailable_not_an_error(snapshot):
    from gowhere.scoring.engine import NoFactorsLeft
    with pytest.raises(NoFactorsLeft):
        engine_for(snapshot, FakeOneMap(search_fails=True)).compare(["WEST", "EAST"], choice())


def test_unknown_postal_code_is_a_user_error(snapshot):
    with pytest.raises(InvalidRequest, match="postal code was not found"):
        engine_for(snapshot, FakeOneMap(known=())).compare(["WEST", "EAST"], choice())


@pytest.mark.parametrize("postal", ["04858", "0485830", "04858A", ""])
def test_postal_code_must_be_six_digits_and_error_does_not_echo_it(snapshot, postal):
    with pytest.raises(InvalidRequest) as err:
        engine_for(snapshot, FakeOneMap()).compare(["WEST", "EAST"], choice(postal=postal))
    assert "6-digit" in str(err.value)
    assert postal == "" or postal not in str(err.value)


# ---- Security NFR: the destination never reaches logs or exception text ----

class LeakySession:
    """Fails like requests does: the exception text contains the full URL and query."""

    def get(self, url, params=None, headers=None, timeout=None):
        query = "&".join(f"{k}={v}" for k, v in (params or {}).items())
        raise requests.ConnectionError(f"Max retries exceeded with url: {url}?{query}")


def test_redacted_requests_keep_destination_out_of_logs_and_errors(caplog):
    caplog.set_level(logging.DEBUG)
    adapter = OneMapAdapter(session=LeakySession(), token="t", min_interval_s=0, sleep=lambda s: None)
    with pytest.raises(HttpError) as err:
        adapter.search(POSTAL, redact=True)
    with pytest.raises(HttpError) as err2:
        adapter.drive_route((1.35, 103.75), (1.2844, 103.8511), redact=True)
    for text in (caplog.text, str(err.value), str(err2.value)):
        assert POSTAL not in text and "103.8511" not in text
    assert "ConnectionError" in str(err.value)


def test_unredacted_errors_still_carry_detail_for_etl_debugging():
    adapter = OneMapAdapter(session=LeakySession(), token="t", min_interval_s=0, sleep=lambda s: None)
    with pytest.raises(HttpError) as err:
        adapter.search("1 BEACH RD")
    assert "1 BEACH RD" in str(err.value)


def test_urllib3_request_logging_never_at_debug():
    assert logging.getLogger("urllib3").getEffectiveLevel() >= logging.INFO


def test_router_keeps_destination_in_memory_only(tmp_path, monkeypatch, snapshot):
    monkeypatch.chdir(tmp_path)
    before = set(tmp_path.rglob("*"))
    engine_for(snapshot, FakeOneMap()).compare(["WEST", "EAST"], choice())
    assert set(tmp_path.rglob("*")) == before   # nothing written
