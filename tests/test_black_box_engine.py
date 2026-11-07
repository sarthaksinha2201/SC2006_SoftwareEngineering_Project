"""Black-box test of ScoringEngine.compare (Lab 4 3.2.1): equivalence classes and
boundary values, designed from the Where to Live FRs, not from the code.

One row per test case in docs/testing/black-box-scoring-engine.md; the ids match (BB-01
to BB-25). Valid cases combine many valid classes at once; each invalid case has exactly
one invalid input and every other input valid (Lecture 17).

Runs against the real committed snapshot (data/snapshot.db) and the six real factors.
The only stand-in is OneMap, an External Service outside the class under test.
"""
import pytest

from gowhere.scoring.base import InvalidRequest
from gowhere.scoring.commute import CommuteRouter
from gowhere.scoring.engine import FactorChoice as F
from gowhere.scoring.engine import ScoringEngine
from gowhere.scoring.registry import default_strategies
from gowhere.snapshot import Snapshot

POSTAL = "018956"
ALL_AMENITIES = ["supermarket", "hawker_centre", "library", "mall", "gym", "cafe"]
AMENITIES_MESSAGE = ("Amenities: choose one or more of supermarkets, hawker centres, libraries, "
                     "malls, gyms, cafes, each once")
GREENERY = {"greenery": F(5)}


class FakeOneMap:
    """Every postal code resolves; every route takes 30 min by transit, 20 by car."""

    def search(self, query, redact=False):
        return {"results": [{"POSTAL": query, "LATITUDE": "1.28", "LONGITUDE": "103.85"}]}

    def transit_route(self, start, end, departure, redact=False, retries=4):
        return {"plan": {"itineraries": [{"duration": 1800}]}}

    def drive_route(self, start, end, redact=False, retries=4):
        return {"route_summary": {"total_time": 1200}}


def housing(**changes):
    return F(5, {"flat_type": "4 ROOM", "budget_min": 300_000, "budget_max": 700_000,
                 "min_remaining_lease_years": None, **changes})


@pytest.fixture(scope="module")
def engine():
    return ScoringEngine(default_strategies(CommuteRouter(adapter=FakeOneMap())), Snapshot())


# ---- valid cases: the comparison runs and ranks every selected area -----------------

VALID = {
    # 2 areas (min), 1 factor (min), weight 1 (min)
    "BB-01": (["BEDOK", "TAMPINES"], {"greenery": F(1)}),
    # 4 areas (max), all 6 factors (max), weight 10 (max), budget 0 and 5,000,000
    # (both range ends), all 6 amenity types (max)
    "BB-02": (["BEDOK", "TAMPINES", "BISHAN", "PUNGGOL"], {
        "public_transport": F(10, {"mode": "either"}),
        "housing_affordability": F(5, {"flat_type": "4 ROOM", "budget_min": 0,
                                       "budget_max": 5_000_000,
                                       "min_remaining_lease_years": None}),
        "amenities": F(5, {"amenity_types": ALL_AMENITIES}),
        "greenery": F(5),
        "healthcare": F(5, {"facility_type": "polyclinic"}),
        "commute": F(5, {"destination_postal": POSTAL, "mode": "pt"})}),
    # 3 areas (nominal), budget minimum = maximum (boundary), 1 amenity type (min)
    "BB-03": (["ANG MO KIO", "BUKIT BATOK", "QUEENSTOWN"], {
        "public_transport": F(5, {"mode": "rail"}),
        "housing_affordability": F(5, {"flat_type": "EXECUTIVE", "budget_min": 800_000,
                                       "budget_max": 800_000,
                                       "min_remaining_lease_years": 80}),
        "amenities": F(5, {"amenity_types": ["library"]}),
        "healthcare": F(5, {"facility_type": "gp"}),
        "commute": F(5, {"destination_postal": POSTAL, "mode": "drive"})}),
    # the remaining values of the small discrete classes
    "BB-04": (["JURONG WEST", "WOODLANDS"], {
        "public_transport": F(2, {"mode": "bus"}),
        "healthcare": F(9, {"facility_type": "hospital"}),
        "housing_affordability": F(5, {"flat_type": "3 ROOM", "budget_min": 200_000,
                                       "budget_max": 600_000,
                                       "min_remaining_lease_years": 60})}),
}


@pytest.mark.parametrize("case", VALID, ids=list(VALID))
def test_valid_requests_rank_every_area(engine, case):
    areas, choices = VALID[case]
    result = engine.compare(areas, choices)
    assert sorted(a["name"] for a in result["areas"]) == sorted(areas)
    assert result["areas"][0]["rank"] == 1
    assert all(0 <= a["overall_display"] <= 10 for a in result["areas"])
    # every included factor is either scored or reported as dropped (FR 1.3.x)
    scored = {f["key"] for f in result["factors"]}
    dropped = {d["key"] for d in result["dropped"]}
    assert scored | dropped == set(choices) and not scored & dropped


# ---- invalid cases: exactly one invalid input each ----------------------------------

INVALID = {
    "BB-05": (["BEDOK"], GREENERY, "select 2 to 4 neighbourhoods"),
    "BB-06": (["BEDOK", "TAMPINES", "BISHAN", "PUNGGOL", "SENGKANG"], GREENERY,
              "select 2 to 4 neighbourhoods"),
    "BB-07": (["BEDOK", "BEDOK"], GREENERY, "each neighbourhood can be selected once"),
    "BB-08": (["BEDOK", "BOON LAY"], GREENERY, "not an in-scope neighbourhood: BOON LAY"),
    "BB-09": (["BEDOK", "ATLANTIS"], GREENERY, "not an in-scope neighbourhood: ATLANTIS"),
    "BB-10": (["BEDOK", "TAMPINES"], {}, "include at least one factor"),
    "BB-11": (["BEDOK", "TAMPINES"], {"crowdedness": F(5)}, "unknown factor: crowdedness"),
    "BB-12": (["BEDOK", "TAMPINES"], {"greenery": F(0)},
              "Greenery: weight must be a whole number from 1 to 10"),
    "BB-13": (["BEDOK", "TAMPINES"], {"greenery": F(11)},
              "Greenery: weight must be a whole number from 1 to 10"),
    "BB-14": (["BEDOK", "TAMPINES"], {"greenery": F(5.5)},
              "Greenery: weight must be a whole number from 1 to 10"),
    "BB-15": (["BEDOK", "TAMPINES"], {"healthcare": F(5, {})},
              "Healthcare: options must be exactly facility type"),
    "BB-16": (["BEDOK", "TAMPINES"], {"healthcare": F(5, {"facility_type": "clinic"})},
              "Healthcare: facility type must be one of GP clinic (CHAS), public acute hospital, polyclinic"),
    "BB-17": (["BEDOK", "TAMPINES"], {"housing_affordability": housing(budget_min=-1)},
              "Housing Affordability: budget minimum must be a number from 0 to 5,000,000"),
    "BB-18": (["BEDOK", "TAMPINES"], {"housing_affordability": housing(budget_max=5_000_001)},
              "Housing Affordability: budget maximum must be a number from 0 to 5,000,000"),
    "BB-19": (["BEDOK", "TAMPINES"],
              {"housing_affordability": housing(budget_min=700_001, budget_max=700_000)},
              "Housing Affordability: budget minimum must not exceed budget maximum"),
    "BB-20": (["BEDOK", "TAMPINES"], {"amenities": F(5, {"amenity_types": []})},
              AMENITIES_MESSAGE),
    "BB-21": (["BEDOK", "TAMPINES"], {"amenities": F(5, {"amenity_types": ["gym", "gym"]})},
              AMENITIES_MESSAGE),
    "BB-22": (["BEDOK", "TAMPINES"], {"amenities": F(5, {"amenity_types": ["cinema"]})},
              AMENITIES_MESSAGE),
    "BB-23": (["BEDOK", "TAMPINES"],
              {"commute": F(5, {"destination_postal": "12345", "mode": "pt"})},
              "Commute: destination postal code must be a 6-digit Singapore postal code"),
    "BB-24": (["BEDOK", "TAMPINES"],
              {"commute": F(5, {"destination_postal": "1234567", "mode": "pt"})},
              "Commute: destination postal code must be a 6-digit Singapore postal code"),
    "BB-25": (["BEDOK", "TAMPINES"],
              {"commute": F(5, {"destination_postal": "12345A", "mode": "pt"})},
              "Commute: destination postal code must be a 6-digit Singapore postal code"),
}

# BB-17 and BB-18 found defect D1 (docs/testing/black-box-scoring-engine.md): the budget
# limit was printed with :g, so a user who typed 6000000 read "from 0 to 5e+06". Fixed;
# they now guard against it coming back.


@pytest.mark.parametrize("case", INVALID, ids=list(INVALID))
def test_invalid_requests_are_rejected_with_a_message(engine, case):
    areas, choices, message = INVALID[case]
    with pytest.raises(InvalidRequest) as err:
        engine.compare(areas, choices)
    assert str(err.value) == message
