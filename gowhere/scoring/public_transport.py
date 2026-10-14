"""Public Transport category score (DECISIONS.md sections 2 and 16; FR 1.2.4).

The user picks a mode (FR 1.2.4.1): MRT/LRT, Bus, or Either (the default). Per block,
the walk is to the nearest:
  - rail:   MRT or LRT exit
  - bus:    Qualifying Bus Stop, one served by at least 3 bus services (Data Dictionary)
  - either: whichever of those two is nearer
Per area, flat-weighted over its HDB blocks (weight = total_dwelling_units):
  - % of flats within a 10-minute walk
  - median and P90 walking time
Score = 0.7 x PR(% within 10 min, higher better) + 0.3 x PR(median walk, lower better),
where PR is the 0-10 percentile rank across all in-scope areas (average rank for ties),
ranked separately for each mode. P90 is reported, not scored.

Walking time = straight-line distance to the nearest stop x detour factor / 80 m per min.

The mode option exists only when the snapshot holds bus data (LTA DataMall, which needs
LTA_DATAMALL_KEY). Without it the factor is rail-only and takes no options.
"""
from gowhere import config
from gowhere.etl.geo import nearest, walk_minutes
from gowhere.scoring import notes
from gowhere.scoring.base import ScoringStrategy, group_by_area, select_by_area
from gowhere.scoring.stats import (percentile_ranks, round1, weighted_quantile,
                                   weighted_share_at_most)

WEIGHT_PCT_WITHIN = 0.7
WEIGHT_MEDIAN = 0.3
# key -> what the walk is to, in the order the form lists them (FR 1.2.4.1)
MODES = {"rail": "an MRT/LRT exit",
         "bus": "a bus stop with 3 or more services",
         "either": "an MRT/LRT exit or a bus stop with 3 or more services"}
MODE_LABELS = {"rail": "MRT/LRT", "bus": "Bus", "either": "Either"}
DEFAULT_MODE = "either"


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


def mode_walk(block_row, mode):
    """(walk minutes, distance m) for one block under one mode."""
    if mode == "rail":
        return block_row["walk_min"], block_row["exit_distance_m"]
    if mode == "bus":
        return block_row["bus_walk_min"], block_row["bus_distance_m"]
    return min((block_row["walk_min"], block_row["exit_distance_m"]),
               (block_row["bus_walk_min"], block_row["bus_distance_m"]))


class PublicTransportScorer(ScoringStrategy):
    key = "public_transport"
    label = "Public Transport"
    option_labels = {"mode": "public transport mode"}

    def __init__(self, detour=config.DETOUR_FACTOR, far_from_rail_m=config.FAR_FROM_RAIL_M):
        self.detour = detour
        self.far_from_rail_m = far_from_rail_m

    def schema(self):
        return """
CREATE TABLE mrt_exit (station TEXT NOT NULL, exit_code TEXT NOT NULL,
    lat REAL NOT NULL, lon REAL NOT NULL);           -- MRT and LRT exits, one set
CREATE TABLE bus_stop (code TEXT PRIMARY KEY, name TEXT NOT NULL,
    lat REAL NOT NULL, lon REAL NOT NULL,
    services INTEGER NOT NULL);           -- Qualifying Bus Stops only (>= 3 services)
CREATE TABLE public_transport_block (
    block_id INTEGER PRIMARY KEY REFERENCES hdb_block(id),
    nearest_station TEXT NOT NULL, nearest_exit_code TEXT NOT NULL,
    exit_distance_m REAL NOT NULL,        -- straight line (Haversine)
    walk_min REAL NOT NULL,               -- exit_distance_m x detour / walk speed
    nearest_bus_stop TEXT,                -- NULL when the snapshot has no bus data
    bus_distance_m REAL, bus_walk_min REAL);
CREATE TABLE public_transport_area (
    planning_area TEXT NOT NULL REFERENCES planning_area(name),
    mode TEXT NOT NULL,                   -- 'rail', 'bus' or 'either'
    n_blocks INTEGER NOT NULL, n_flats INTEGER NOT NULL,
    pct_within_10 REAL NOT NULL, median_walk_min REAL NOT NULL, p90_walk_min REAL NOT NULL,
    median_distance_m REAL NOT NULL,      -- to this mode's nearest stop or exit
    far_from_rail INTEGER NOT NULL,       -- 1 if the median rail exit distance > meta.far_from_rail_m
    pr_pct_within_10 REAL NOT NULL, pr_median_walk REAL NOT NULL,
    score REAL NOT NULL,
    PRIMARY KEY (planning_area, mode));
"""

    def precompute(self, blocks, sources):
        exits = sources.mrt_exits()
        stops = sources.bus_stops() if hasattr(sources, "bus_stops") else []
        block_rows = []
        for b in blocks:
            exit_, dist = nearest(b["lat"], b["lon"], exits)
            row = {"block_id": b["id"], "nearest_station": exit_["station"],
                   "nearest_exit_code": exit_["exit_code"], "exit_distance_m": dist,
                   "walk_min": walk_minutes(dist, detour=self.detour),
                   "nearest_bus_stop": None, "bus_distance_m": None, "bus_walk_min": None}
            if stops:
                stop, bus_dist = nearest(b["lat"], b["lon"], stops)
                row.update(nearest_bus_stop=stop["code"], bus_distance_m=bus_dist,
                           bus_walk_min=walk_minutes(bus_dist, detour=self.detour))
            block_rows.append(row)
        by_block = {r["block_id"]: r for r in block_rows}
        rail_dists = group_by_area(blocks, lambda b: by_block[b["id"]]["exit_distance_m"])
        far = {a: int(weighted_quantile(*rail_dists[a], 0.5) > self.far_from_rail_m)
               for a in rail_dists}
        area_rows = []
        for mode in (list(MODES) if stops else ["rail"]):
            walks = group_by_area(blocks, lambda b: mode_walk(by_block[b["id"]], mode)[0])
            dists = group_by_area(blocks, lambda b: mode_walk(by_block[b["id"]], mode)[1])
            metrics = {a: area_metrics(w, f) for a, (w, f) in walks.items()}
            scores = public_transport_scores(metrics)
            for a, m in sorted(metrics.items()):
                area_rows.append({"planning_area": a, "mode": mode, **m,
                                  "median_distance_m": weighted_quantile(*dists[a], 0.5),
                                  "far_from_rail": far[a], **scores[a]})
        return {"mrt_exit": [dict(e) for e in exits],
                "bus_stop": [{k: st[k] for k in ("code", "name", "lat", "lon", "services")}
                             for st in stops],
                "public_transport_block": block_rows,
                "public_transport_area": area_rows}

    def meta(self, sources):
        exits = sources.mrt_exits()
        stations = {e["station"] for e in exits}
        out = {"detour_factor": str(self.detour),
               "rail_exits": str(len(exits)), "rail_stations": str(len(stations)),
               "lrt_stations": str(sum("LRT" in s for s in stations)),
               "rail_data_as_of": sources.mrt_exits_as_of(),
               "far_from_rail_m": str(self.far_from_rail_m)}
        if hasattr(sources, "bus_meta"):
            out.update(sources.bus_meta())
        return out

    # ---- request time ---------------------------------------------------------------

    def _modes(self, snapshot):
        return [r["mode"] for r in snapshot.query(
            "SELECT DISTINCT mode FROM public_transport_area")]

    def options(self, snapshot):
        modes = self._modes(snapshot)
        if modes == ["rail"]:
            return {}                     # no bus data in this snapshot: rail only
        return {"mode": [m for m in MODES if m in modes]}

    @staticmethod
    def _mode(options):
        return options.get("mode", "rail")

    def category_scores(self, snapshot, areas, options):
        rows = select_by_area(snapshot, "public_transport_area", ["score"], areas,
                              where="mode = ?", params=(self._mode(options),))
        return {a: rows[a]["score"] if a in rows else None for a in areas}

    def raw_values(self, snapshot, areas, options):
        mode = self._mode(options)
        rows = select_by_area(snapshot, "public_transport_area",
                              ["pct_within_10", "median_walk_min", "p90_walk_min"], areas,
                              where="mode = ?", params=(mode,))
        return {a: {"summary": f"{round1(r['pct_within_10']):g}% of flats are within a 10-minute "
                               f"walk of {MODES[mode]}; median walk "
                               f"{round1(r['median_walk_min']):g} min",
                    "% of flats within 10 min walk": r["pct_within_10"],
                    "median walk (min)": r["median_walk_min"],
                    "90th percentile walk (min)": r["p90_walk_min"]}
                for a, r in rows.items()}

    def notes(self, snapshot, areas, options):
        if self._mode(options) == "bus":
            return {}                     # the rail-data note is about MRT/LRT exits
        rows = select_by_area(snapshot, "public_transport_area", ["far_from_rail"], areas,
                              where="mode = ?", params=(self._mode(options),))
        far = [a for a, r in rows.items() if r["far_from_rail"]]
        if not far:
            return {}
        note = notes.rail_data_note(snapshot.meta()["rail_data_as_of"])
        return {a: [note] for a in far}

    def factor_notes(self, snapshot, options):
        if self._mode(options) == "rail":
            return []
        meta = snapshot.meta()
        return [f"A bus stop counts when at least {meta['qualifying_bus_services']} bus services "
                f"stop there ({meta['bus_stops_qualifying']} stops, LTA data of "
                f"{meta['bus_data_as_of']})."]
