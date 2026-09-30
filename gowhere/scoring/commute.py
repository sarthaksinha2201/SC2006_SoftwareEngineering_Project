"""Commute category score (DECISIONS.md section 2).

Each area is represented by one HDB block: the block nearest the area's flat-weighted
centroid, precomputed in the ETL. At request time the commute is routed with OneMap from
that block to the user's destination postal code: at most one route per area (so at most
4 per comparison), sent in parallel. The score is absolute:
    <= 20 min -> 10, >= 80 min -> 0, linear in between.
If routing fails for an area, commute has no data for it and the engine drops the factor
for all selected areas.

Privacy (Security NFR): the destination postal code and its coordinates live only in a
CommuteRouter's memory, one router per user session. Nothing here writes them to disk,
and OneMap calls are made with redact=True so no error or log line carries them.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from gowhere.adapters.http import HttpError
from gowhere.adapters.onemap import OneMapAdapter
from gowhere.etl.addresses import expand_street, match_postal
from gowhere.etl.geo import LocalProjection
from gowhere.scoring.base import InvalidRequest, ScoringStrategy, TextPattern, select_by_area
from gowhere.scoring.stats import round1

MODES = {"pt": "public transport", "drive": "car"}
BEST_MINUTES, WORST_MINUTES = 20.0, 80.0
DEPARTURE_TIME = (8, 30)          # weekday morning peak, Singapore time
SGT = timezone(timedelta(hours=8))


def commute_score(minutes):
    """10 at <= 20 min, 0 at >= 80 min, linear in between."""
    if minutes <= BEST_MINUTES:
        return 10.0
    if minutes >= WORST_MINUTES:
        return 0.0
    return 10 * (WORST_MINUTES - minutes) / (WORST_MINUTES - BEST_MINUTES)


def next_weekday_departure(now=None):
    """The next Monday-Friday 08:30 in Singapore after `now`."""
    now = now or datetime.now(SGT)
    d = now.replace(hour=DEPARTURE_TIME[0], minute=DEPARTURE_TIME[1], second=0, microsecond=0)
    if d <= now:
        d += timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


class CommuteRouter:
    """Routes from representative blocks to one user's destination. Create one per user
    session and keep it in memory only. Results, including failures, are cached per
    (area, destination, mode), so changing a weight slider never re-routes."""

    def __init__(self, adapter=None, departure=None, max_workers=4):
        # No pacing: at most 4 calls per comparison, far under OneMap's 250/min.
        self.adapter = adapter or OneMapAdapter(min_interval_s=0)
        self.departure = departure
        self.max_workers = max_workers
        self._located = {}      # postal -> (lat, lon) or None when OneMap has no match
        self._minutes = {}      # (area, postal, mode) -> minutes or None when unroutable

    def locate(self, postal):
        """(lat, lon) of a postal code, or None if OneMap has no such postal code.
        Raises HttpError if OneMap cannot be reached."""
        if postal not in self._located:
            response = self.adapter.search(postal, redact=True)
            match = match_postal(postal, response.get("results", []))
            self._located[postal] = (match["lat"], match["lon"]) if match else None
        return self._located[postal]

    def minutes(self, origins, postal, mode):
        """{area: minutes or None}. origins: {area: (lat, lon)}."""
        destination = self.locate(postal)
        todo = [a for a in origins if (a, postal, mode) not in self._minutes]
        if todo:
            with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
                results = pool.map(lambda a: self._route(origins[a], destination, mode), todo)
                for area, result in zip(todo, results):
                    self._minutes[(area, postal, mode)] = result
        return {a: self._minutes[(a, postal, mode)] for a in origins}

    def _route(self, origin, destination, mode):
        try:
            if mode == "pt":
                departure = self.departure or next_weekday_departure()
                resp = self.adapter.transit_route(origin, destination, departure,
                                                  redact=True, retries=1)
                durations = [i["duration"] for i in (resp.get("plan") or {}).get("itineraries", [])]
                return min(durations) / 60 if durations else None
            resp = self.adapter.drive_route(origin, destination, redact=True, retries=1)
            seconds = (resp.get("route_summary") or {}).get("total_time")
            return seconds / 60 if seconds is not None else None
        except (HttpError, KeyError, TypeError, ValueError):
            return None


class CommuteScorer(ScoringStrategy):
    key = "commute"
    label = "Commute"

    def __init__(self, router=None):
        self.router = router or CommuteRouter()

    def schema(self):
        return """
CREATE TABLE commute_origin (
    planning_area TEXT PRIMARY KEY REFERENCES planning_area(name),
    block_id INTEGER NOT NULL REFERENCES hdb_block(id),
    blk_no TEXT NOT NULL, street TEXT NOT NULL,
    lat REAL NOT NULL, lon REAL NOT NULL,
    centroid_distance_m REAL NOT NULL);   -- block to the flat-weighted centroid
"""

    def precompute(self, blocks, sources):
        proj = LocalProjection()
        by_area = {}
        for b in blocks:
            by_area.setdefault(b["planning_area"], []).append(b)
        rows = []
        for area, bs in sorted(by_area.items()):
            flats = sum(b["total_dwelling_units"] for b in bs)
            xy = {b["id"]: proj.xy(b["lat"], b["lon"]) for b in bs}
            cx = sum(xy[b["id"]][0] * b["total_dwelling_units"] for b in bs) / flats
            cy = sum(xy[b["id"]][1] * b["total_dwelling_units"] for b in bs) / flats
            dist = lambda b: ((xy[b["id"]][0] - cx) ** 2 + (xy[b["id"]][1] - cy) ** 2) ** 0.5
            rep = min(bs, key=lambda b: (dist(b), b["id"]))
            rows.append({"planning_area": area, "block_id": rep["id"], "blk_no": rep["blk_no"],
                         "street": rep["street"], "lat": rep["lat"], "lon": rep["lon"],
                         "centroid_distance_m": dist(rep)})
        return {"commute_origin": rows}

    def options(self, snapshot):
        return {"destination_postal": TextPattern(r"\d{6}", "a 6-digit Singapore postal code"),
                "mode": list(MODES)}

    def _origins(self, snapshot, areas):
        rows = select_by_area(snapshot, "commute_origin", ["blk_no", "street", "lat", "lon"], areas)
        return rows, {a: (r["lat"], r["lon"]) for a, r in rows.items()}

    def _minutes(self, snapshot, areas, options):
        rows, origins = self._origins(snapshot, areas)
        try:
            if self.router.locate(options["destination_postal"]) is None:
                raise InvalidRequest("that postal code was not found")
            return rows, self.router.minutes(origins, options["destination_postal"], options["mode"])
        except HttpError:
            return rows, {}      # OneMap unreachable: commute unavailable for every area

    def category_scores(self, snapshot, areas, options):
        _, minutes = self._minutes(snapshot, areas, options)
        return {a: commute_score(minutes[a]) if minutes.get(a) is not None else None
                for a in areas}

    def raw_values(self, snapshot, areas, options):
        rows, minutes = self._minutes(snapshot, areas, options)
        mode = MODES[options["mode"]]
        return {a: {"summary": f"{round1(m):g} min by {mode} from Blk {rows[a]['blk_no']} "
                               f"{expand_street(rows[a]['street']).title()}",
                    "minutes": m}
                for a, m in minutes.items() if m is not None}

    def factor_notes(self, snapshot, options):
        when = " departing 8:30 am on a weekday" if options["mode"] == "pt" else ""
        return [f"Commute is timed from one HDB block per area, the block nearest the "
                f"centre of the area's flats, by {MODES[options['mode']]}{when}."]
