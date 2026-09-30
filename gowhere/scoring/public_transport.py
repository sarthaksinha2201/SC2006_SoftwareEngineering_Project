"""Public Transport category score (DECISIONS.md section 2).

Per area, flat-weighted over its HDB blocks (weight = total_dwelling_units):
  - % of flats within a 10-minute walk of an MRT/LRT exit
  - median and P90 walking time
Score = 0.7 x PR(% within 10 min, higher better) + 0.3 x PR(median walk, lower better),
where PR is the 0-10 percentile rank across all in-scope areas (average rank for ties).
P90 is reported, not scored.

Walking time = straight-line distance to the nearest exit x detour factor / 80 m per min.
"""
from gowhere import config
from gowhere.etl.geo import nearest, walk_minutes
from gowhere.scoring import notes
from gowhere.scoring.base import ScoringStrategy, group_by_area, select_by_area
from gowhere.scoring.stats import percentile_ranks, weighted_quantile, weighted_share_at_most

WEIGHT_PCT_WITHIN = 0.7
WEIGHT_MEDIAN = 0.3


def area_metrics(walk_minutes, flats, threshold=config.WALK_THRESHOLD_MIN):
    """Flat-weighted walking metrics for one area's blocks."""
    return {
        "n_blocks": len(walk_minutes),
        "n_flats": sum(flats),
        "pct_within_10": weighted_share_at_most(walk_minutes, flats, threshold),
        "median_walk_min": weighted_quantile(walk_minutes, flats, 0.5),
        "p90_walk_min": weighted_quantile(walk_minutes, flats, 0.9),
    }


def public_transport_scores(metrics):
    """metrics: {area: area_metrics(...)} -> {area: {"pr_pct_within_10", "pr_median_walk", "score"}}"""
    pr_pct = percentile_ranks({a: m["pct_within_10"] for a, m in metrics.items()},
                              higher_is_better=True)
    pr_med = percentile_ranks({a: m["median_walk_min"] for a, m in metrics.items()},
                              higher_is_better=False)
    return {a: {"pr_pct_within_10": pr_pct[a], "pr_median_walk": pr_med[a],
                "score": WEIGHT_PCT_WITHIN * pr_pct[a] + WEIGHT_MEDIAN * pr_med[a]}
            for a in metrics}


class PublicTransportScorer(ScoringStrategy):
    key = "public_transport"
    label = "Public Transport"

    def __init__(self, detour=config.DETOUR_FACTOR, far_from_rail_m=config.FAR_FROM_RAIL_M):
        self.detour = detour
        self.far_from_rail_m = far_from_rail_m

    def schema(self):
        return """
CREATE TABLE mrt_exit (station TEXT NOT NULL, exit_code TEXT NOT NULL,
    lat REAL NOT NULL, lon REAL NOT NULL);           -- MRT and LRT exits, one set
CREATE TABLE public_transport_block (
    block_id INTEGER PRIMARY KEY REFERENCES hdb_block(id),
    nearest_station TEXT NOT NULL, nearest_exit_code TEXT NOT NULL,
    exit_distance_m REAL NOT NULL,        -- straight line (Haversine)
    walk_min REAL NOT NULL);              -- exit_distance_m x detour / walk speed
CREATE TABLE public_transport_area (
    planning_area TEXT PRIMARY KEY REFERENCES planning_area(name),
    n_blocks INTEGER NOT NULL, n_flats INTEGER NOT NULL,
    pct_within_10 REAL NOT NULL, median_walk_min REAL NOT NULL, p90_walk_min REAL NOT NULL,
    median_exit_distance_m REAL NOT NULL,
    far_from_rail INTEGER NOT NULL,       -- 1 if median_exit_distance_m > meta.far_from_rail_m
    pr_pct_within_10 REAL NOT NULL, pr_median_walk REAL NOT NULL,
    score REAL NOT NULL);
"""

    def precompute(self, blocks, sources):
        exits = sources.mrt_exits()
        block_rows = []
        for b in blocks:
            exit_, dist = nearest(b["lat"], b["lon"], exits)
            block_rows.append({"block_id": b["id"], "nearest_station": exit_["station"],
                               "nearest_exit_code": exit_["exit_code"], "exit_distance_m": dist,
                               "walk_min": walk_minutes(dist, detour=self.detour)})
        by_block = {r["block_id"]: r for r in block_rows}
        walks = group_by_area(blocks, lambda b: by_block[b["id"]]["walk_min"])
        dists = group_by_area(blocks, lambda b: by_block[b["id"]]["exit_distance_m"])
        metrics = {a: area_metrics(w, f) for a, (w, f) in walks.items()}
        scores = public_transport_scores(metrics)
        area_rows = []
        for a, m in sorted(metrics.items()):
            median_dist = weighted_quantile(*dists[a], 0.5)
            area_rows.append({"planning_area": a, **m, "median_exit_distance_m": median_dist,
                              "far_from_rail": int(median_dist > self.far_from_rail_m),
                              **scores[a]})
        return {"mrt_exit": [dict(e) for e in exits],
                "public_transport_block": block_rows,
                "public_transport_area": area_rows}

    def meta(self, sources):
        exits = sources.mrt_exits()
        stations = {e["station"] for e in exits}
        return {"detour_factor": str(self.detour),
                "rail_exits": str(len(exits)), "rail_stations": str(len(stations)),
                "lrt_stations": str(sum("LRT" in s for s in stations)),
                "rail_data_as_of": sources.mrt_exits_as_of(),
                "far_from_rail_m": str(self.far_from_rail_m)}

    def category_scores(self, snapshot, areas, options):
        rows = select_by_area(snapshot, "public_transport_area", ["score"], areas)
        return {a: rows[a]["score"] if a in rows else None for a in areas}

    def raw_values(self, snapshot, areas, options):
        rows = select_by_area(snapshot, "public_transport_area",
                              ["pct_within_10", "median_walk_min", "p90_walk_min"], areas)
        return {a: {"% of flats within 10 min walk": r["pct_within_10"],
                    "median walk (min)": r["median_walk_min"],
                    "90th percentile walk (min)": r["p90_walk_min"]}
                for a, r in rows.items()}

    def notes(self, snapshot, areas, options):
        rows = select_by_area(snapshot, "public_transport_area", ["far_from_rail"], areas)
        far = [a for a, r in rows.items() if r["far_from_rail"]]
        if not far:
            return {}
        note = notes.rail_data_note(snapshot.meta()["rail_data_as_of"])
        return {a: [note] for a in far}
