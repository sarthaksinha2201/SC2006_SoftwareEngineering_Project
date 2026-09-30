"""Amenities category score (DECISIONS.md section 2).

The user picks one or more amenity types. For each HDB block, count each selected type
within 800 m (straight line), cap each count at 3, and add them up; so twenty cafes
cannot outweigh having no supermarket. Per area, take the flat-weighted median of that
sum, and score it by percentile rank across in-scope areas (average rank for ties; the
cap makes ties common).

Every non-empty combination of the six types (63) is precomputed per area, so the
request only looks up a row.

Sources: supermarkets (SFA licences), hawker centres (NEA), libraries (NLB); malls, gyms
and cafes from OpenStreetMap (© OpenStreetMap contributors).
"""
from itertools import combinations

from gowhere import config
from gowhere.etl.geo import CountIndex, LocalProjection
from gowhere.scoring.base import (ScoringStrategy, SubsetOf, add_percentile_scores,
                                  group_by_area, select_by_area)
from gowhere.scoring.stats import round1, weighted_quantile

AMENITY_TYPES = {  # key -> plural label, in canonical order
    "supermarket": "supermarkets", "hawker_centre": "hawker centres", "library": "libraries",
    "mall": "malls", "gym": "gyms", "cafe": "cafes"}
OSM_TYPES = {"mall", "gym", "cafe"}


def combination_key(types):
    """Canonical key for a selection, e.g. ['cafe', 'supermarket'] -> 'supermarket,cafe'."""
    return ",".join(t for t in AMENITY_TYPES if t in types)


def all_combinations():
    keys = list(AMENITY_TYPES)
    return [c for n in range(1, len(keys) + 1) for c in combinations(keys, n)]


class AmenitiesScorer(ScoringStrategy):
    key = "amenities"
    label = "Amenities"

    def __init__(self, radius_m=config.AMENITY_RADIUS_M, cap=config.AMENITY_CAP):
        self.radius_m, self.cap = radius_m, cap

    def schema(self):
        return """
CREATE TABLE amenity_block (
    block_id INTEGER NOT NULL REFERENCES hdb_block(id),
    amenity_type TEXT NOT NULL,
    count_within INTEGER NOT NULL,        -- uncapped, within meta.amenity_radius_m
    PRIMARY KEY (block_id, amenity_type));
CREATE TABLE amenity_area (
    planning_area TEXT NOT NULL REFERENCES planning_area(name),
    amenity_types TEXT NOT NULL,          -- canonical comma list, e.g. 'supermarket,cafe'
    median_capped_count REAL NOT NULL,    -- flat-weighted median of the capped sum
    score REAL NOT NULL,                  -- percentile rank within this combination
    PRIMARY KEY (planning_area, amenity_types));
"""

    def precompute(self, blocks, sources):
        proj = LocalProjection()
        counts = {}   # (block id, type) -> uncapped count
        block_rows = []
        for kind, points in sources.amenities().items():
            if kind not in AMENITY_TYPES:
                continue
            index = CountIndex(points, proj)
            for b in blocks:
                n = index.count_within(b["lat"], b["lon"], self.radius_m)
                counts[(b["id"], kind)] = n
                block_rows.append({"block_id": b["id"], "amenity_type": kind, "count_within": n})
        area_rows = []
        for combo in all_combinations():
            value = lambda b: sum(min(counts[(b["id"], t)], self.cap) for t in combo)
            rows = [{"planning_area": a, "amenity_types": combination_key(combo),
                     "median_capped_count": weighted_quantile(v, f, 0.5)}
                    for a, (v, f) in sorted(group_by_area(blocks, value).items())]
            area_rows += add_percentile_scores(rows, "median_capped_count", higher_is_better=True)
        return {"amenity_block": block_rows, "amenity_area": area_rows}

    def meta(self, sources):
        dates = sources.amenities_as_of()
        return {"amenity_radius_m": str(self.radius_m), "amenity_cap": str(self.cap),
                **{f"{k}_count": str(len(v)) for k, v in sources.amenities().items()},
                **{f"{k}_data_as_of": v for k, v in dates.items()},
                **{k: str(v) for k, v in sources.amenities_meta().items()}}

    def options(self, snapshot):
        return {"amenity_types": SubsetOf(tuple(AMENITY_TYPES))}

    def category_scores(self, snapshot, areas, options):
        rows = select_by_area(snapshot, "amenity_area", ["score"], areas, where="amenity_types = ?",
                              params=(combination_key(options["amenity_types"]),))
        return {a: rows[a]["score"] if a in rows else None for a in areas}

    def raw_values(self, snapshot, areas, options):
        selected = [t for t in AMENITY_TYPES if t in options["amenity_types"]]
        combined = select_by_area(snapshot, "amenity_area", ["median_capped_count"], areas,
                                  where="amenity_types = ?", params=(combination_key(selected),))
        out = {}
        for a, r in combined.items():
            out[a] = {"summary": f"The typical flat has {round1(r['median_capped_count']):g} of "
                                 f"the selected amenities within {self.radius_m:.0f} m "
                                 f"(each type counted up to {self.cap})"}
        for t in selected:
            rows = select_by_area(snapshot, "amenity_area", ["median_capped_count"], areas,
                                  where="amenity_types = ?", params=(t,))
            for a, r in rows.items():
                out.setdefault(a, {})[f"{AMENITY_TYPES[t]} (typical flat, up to {self.cap})"] = \
                    r["median_capped_count"]
        return out

    def factor_notes(self, snapshot, options):
        meta, selected = snapshot.meta(), set(options["amenity_types"])
        notes = []
        if "supermarket" in selected:
            notes.append("Supermarkets come from SFA's supermarket licence list (published "
                         "Jun 2024); stores opened or closed since may be missing or still listed.")
        if selected & OSM_TYPES:
            names = ", ".join(AMENITY_TYPES[t] for t in AMENITY_TYPES if t in selected & OSM_TYPES)
            notes.append(f"{names[0].upper()}{names[1:]} come from OpenStreetMap "
                         f"(© OpenStreetMap contributors), which volunteers keep up to date "
                         f"and may be incomplete.")
        return notes
