"""Golden test: Amenities for a fixed mini-dataset, calculated by hand
(docs/golden-amenities.md). Each type is capped at 3 per block; the area value is the
flat-weighted median of the capped sum; the score is the percentile rank."""
import pytest

from gowhere.etl.geo import CountIndex
from gowhere.scoring.amenities import AmenitiesScorer, all_combinations, combination_key
from gowhere.scoring.base import SubsetOf
from tests.fakes import FakeAmenitySources

# Blocks ~5.5 km apart, so an amenity placed on a block counts for that block only.
LOCS = {"a1": (1.30, 103.70), "a2": (1.35, 103.70), "b1": (1.30, 103.80),
        "b2": (1.35, 103.80), "c1": (1.30, 103.90)}
BLOCKS = [
    {"id": 1, "lat": 1.30, "lon": 103.70, "planning_area": "A", "total_dwelling_units": 100},
    {"id": 2, "lat": 1.35, "lon": 103.70, "planning_area": "A", "total_dwelling_units": 100},
    {"id": 3, "lat": 1.30, "lon": 103.80, "planning_area": "B", "total_dwelling_units": 300},
    {"id": 4, "lat": 1.35, "lon": 103.80, "planning_area": "B", "total_dwelling_units": 100},
    {"id": 5, "lat": 1.30, "lon": 103.90, "planning_area": "C", "total_dwelling_units": 100},
]


def at(block, n, kind):
    lat, lon = LOCS[block]
    return [{"name": f"{kind} {block} {i}", "lat": lat, "lon": lon} for i in range(n)]


AMENITIES = {
    "supermarket": at("a1", 1, "s") + at("b1", 2, "s"),
    "cafe": at("a1", 5, "c") + at("a2", 2, "c") + at("b1", 1, "c") + at("c1", 20, "c"),
    "hawker_centre": [], "library": [], "mall": [], "gym": [],
}

# combination -> area -> (median capped count, score)
EXPECTED = {
    "supermarket,cafe": {"A": (2, 0.0), "B": (3, 7.5), "C": (3, 7.5)},   # B, C tie: rank 2.5
    "cafe": {"A": (2, 5.0), "B": (1, 0.0), "C": (3, 10.0)},             # C: 20 cafes -> 3
    "supermarket": {"A": (0, 2.5), "B": (2, 10.0), "C": (0, 2.5)},       # A, C tie: rank 1.5
}


@pytest.fixture(scope="module")
def area_rows():
    out = AmenitiesScorer().precompute(BLOCKS, FakeAmenitySources(AMENITIES))
    return {(r["amenity_types"], r["planning_area"]): r for r in out["amenity_area"]}


@pytest.mark.parametrize("combo", sorted(EXPECTED))
def test_golden_medians_and_scores(area_rows, combo):
    for area, (median, score) in EXPECTED[combo].items():
        row = area_rows[(combo, area)]
        assert row["median_capped_count"] == median, (combo, area)
        assert row["score"] == pytest.approx(score), (combo, area)


def test_every_combination_precomputed(area_rows):
    assert len(all_combinations()) == 63
    assert len(area_rows) == 63 * 3


def test_block_counts_stored_uncapped():
    out = AmenitiesScorer().precompute(BLOCKS, FakeAmenitySources(AMENITIES))
    c1 = next(r for r in out["amenity_block"] if r["block_id"] == 5 and r["amenity_type"] == "cafe")
    assert c1["count_within"] == 20


def test_radius_is_inclusive_at_800m():
    # 0.0072 deg of latitude is ~800.6 m; 0.00719 deg is ~799.5 m
    idx = CountIndex([{"lat": 1.30719, "lon": 103.8}, {"lat": 1.3072, "lon": 103.8}])
    assert idx.count_within(1.30, 103.8, 800) == 1
    assert idx.count_within(1.30, 103.8, 801) == 2


def test_selection_order_does_not_matter():
    assert combination_key(["cafe", "supermarket"]) == combination_key(["supermarket", "cafe"]) \
        == "supermarket,cafe"


@pytest.mark.parametrize("value, ok", [
    (["cafe"], True), (["cafe", "gym"], True), ([], False), (["cafe", "cafe"], False),
    (["bar"], False), ("cafe", False)])
def test_subset_option(value, ok):
    assert (value in SubsetOf(("supermarket", "cafe", "gym"))) is ok
