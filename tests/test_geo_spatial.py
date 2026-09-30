import pytest

from gowhere.etl.build_snapshot import compute
from gowhere.etl.geo import PlanningAreaIndex, haversine_m, nearest, walk_minutes


def square(x0, y0, x1, y1):
    return [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]


AREAS = [
    {"name": "WEST", "region": "W", "geometry": {"type": "Polygon",
                                                 "coordinates": square(103.70, 1.30, 103.80, 1.40)}},
    {"name": "EAST", "region": "E", "geometry": {"type": "MultiPolygon", "coordinates": [
        square(103.80, 1.30, 103.90, 1.40), square(104.00, 1.30, 104.05, 1.35)]}},
    {"name": "EMPTY", "region": "E", "geometry": {"type": "Polygon",
                                                  "coordinates": square(103.60, 1.20, 103.65, 1.25)}},
]


def test_haversine_one_degree_latitude():
    assert haversine_m(1.0, 103.8, 2.0, 103.8) == pytest.approx(111_195, rel=1e-4)


def test_walk_minutes_model():
    assert walk_minutes(800) == pytest.approx(800 * 1.3 / 80)
    assert walk_minutes(800, detour=1.0) == 10.0


def test_nearest_picks_closest():
    pts = [{"id": 1, "lat": 1.30, "lon": 103.80}, {"id": 2, "lat": 1.31, "lon": 103.80}]
    p, d = nearest(1.309, 103.80, pts)
    assert p["id"] == 2 and d == pytest.approx(haversine_m(1.309, 103.80, 1.31, 103.80))


def test_point_in_polygon_including_multipolygon_part():
    idx = PlanningAreaIndex(AREAS)
    assert idx.area_of(1.35, 103.75) == "WEST"
    assert idx.area_of(1.35, 103.85) == "EAST"
    assert idx.area_of(1.32, 104.02) == "EAST"     # second polygon of the MultiPolygon
    assert idx.area_of(1.50, 103.75) is None       # sea / outside


def test_compute_places_blocks_and_logs_unplaced():
    blocks = [{"blk_no": "1", "street": "A", "total_dwelling_units": 100},
              {"blk_no": "2", "street": "B", "total_dwelling_units": 300},
              {"blk_no": "3", "street": "C", "total_dwelling_units": 50},
              {"blk_no": "4", "street": "D", "total_dwelling_units": 50}]
    geocodes = [
        {"blk_no": "1", "street": "A", "status": "ok", "lat": 1.35, "lon": 103.75, "detail": ""},
        {"blk_no": "2", "street": "B", "status": "ok", "lat": 1.35, "lon": 103.85, "detail": ""},
        {"blk_no": "3", "street": "C", "status": "no_match", "detail": "x"},
        {"blk_no": "4", "street": "D", "status": "ok", "lat": 1.50, "lon": 103.75, "detail": ""},
    ]
    exits = [{"station": "S1", "exit_code": "A", "lat": 1.355, "lon": 103.75}]
    out = compute(blocks, geocodes, AREAS, exits)

    assert {b["blk_no"]: b["planning_area"] for b in out["placed"]} == {"1": "WEST", "2": "EAST"}
    assert {b["blk_no"]: b["reason"] for b in out["unplaced"]} == {
        "3": "geocode no_match", "4": "outside every planning area"}
    b1 = next(b for b in out["placed"] if b["blk_no"] == "1")
    assert b1["walk_min"] == pytest.approx(haversine_m(1.35, 103.75, 1.355, 103.75) * 1.3 / 80)
    # EMPTY has no HDB blocks, so it is out of scope and gets no score
    assert set(out["scores"]) == {"WEST", "EAST"}
    assert out["metrics"]["EAST"]["n_flats"] == 300


def test_snapshot_flags_small_areas_but_keeps_them_in_scope(tmp_path):
    import sqlite3

    from gowhere.etl.build_snapshot import is_small_sample, write_snapshot

    blocks = [{"blk_no": str(i), "street": "W", "total_dwelling_units": 100} for i in range(12)]
    blocks.append({"blk_no": "1", "street": "E", "total_dwelling_units": 55})
    geocodes = ([{"blk_no": str(i), "street": "W", "status": "ok", "lat": 1.35, "lon": 103.75,
                  "detail": ""} for i in range(12)]
                + [{"blk_no": "1", "street": "E", "status": "ok", "lat": 1.35, "lon": 103.85,
                    "detail": ""}])
    exits = [{"station": "S", "exit_code": "A", "lat": 1.355, "lon": 103.75}]
    out = compute(blocks, geocodes, AREAS, exits)
    path = tmp_path / "s.db"
    write_snapshot(path, out, AREAS, exits, {"small_area_blocks": "10"})

    rows = {r[0]: r[1:] for r in sqlite3.connect(path).execute(
        "SELECT name, in_scope, n_blocks, n_flats, small_sample FROM planning_area")}
    assert rows == {"WEST": (1, 12, 1200, 0), "EAST": (1, 1, 55, 1), "EMPTY": (0, 0, 0, 0)}
    assert (is_small_sample(9), is_small_sample(10), is_small_sample(0)) == (True, False, False)
