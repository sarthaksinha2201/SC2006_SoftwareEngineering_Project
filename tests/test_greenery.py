import pytest

from gowhere.etl.geo import LocalProjection, NearestIndex, haversine_m
from gowhere.scoring.greenery import GreeneryScorer
from tests.fakes import FakeSources


def square(lon0, lat0, size):
    return {"type": "Polygon", "coordinates": [[[lon0, lat0], [lon0 + size, lat0],
            [lon0 + size, lat0 + size], [lon0, lat0 + size], [lon0, lat0]]]}


def test_projection_matches_haversine_within_0_1_percent():
    proj = LocalProjection()
    for (a, b) in [((1.30, 103.70), (1.44, 103.98)), ((1.27, 103.85), (1.28, 103.86))]:
        (x1, y1), (x2, y2) = proj.xy(*a), proj.xy(*b)
        planar = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
        assert planar == pytest.approx(haversine_m(*a, *b), rel=1e-3)


def test_distance_is_to_the_park_edge_and_zero_inside():
    # a ~1.1 km square park; a block 0.001 deg (~111 m) west of its edge
    idx = NearestIndex([{"name": "BIG PARK", "geometry": square(103.80, 1.30, 0.01)}])
    name, d = idx.nearest(1.305, 103.799)
    assert name == "BIG PARK" and d == pytest.approx(111.2, rel=0.01)
    assert idx.nearest(1.305, 103.805)[1] == 0.0          # inside the park
    # the park's centre is ~667 m away, so a centroid would have said "not within 400 m"
    assert haversine_m(1.305, 103.799, 1.305, 103.805) > 600


def test_distance_to_connector_line():
    idx = NearestIndex([{"name": "PCN", "geometry": {
        "type": "LineString", "coordinates": [[103.80, 1.30], [103.80, 1.32]]}}])
    assert idx.nearest(1.31, 103.803)[1] == pytest.approx(333.6, rel=0.01)


def test_greenery_scores_share_within_400m():
    park = {"name": "P", "geometry": square(103.80, 1.30, 0.002)}
    pcn = {"name": "L", "geometry": {"type": "LineString",
                                     "coordinates": [[103.90, 1.30], [103.90, 1.31]]}}
    # AREA A: one block inside the park (100 flats), one 1 km away (100 flats) -> 50%
    # AREA B: one block 0.003 deg (~334 m) from the connector (300 flats)        -> 100%
    # AREA C: one block far from everything                                        -> 0%
    blocks = [
        {"id": 1, "lat": 1.301, "lon": 103.801, "planning_area": "A", "total_dwelling_units": 100},
        {"id": 2, "lat": 1.301, "lon": 103.811, "planning_area": "A", "total_dwelling_units": 100},
        {"id": 3, "lat": 1.305, "lon": 103.903, "planning_area": "B", "total_dwelling_units": 300},
        {"id": 4, "lat": 1.400, "lon": 103.700, "planning_area": "C", "total_dwelling_units": 50},
    ]
    out = GreeneryScorer().precompute(blocks, FakeSources(parks=[park], connectors=[pcn]))
    areas = {r["planning_area"]: r for r in out["greenery_area"]}
    assert {a: r["pct_within_radius"] for a, r in areas.items()} == {"A": 50.0, "B": 100.0, "C": 0.0}
    assert {a: r["score"] for a, r in areas.items()} == {"A": 5.0, "B": 10.0, "C": 0.0}
    b3 = next(r for r in out["greenery_block"] if r["block_id"] == 3)
    assert b3["green_space_type"] == "park connector" and b3["distance_m"] < 400
    assert out["greenery_block"][0]["distance_m"] == 0.0
