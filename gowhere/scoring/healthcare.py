"""Healthcare category score (DECISIONS.md section 2).

The user chooses a facility type at request time: GP clinics, polyclinics or hospitals.
For every type, each block's straight-line distance to its nearest facility is
precomputed; per area, the flat-weighted median of those distances is scored by
percentile rank (shorter is better) across in-scope areas, average rank for ties.

Sources: GP clinics are CHAS medical clinics (MOH). Polyclinics and the hospital
classification come from the hand-compiled, sourced files in data/reference/.
"""
from gowhere.etl.geo import LocalProjection, NearestIndex
from gowhere.scoring.base import (ScoringStrategy, add_percentile_scores, group_by_area,
                                  select_by_area)
from gowhere.scoring.stats import weighted_quantile

FACILITY_LABELS = {
    "gp": "GP clinic (CHAS)",
    "polyclinic": "polyclinic",
    "hospital": "hospital with 24-hour emergency or urgent care",
}


class HealthcareScorer(ScoringStrategy):
    key = "healthcare"
    label = "Healthcare"

    def schema(self):
        return """
CREATE TABLE healthcare_facility (facility_type TEXT NOT NULL, name TEXT NOT NULL,
    lat REAL NOT NULL, lon REAL NOT NULL);
CREATE TABLE healthcare_block (
    block_id INTEGER NOT NULL REFERENCES hdb_block(id),
    facility_type TEXT NOT NULL,          -- 'gp', 'polyclinic' or 'hospital'
    nearest_facility TEXT NOT NULL,
    distance_m REAL NOT NULL,             -- straight line
    PRIMARY KEY (block_id, facility_type));
CREATE TABLE healthcare_area (
    planning_area TEXT NOT NULL REFERENCES planning_area(name),
    facility_type TEXT NOT NULL,
    n_blocks INTEGER NOT NULL, n_flats INTEGER NOT NULL,
    median_distance_m REAL NOT NULL,
    score REAL NOT NULL,                  -- percentile rank within this facility type
    PRIMARY KEY (planning_area, facility_type));
"""

    def precompute(self, blocks, sources):
        proj = LocalProjection()
        facility_rows, block_rows, area_rows = [], [], []
        for ftype, facilities in sorted(sources.facilities().items()):
            if not facilities:
                raise ValueError(f"no {ftype} facilities loaded")
            facility_rows += [{"facility_type": ftype, "name": f["name"],
                               "lat": f["lat"], "lon": f["lon"]} for f in facilities]
            index = NearestIndex(facilities, proj)
            dist_of = {}
            for b in blocks:
                name, dist = index.nearest(b["lat"], b["lon"])
                dist_of[b["id"]] = dist
                block_rows.append({"block_id": b["id"], "facility_type": ftype,
                                   "nearest_facility": name, "distance_m": dist})
            rows = [{"planning_area": a, "facility_type": ftype, "n_blocks": len(d),
                     "n_flats": sum(f), "median_distance_m": weighted_quantile(d, f, 0.5)}
                    for a, (d, f) in sorted(group_by_area(blocks, lambda b: dist_of[b["id"]]).items())]
            area_rows += add_percentile_scores(rows, "median_distance_m", higher_is_better=False)
        return {"healthcare_facility": facility_rows, "healthcare_block": block_rows,
                "healthcare_area": area_rows}

    def meta(self, sources):
        counts = {t: len(f) for t, f in sources.facilities().items()}
        dates = sources.facilities_as_of()
        return {**{f"{t}_facilities": str(n) for t, n in counts.items()},
                **{f"{t}_data_as_of": d for t, d in dates.items()},
                "polyclinic_source": "hand-compiled: data/reference/polyclinics.csv",
                "hospital_source": "OneMap moh_hospitals theme, filtered by "
                                   "data/reference/hospitals.csv (hand-compiled)"}

    def options(self, snapshot):
        types = [r["facility_type"] for r in snapshot.query(
            "SELECT DISTINCT facility_type FROM healthcare_area ORDER BY facility_type")]
        return {"facility_type": types}

    def category_scores(self, snapshot, areas, options):
        rows = select_by_area(snapshot, "healthcare_area", ["score"], areas,
                              where="facility_type = ?", params=(options["facility_type"],))
        return {a: rows[a]["score"] if a in rows else None for a in areas}

    def raw_values(self, snapshot, areas, options):
        ftype = options["facility_type"]
        rows = select_by_area(snapshot, "healthcare_area", ["median_distance_m"], areas,
                              where="facility_type = ?", params=(ftype,))
        return {a: {f"median distance to nearest {FACILITY_LABELS.get(ftype, ftype)} (m)":
                    r["median_distance_m"]} for a, r in rows.items()}
