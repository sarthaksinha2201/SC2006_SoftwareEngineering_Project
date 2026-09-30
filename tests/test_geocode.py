"""Geocoding with a fake OneMap adapter: resumability, fallback query, failure logging."""
import csv
import io

from gowhere.adapters.http import HttpError
from gowhere.etl.geocode import SearchCache, geocode_all, write_failure_log


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
