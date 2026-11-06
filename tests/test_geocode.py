"""Geocoding with a fake OneMap adapter: resumability, fallback query, failure logging."""
import csv
import io

from gowhere.adapters.http import HttpError
from gowhere.etl import geocode
from gowhere.etl.geocode import (SearchCache, geocode_all, geocode_postal, geocode_postal_codes,
                                 load_geocodes, load_postal_geocodes, write_failure_log)


def hit(blk, road, lat=1.35, lon=103.85):
    return {"found": 1, "results": [{"BLK_NO": blk, "ROAD_NAME": road, "LATITUDE": str(lat),
                                     "LONGITUDE": str(lon), "POSTAL": "123456", "ADDRESS": road}]}


class FakeOneMap:
    def __init__(self, answers, fail=()):
        self.answers, self.fail, self.calls = answers, set(fail), []

    def search(self, query):
        self.calls.append(query)
        if query in self.fail:
            raise HttpError("HTTP 503", status=503)
        return self.answers.get(query, {"found": 0, "results": []})


BLOCKS = [{"blk_no": "1", "street": "BEACH RD"},
          {"blk_no": "2", "street": "C'WEALTH CL"},
          {"blk_no": "3", "street": "NOWHERE ST"}]


def run(tmp_path, adapter):
    return geocode_all(BLOCKS, adapter, SearchCache(tmp_path / "c.sqlite"),
                       progress_every=0, out=io.StringIO())


def test_second_run_makes_no_requests(tmp_path):
    answers = {"1 BEACH RD": hit("1", "BEACH ROAD"),
               "2 COMMONWEALTH CLOSE": hit("2", "COMMONWEALTH CLOSE")}
    first = FakeOneMap(answers)
    results, stats = run(tmp_path, first)
    assert [r["status"] for r in results] == ["ok", "ok", "no_match"]
    assert stats["requests"] == len(first.calls) > 0

    second = FakeOneMap(answers)
    results2, stats2 = run(tmp_path, second)
    assert second.calls == [] and stats2["requests"] == 0
    assert [r["status"] for r in results2] == ["ok", "ok", "no_match"]


def test_falls_back_to_expanded_query(tmp_path):
    adapter = FakeOneMap({"2 COMMONWEALTH CLOSE": hit("2", "COMMONWEALTH CLOSE")})
    results, _ = run(tmp_path, adapter)
    assert results[1]["status"] == "ok"
    assert adapter.calls[2:4] == ["2 C'WEALTH CL", "2 COMMONWEALTH CLOSE"]


def test_errors_are_not_cached_and_are_retried_next_run(tmp_path):
    results, _ = run(tmp_path, FakeOneMap({"1 BEACH RD": hit("1", "BEACH ROAD")},
                                          fail={"1 BEACH RD"}))
    assert results[0]["status"] == "error" and "503" in results[0]["detail"]

    retry = FakeOneMap({"1 BEACH RD": hit("1", "BEACH ROAD")})
    results, _ = run(tmp_path, retry)
    assert "1 BEACH RD" in retry.calls and results[0]["status"] == "ok"


def test_every_failure_is_logged(tmp_path):
    results, _ = run(tmp_path, FakeOneMap({}, fail={"2 C'WEALTH CL"}))
    log = tmp_path / "failures.csv"
    failures = write_failure_log(results, log)
    rows = list(csv.DictReader(open(log)))
    assert len(rows) == len(failures) == 3
    assert {r["status"] for r in rows} == {"no_match", "error"}


# ---- postal codes: polyclinics and supermarkets are located by postal code -----------

def test_a_postal_code_is_searched_once_and_then_read_from_the_cache(tmp_path):
    cache, adapter = SearchCache(tmp_path / "c.sqlite"), FakeOneMap({"123456": hit("1", "BEACH ROAD")})
    assert geocode_postal("123456", adapter, cache) == {"lat": 1.35, "lon": 103.85}
    assert geocode_postal("123456", adapter, cache) == {"lat": 1.35, "lon": 103.85}
    assert adapter.calls == ["123456"]


def test_a_result_for_a_different_postal_code_is_not_accepted(tmp_path):
    adapter = FakeOneMap({"654321": hit("1", "BEACH ROAD")})          # its POSTAL is 123456
    assert geocode_postal("654321", adapter, SearchCache(tmp_path / "c.sqlite")) is None


def places(monkeypatch, *rows):
    monkeypatch.setattr(geocode, "postal_code_places", lambda: list(rows))


def test_two_places_in_one_building_cost_one_search(tmp_path, monkeypatch):
    places(monkeypatch, ("Clinic", "123456"), ("Supermarket", "123456"))
    adapter = FakeOneMap({"123456": hit("1", "BEACH ROAD")})
    assert geocode_postal_codes(adapter, SearchCache(tmp_path / "c.sqlite")) == []
    assert adapter.calls == ["123456"]


def test_every_postal_failure_is_named_and_the_rest_still_run(tmp_path, monkeypatch):
    places(monkeypatch, ("Lost Clinic", "000001"), ("Down Clinic", "000002"), ("Good Clinic", "123456"))
    adapter = FakeOneMap({"123456": hit("1", "BEACH ROAD")}, fail={"000002"})
    failures = geocode_postal_codes(adapter, SearchCache(tmp_path / "c.sqlite"))
    assert failures == ["Lost Clinic (000001): no OneMap match", "Down Clinic (000002): HTTP 503"]
    assert adapter.calls == ["000001", "000002", "123456"]


def test_a_failed_postal_search_is_retried_next_run(tmp_path, monkeypatch):
    places(monkeypatch, ("Clinic", "123456"))
    cache = SearchCache(tmp_path / "c.sqlite")
    geocode_postal_codes(FakeOneMap({}, fail={"123456"}), cache)
    retry = FakeOneMap({"123456": hit("1", "BEACH ROAD")})
    assert geocode_postal_codes(retry, cache) == [] and retry.calls == ["123456"]


# ---- offline: the snapshot build reads only the cache --------------------------------

def test_offline_blocks_resolve_from_the_cache_and_the_rest_are_marked_uncached(tmp_path):
    path = tmp_path / "c.sqlite"
    SearchCache(path).put("1 BEACH RD", hit("1", "BEACH ROAD"))
    results = load_geocodes(path, blocks=BLOCKS[:2])
    assert [r["status"] for r in results] == ["ok", "uncached"]


def test_offline_postal_codes_separate_found_from_never_searched(tmp_path):
    path = tmp_path / "c.sqlite"
    cache = SearchCache(path)
    cache.put("123456", hit("1", "BEACH ROAD"))
    cache.put("654321", {"found": 0, "results": []})
    assert load_postal_geocodes(["123456", "654321", "000001"], path) == {
        "123456": {"lat": 1.35, "lon": 103.85}, "654321": None, "000001": None}


def test_the_cache_keeps_one_answer_per_query(tmp_path):
    cache = SearchCache(tmp_path / "c.sqlite")
    cache.put("q", {"found": 0})
    cache.put("q", {"found": 1})
    assert cache.get("q") == {"found": 1} and len(cache) == 1 and cache.get("other") is None
