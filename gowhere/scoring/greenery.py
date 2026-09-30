"""Greenery category score (DECISIONS.md section 2).

Per area: flat-weighted % of flats within 400 m (straight line) of a park, nature
reserve or park connector. Distance is measured to the park's boundary, not a centre
point: a point inside a park is at distance 0, and a large park's centre can be hundreds
of metres from its edge. Only the built connector network counts, not planned routes.
Score = PR(% within 400 m, higher better) across in-scope areas, average rank for ties.
The median distance is reported, not scored.
"""
from gowhere import config
from gowhere.etl.geo import LocalProjection, NearestIndex
from gowhere.scoring.base import (ScoringStrategy, add_percentile_scores, group_by_area,
                                  select_by_area)
from gowhere.scoring.stats import weighted_quantile, weighted_share_at_most


class GreeneryScorer(ScoringStrategy):
    key = "greenery"
    label = "Greenery"

    def __init__(self, radius_m=config.GREEN_SPACE_RADIUS_M):
        self.radius_m = radius_m

    def schema(self):
        return """
CREATE TABLE greenery_block (
    block_id INTEGER PRIMARY KEY REFERENCES hdb_block(id),
    nearest_green_space TEXT NOT NULL,
    green_space_type TEXT NOT NULL,       -- 'park' or 'park connector'
    distance_m REAL NOT NULL);            -- to the boundary; 0 inside a park
CREATE TABLE greenery_area (
    planning_area TEXT PRIMARY KEY REFERENCES planning_area(name),
    n_blocks INTEGER NOT NULL, n_flats INTEGER NOT NULL,
    pct_within_radius REAL NOT NULL,      -- radius in meta.green_space_radius_m
    median_distance_m REAL NOT NULL,
    score REAL NOT NULL);
"""

    def precompute(self, blocks, sources):
        proj = LocalProjection()
        indexes = {"park": NearestIndex(sources.parks(), proj),
                   "park connector": NearestIndex(sources.park_connectors(), proj)}
        block_rows = []
        for b in blocks:
            kind, (name, dist) = min(((k, idx.nearest(b["lat"], b["lon"]))
                                      for k, idx in indexes.items()), key=lambda t: t[1][1])
            block_rows.append({"block_id": b["id"], "nearest_green_space": name,
                               "green_space_type": kind, "distance_m": dist})
        dist_of = {r["block_id"]: r["distance_m"] for r in block_rows}
        area_rows = [{"planning_area": a, "n_blocks": len(d), "n_flats": sum(f),
                      "pct_within_radius": weighted_share_at_most(d, f, self.radius_m),
                      "median_distance_m": weighted_quantile(d, f, 0.5)}
                     for a, (d, f) in sorted(group_by_area(blocks, lambda b: dist_of[b["id"]]).items())]
        add_percentile_scores(area_rows, "pct_within_radius", higher_is_better=True)
        return {"greenery_block": block_rows, "greenery_area": area_rows}

    def meta(self, sources):
        return {"green_space_radius_m": str(self.radius_m),
                "parks": str(len(sources.parks())),
                "park_connector_segments": str(len(sources.park_connectors()))}

    def category_scores(self, snapshot, areas, options):
        rows = select_by_area(snapshot, "greenery_area", ["score"], areas)
        return {a: rows[a]["score"] if a in rows else None for a in areas}

    def raw_values(self, snapshot, areas, options):
        radius = float(snapshot.meta()["green_space_radius_m"])
        rows = select_by_area(snapshot, "greenery_area",
                              ["pct_within_radius", "median_distance_m"], areas)
        return {a: {f"% of flats within {radius:.0f} m of a park or park connector":
                    r["pct_within_radius"],
                    "median distance to green space (m)": r["median_distance_m"]}
                for a, r in rows.items()}
