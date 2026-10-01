"""Golden test: Housing Affordability for a fixed mini-dataset, calculated by hand.

The hand calculation is in docs/golden-housing.md. Request: 4-room, budget
$400,000-$600,000 inclusive, at least 70 years of lease left.
"""
import pytest

from gowhere.etl.build_snapshot import compute, write_snapshot
from gowhere.scoring.engine import FactorChoice, InvalidRequest, NoFactorsLeft, ScoringEngine
from gowhere.scoring.housing import HousingAffordabilityScorer
from gowhere.scoring.stats import round1
from gowhere.snapshot import Snapshot
from tests.fakes import FakeResaleSources
from tests.test_geo_spatial import AREAS

LEASE_70 = 70 * 12


def tx(blk, flat_type, price, lease_months=LEASE_70 + 60, month="2026-01"):
    return {"month": month, "flat_type": flat_type, "blk_no": blk, "street": "S",
            "resale_price": price, "remaining_lease_months": lease_months}


# Block "W" is in WEST, block "E" is in EAST.
TRANSACTIONS = (
    # WEST: 16 matching 4-room sales, 10 within budget (both boundary prices count)
    [tx("W", "4 ROOM", p) for p in (400_000, 600_000, 450_000, 480_000, 500_000,
                                     520_000, 540_000, 560_000, 580_000, 590_000)]
    + [tx("W", "4 ROOM", p) for p in (399_999, 600_001, 700_000, 700_000, 700_000, 700_000)]
    # WEST distractors: wrong flat type; lease one month short of 70 years
    + [tx("W", "3 ROOM", 450_000), tx("W", "4 ROOM", 450_000, lease_months=LEASE_70 - 1)]
    # EAST: exactly 10 matching (lease exactly 70 years counts), 7 within budget
    + [tx("E", "4 ROOM", 500_000, lease_months=LEASE_70) for _ in range(7)]
    + [tx("E", "4 ROOM", 650_000, lease_months=LEASE_70) for _ in range(3)]
    # a sale on a block not in the snapshot: counted as unmatched, not placed
    + [tx("X", "4 ROOM", 500_000)]
)

REQUEST = {"flat_type": "4 ROOM", "budget_min": 400_000, "budget_max": 600_000,
           "min_remaining_lease_years": 70}


@pytest.fixture
def snapshot(tmp_path):
    blocks = [{"blk_no": "W", "street": "S", "total_dwelling_units": 100},
              {"blk_no": "E", "street": "S", "total_dwelling_units": 100}]
    geocodes = [{"blk_no": "W", "street": "S", "status": "ok", "lat": 1.35, "lon": 103.75, "detail": ""},
                {"blk_no": "E", "street": "S", "status": "ok", "lat": 1.35, "lon": 103.85, "detail": ""}]
    sources = FakeResaleSources(["2025-09", "2026-08"], TRANSACTIONS)
    strategy = HousingAffordabilityScorer()
    out = compute(blocks, geocodes, AREAS, sources, [strategy])
    path = tmp_path / "s.db"
    write_snapshot(path, out, AREAS, [strategy], {"generated_at": "x", **strategy.meta(sources)})
    return Snapshot(path)


def test_golden_scores(snapshot):
    scores = HousingAffordabilityScorer().category_scores(snapshot, ["WEST", "EAST"], REQUEST)
    assert scores["WEST"] == pytest.approx(10 / 16 * 100 / 10)   # 6.25
    assert scores["EAST"] == pytest.approx(7 / 10 * 100 / 10)    # 7.0
    assert round1(scores["WEST"]) == 6.3                         # half up, not 6.2


def test_golden_raw_values_sentence(snapshot):
    raw = HousingAffordabilityScorer().raw_values(snapshot, ["WEST", "EAST"], REQUEST)
    assert raw["WEST"]["summary"] == ("62.5% of 4-room resales with at least 70 years of lease "
                                      "left in the last 12 months (10 of 16) were within your budget")
    assert (raw["EAST"]["matching resales"], raw["EAST"]["within budget"]) == (10, 7)


def test_without_lease_filter_the_short_lease_sale_counts(snapshot):
    scores = HousingAffordabilityScorer().category_scores(
        snapshot, ["WEST"], {**REQUEST, "min_remaining_lease_years": None})
    assert scores["WEST"] == pytest.approx(11 / 17 * 10)


def test_fewer_than_10_matching_is_no_data(snapshot):
    # EAST has exactly 10: scored. Raising the threshold to 11 makes it missing.
    assert HousingAffordabilityScorer(min_transactions=11).category_scores(
        snapshot, ["EAST"], REQUEST)["EAST"] is None
    # 5-room has no sales anywhere -> engine drops the only factor for all areas
    engine = ScoringEngine([HousingAffordabilityScorer()], snapshot)
    with pytest.raises(NoFactorsLeft):
        engine.compare(["WEST", "EAST"], {"housing_affordability": FactorChoice(
            5, {**REQUEST, "flat_type": "5 ROOM"})})


def test_budget_min_above_max_rejected(snapshot):
    engine = ScoringEngine([HousingAffordabilityScorer()], snapshot)
    with pytest.raises(InvalidRequest, match="budget minimum must not exceed"):
        engine.compare(["WEST", "EAST"], {"housing_affordability": FactorChoice(
            5, {**REQUEST, "budget_min": 700_000})})


def test_unmatched_sales_are_counted_and_window_recorded(snapshot):
    meta = snapshot.meta()
    assert (meta["housing_transactions"], meta["housing_unmatched_transactions"]) == ("28", "1")   # 18 WEST + 10 EAST; 1 unplaced
    assert (meta["housing_window_start"], meta["housing_window_end"]) == ("2025-09", "2026-08")


def test_factor_note_states_window_and_no_price_adjustment(snapshot):
    note = HousingAffordabilityScorer().factor_notes(snapshot, REQUEST)[0]
    assert note == ("Based on HDB resale transactions registered from Sep 2025 to Aug 2026. "
                    "Prices are as transacted, not adjusted for market movement over that period.")


def test_lease_parser():
    from gowhere.etl.raw import parse_remaining_lease
    assert parse_remaining_lease("61 years 04 months") == 736
    assert parse_remaining_lease("70 years") == 840
    assert parse_remaining_lease("1 year 01 month") == 13
    with pytest.raises(ValueError):
        parse_remaining_lease("sixty years")
