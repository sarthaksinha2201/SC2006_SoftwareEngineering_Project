"""Public Transport category score (DECISIONS.md sections 2, 16 and 18; FR 1.2.4).

The user picks a mode (FR 1.2.4.1): MRT/LRT, Bus, or Either (the default). Per area,
flat-weighted over its HDB blocks (weight = total_dwelling_units), with PR the 0-10
percentile rank across all in-scope areas (average rank for ties), ranked per mode:

  rail:   0.7 x PR(% of flats within a 10-minute walk of an MRT/LRT exit, higher better)
        + 0.3 x PR(median walk to the nearest exit, lower better)
  bus:    0.7 x PR(median number of distinct bus services stopping within 400 m, higher better)
        + 0.3 x PR(median walk to the nearest Qualifying Bus Stop, lower better)
  either: the higher of the rail and bus scores, area by area

Rail is scarce, so the walk to it is what varies. Bus stops are everywhere (30 of 32
areas have every flat within 10 minutes of a qualifying stop), so the bus measure
counts the services instead (DECISIONS.md section 18). A Qualifying Bus Stop is one
served by at least 3 bus services (Data Dictionary); the 400 m count uses every stop.
The higher of two percentile ranks is not itself a percentile rank, so Either scores
sit above either mode alone. P90 and the bus % within 10 minutes are reported, not scored.

Walking time = straight-line distance to the nearest stop x detour factor / 80 m per min.

The mode option exists only when the snapshot holds bus data (LTA DataMall, which needs
LTA_DATAMALL_KEY). Without it the factor is rail-only and takes no options.
"""
from gowhere import config
from gowhere.etl.geo import LocalProjection, nearest, walk_minutes
from gowhere.scoring import notes
from gowhere.scoring.base import ScoringStrategy, group_by_area, select_by_area
from gowhere.scoring.stats import (percentile_ranks, round1, weighted_quantile,
                                   weighted_share_at_most)

WEIGHT_PCT_WITHIN = 0.7
WEIGHT_MEDIAN = 0.3
WEIGHT_SERVICES = 0.7               # bus: the services term takes the 70% that rail gives to %
# in the order the form lists them (FR 1.2.4.1)
MODES = ("rail", "bus", "either")
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


def bus_scores(metrics):
    """metrics: {area: {"median_services", "median_walk_min"}} ->
    {area: {"pr_median_services", "pr_median_walk", "score"}}"""
    pr_svc = percentile_ranks({a: m["median_services"] for a, m in metrics.items()},
                              higher_is_better=True)
    pr_med = percentile_ranks({a: m["median_walk_min"] for a, m in metrics.items()},
                              higher_is_better=False)
    return {a: {"pr_median_services": pr_svc[a], "pr_median_walk": pr_med[a],
                "score": WEIGHT_SERVICES * pr_svc[a] + WEIGHT_MEDIAN * pr_med[a]}
            for a in metrics}


def either_choice(rail_score, bus_score):
    """(score, mode) for Either: the better-scoring mode; a tie counts as rail."""
    return (bus_score, "bus") if bus_score > rail_score else (rail_score, "rail")


class ServicesIndex:
    """Distinct bus services stopping within a straight-line radius of a point."""

    def __init__(self, stops, projection=None):
        """stops: [{"lat", "lon", "services": iterable of service numbers}]."""
        from shapely import STRtree
        from shapely.geometry import Point
        self._point = Point
        self.proj = projection or LocalProjection()
        self.services = [frozenset(st["services"]) for st in stops]
        self.tree = STRtree([Point(self.proj.xy(st["lat"], st["lon"])) for st in stops])

    def count_within(self, lat, lon, radius_m):
        hits = self.tree.query(self._point(self.proj.xy(lat, lon)), predicate="dwithin",
                               distance=radius_m)
        return len(frozenset().union(*(self.services[i] for i in hits)))


class PublicTransportScorer(ScoringStrategy):
    key = "public_transport"
    label = "Public Transport"
    option_labels = {"mode": "public transport mode"}

    def __init__(self, detour=config.DETOUR_FACTOR, far_from_rail_m=config.FAR_FROM_RAIL_M,
                 bus_catchment_m=config.BUS_CATCHMENT_M):
        self.detour = detour
        self.far_from_rail_m = far_from_rail_m
        self.bus_catchment_m = bus_catchment_m

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
    bus_distance_m REAL, bus_walk_min REAL,
    bus_services INTEGER);                -- distinct services at any stop within meta.bus_catchment_m
CREATE TABLE public_transport_area (
    planning_area TEXT NOT NULL REFERENCES planning_area(name),
    mode TEXT NOT NULL,                   -- 'rail' or 'bus'; Either is the higher of the two
    n_blocks INTEGER NOT NULL, n_flats INTEGER NOT NULL,
    pct_within_10 REAL NOT NULL, median_walk_min REAL NOT NULL, p90_walk_min REAL NOT NULL,
    median_distance_m REAL NOT NULL,      -- to this mode's nearest stop or exit
    far_from_rail INTEGER NOT NULL,       -- 1 if the median rail exit distance > meta.far_from_rail_m
    median_services REAL,                 -- bus only
    pr_pct_within_10 REAL,                -- rail only
    pr_median_services REAL,              -- bus only
    pr_median_walk REAL NOT NULL,
    score REAL NOT NULL,
    PRIMARY KEY (planning_area, mode));
"""

    def precompute(self, blocks, sources):
        exits = sources.mrt_exits()
        stops = sources.bus_stops() if hasattr(sources, "bus_stops") else []
        qualifying = [st for st in stops if len(st["services"]) >= config.QUALIFYING_BUS_SERVICES]
        services = ServicesIndex(stops) if stops else None
        block_rows = []
        for b in blocks:
            exit_, dist = nearest(b["lat"], b["lon"], exits)
            row = {"block_id": b["id"], "nearest_station": exit_["station"],
                   "nearest_exit_code": exit_["exit_code"], "exit_distance_m": dist,
                   "walk_min": walk_minutes(dist, detour=self.detour),
                   "nearest_bus_stop": None, "bus_distance_m": None, "bus_walk_min": None,
                   "bus_services": None}
            if stops:
                stop, bus_dist = nearest(b["lat"], b["lon"], qualifying)
                row.update(nearest_bus_stop=stop["code"], bus_distance_m=bus_dist,
                           bus_walk_min=walk_minutes(bus_dist, detour=self.detour),
                           bus_services=services.count_within(b["lat"], b["lon"],
                                                              self.bus_catchment_m))
            block_rows.append(row)
        by_block = {r["block_id"]: r for r in block_rows}
        column = lambda key: group_by_area(blocks, lambda b: by_block[b["id"]][key])
        rail_dists = column("exit_distance_m")
        far = {a: int(weighted_quantile(*rail_dists[a], 0.5) > self.far_from_rail_m)
               for a in rail_dists}

        rail = {a: area_metrics(w, f) for a, (w, f) in column("walk_min").items()}
        scores = public_transport_scores(rail)
        area_rows = [{"planning_area": a, "mode": "rail", **m,
                      "median_distance_m": weighted_quantile(*rail_dists[a], 0.5),
                      "far_from_rail": far[a], "median_services": None,
                      "pr_median_services": None, **scores[a]}
                     for a, m in sorted(rail.items())]
        if stops:
            bus_dists = column("bus_distance_m")
            bus = {a: {**area_metrics(w, f),
                       "median_services": weighted_quantile(*column("bus_services")[a], 0.5)}
                   for a, (w, f) in column("bus_walk_min").items()}
            scores = bus_scores(bus)
            area_rows += [{"planning_area": a, "mode": "bus", **m,
                           "median_distance_m": weighted_quantile(*bus_dists[a], 0.5),
                           "far_from_rail": far[a], "pr_pct_within_10": None, **scores[a]}
                          for a, m in sorted(bus.items())]
        return {"mrt_exit": [dict(e) for e in exits],
                "bus_stop": [{"code": st["code"], "name": st["name"], "lat": st["lat"],
                              "lon": st["lon"], "services": len(st["services"])}
                             for st in qualifying],
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
        if hasattr(sources, "bus_meta") and sources.bus_meta():
            out.update(sources.bus_meta(), bus_catchment_m=str(self.bus_catchment_m))
        return out

    # ---- request time ---------------------------------------------------------------

    def _modes(self, snapshot):
        stored = {r["mode"] for r in snapshot.query("SELECT DISTINCT mode FROM public_transport_area")}
        return [m for m in MODES if m in stored or (m == "either" and "bus" in stored)]

    def options(self, snapshot):
        modes = self._modes(snapshot)
        if modes == ["rail"]:
            return {}                     # no bus data in this snapshot: rail only
        return {"mode": modes}

    @staticmethod
    def _mode(options):
        return options.get("mode", "rail")

    def _rows(self, snapshot, areas, options):
        """{area: (scored mode, its public_transport_area row)}; Either picks per area."""
        mode = self._mode(options)
        cols = ["score", "pct_within_10", "median_walk_min", "p90_walk_min",
                "median_services", "far_from_rail"]
        if mode != "either":
            rows = select_by_area(snapshot, "public_transport_area", cols, areas,
                                  where="mode = ?", params=(mode,))
            return {a: (mode, r) for a, r in rows.items()}
        by_mode = {m: select_by_area(snapshot, "public_transport_area", cols, areas,
                                     where="mode = ?", params=(m,)) for m in ("rail", "bus")}
        out = {}
        for a in by_mode["rail"].keys() & by_mode["bus"].keys():
            _, chosen = either_choice(by_mode["rail"][a]["score"], by_mode["bus"][a]["score"])
            out[a] = (chosen, by_mode[chosen][a])
        return out

    def category_scores(self, snapshot, areas, options):
        rows = self._rows(snapshot, areas, options)
        return {a: rows[a][1]["score"] if a in rows else None for a in areas}

    def raw_values(self, snapshot, areas, options):
        either = self._mode(options) == "either"
        catchment = snapshot.meta().get("bus_catchment_m", str(config.BUS_CATCHMENT_M))
        out = {}
        for a, (mode, r) in self._rows(snapshot, areas, options).items():
            walk = f"median walk {round1(r['median_walk_min']):g} min"
            if mode == "rail":
                summary = (f"{round1(r['pct_within_10']):g}% of flats are within a 10-minute "
                           f"walk of an MRT/LRT exit; {walk}")
                values = {"% of flats within 10 min walk": r["pct_within_10"]}
            else:
                summary = (f"a median of {r['median_services']:g} different bus services stop "
                           f"within {catchment} m of a flat; {walk} to a bus stop with 3 or "
                           f"more services")
                values = {f"median bus services within {catchment} m": r["median_services"]}
            if either:
                summary = f"{MODE_LABELS[mode]} scores higher here: {summary}"
            out[a] = {"summary": summary, **values,
                      "median walk (min)": r["median_walk_min"],
                      "90th percentile walk (min)": r["p90_walk_min"]}
        return out

    def notes(self, snapshot, areas, options):
        if self._mode(options) == "bus":
            return {}                     # the rail-data note is about MRT/LRT exits
        far = [a for a, (_, r) in self._rows(snapshot, areas, options).items()
               if r["far_from_rail"]]
        if not far:
            return {}
        note = notes.rail_data_note(snapshot.meta()["rail_data_as_of"])
        return {a: [note] for a in far}

    def factor_notes(self, snapshot, options):
        mode = self._mode(options)
        if mode == "rail":
            return []
        meta = snapshot.meta()
        out = [f"Bus is scored on how many different bus services stop within "
               f"{meta['bus_catchment_m']} m (70%) and the walk to the nearest stop served by "
               f"at least {meta['qualifying_bus_services']} services (30%). Bus stops are near "
               f"almost every flat, so the variety of services is what differs between areas "
               f"(LTA data of {meta['bus_data_as_of']})."]
        if mode == "either":
            out.append("Either uses the higher of the MRT/LRT and Bus scores for each area, "
                       "so it is usually higher than either one alone.")
        return out
