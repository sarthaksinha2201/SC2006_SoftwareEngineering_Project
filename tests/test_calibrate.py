import pytest

from gowhere.adapters.http import HttpError
from gowhere.etl.calibrate import RouteCache, fetch_routes, summarise


class FakeRouter:
    def __init__(self, distances):
        self.distances, self.calls = distances, 0

    def walking_route(self, start, end):
        self.calls += 1
        d = self.distances[start]
        if d is None:
            raise HttpError("HTTP 500", status=500)
        return {"route_summary": {"total_distance": d, "total_time": d / 1.2}}


def block(lat, straight_m):
    return {"lat": lat, "lon": 103.8, "exit_lat": 1.0, "exit_lon": 103.9,
            "exit_distance_m": straight_m}


def test_fetch_is_cached_and_failures_kept(tmp_path):
    sample = [block(1.1, 500), block(1.2, 700), block(1.3, 900)]
    router = FakeRouter({(1.1, 103.8): 650, (1.2, 103.8): 1050, (1.3, 103.8): None})
    cache = RouteCache(tmp_path / "r.sqlite")
    fetch_routes(sample, router, cache)
    assert [b["route_status"] for b in sample] == ["ok", "ok", "error"]

    again = [block(1.1, 500), block(1.2, 700)]
    router2 = FakeRouter({})
    fetch_routes(again, router2, cache)
    assert router2.calls == 0 and again[1]["route_distance_m"] == 1050


def test_summary_ratio_and_threshold_agreement():
    # ratios 1.3, 1.5, 1.7 -> median 1.5
    sample = [dict(block(1.1, 500), route_status="ok", route_distance_m=650),
              dict(block(1.2, 600), route_status="ok", route_distance_m=900),
              dict(block(1.3, 500), route_status="ok", route_distance_m=850),
              dict(block(1.4, 500), route_status="error")]
    s = summarise(sample, current_factor=1.3, speed=80, threshold=10)
    assert s["median"] == pytest.approx(1.5) and s["calibrated_factor"] == 1.5
    assert (s["n_ok"], s["n_failed"]) == (3, 1)
    # route minutes 8.1, 11.25, 10.6 -> within: T, F, F
    # model @1.3 minutes: 8.1, 9.75, 8.1 -> T, T, T  -> agrees 1/3
    # model @1.5 minutes: 9.4, 11.25, 9.4 -> T, F, T  -> agrees 2/3
    assert s["agreement_current"] == pytest.approx(1 / 3)
    assert s["agreement_calibrated"] == pytest.approx(2 / 3)
