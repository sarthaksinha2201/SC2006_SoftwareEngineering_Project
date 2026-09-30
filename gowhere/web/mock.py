"""Regenerate the front-end contract fixtures from the real engine and snapshot.

    python -m gowhere.web.mock

Commute uses FixedRouter (fixed minutes, no network, no real destination), so the
fixtures are reproducible for a given snapshot.
"""
import json

from gowhere import config
from gowhere.scoring.engine import FactorChoice, ScoringEngine
from gowhere.scoring.registry import default_strategies
from gowhere.snapshot import Snapshot
from gowhere.web.view_models import results_view

FIXTURE_DIR = config.ROOT / "tests" / "fixtures"
EXAMPLE_POSTAL = "000000"   # placeholder; FixedRouter never looks it up


class FixedRouter:
    """A CommuteRouter stand-in returning fixed minutes per area."""

    def __init__(self, minutes):
        self._minutes = minutes

    def locate(self, postal):
        return (1.3, 103.8)

    def minutes(self, origins, postal, mode):
        return {a: self._minutes.get(a) for a in origins}


def _choices(facility_type):
    return {
        "public_transport": FactorChoice(8),
        "housing_affordability": FactorChoice(7, {"flat_type": "4 ROOM", "budget_min": 400_000,
                                                  "budget_max": 700_000,
                                                  "min_remaining_lease_years": 60}),
        "amenities": FactorChoice(5, {"amenity_types": ["supermarket", "hawker_centre", "cafe"]}),
        "greenery": FactorChoice(4),
        "healthcare": FactorChoice(5, {"facility_type": facility_type}),
        "commute": FactorChoice(6, {"destination_postal": EXAMPLE_POSTAL, "mode": "pt"}),
    }


SCENARIOS = {
    # Changi: small-area note, far-from-rail note, and too few resales -> Housing dropped.
    # Tengah: far-from-rail note. GP option -> CHAS note. Cafes -> OpenStreetMap note.
    "mock_results.json": (["CHANGI", "TAMPINES", "PASIR RIS", "TENGAH"], "gp",
                          {"CHANGI": 38.0, "TAMPINES": 44.5, "PASIR RIS": 51.2, "TENGAH": 66.8}),
    # All six factors scored, so the housing-window note appears.
    "mock_results_all_scored.json": (["PUNGGOL", "TAMPINES", "BEDOK", "PASIR RIS"], "polyclinic",
                                     {"PUNGGOL": 54.7, "TAMPINES": 43.9, "BEDOK": 39.6,
                                      "PASIR RIS": 51.2}),
}


def build(snapshot=None):
    snapshot = snapshot or Snapshot()
    out = {}
    for name, (areas, facility, minutes) in SCENARIOS.items():
        engine = ScoringEngine(default_strategies(FixedRouter(minutes)), snapshot)
        out[name] = results_view(engine.compare(areas, _choices(facility)), snapshot)
    return out


def main():
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    for name, view in build().items():
        (FIXTURE_DIR / name).write_text(json.dumps(view, indent=1, ensure_ascii=False) + "\n")
        print(f"wrote tests/fixtures/{name}")


if __name__ == "__main__":
    main()
