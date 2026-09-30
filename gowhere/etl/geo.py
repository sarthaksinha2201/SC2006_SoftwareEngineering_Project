"""Pure geometry: Haversine distance, the walking model, nearest point, point-in-polygon."""
import math

from shapely import STRtree
from shapely.geometry import Point, shape

from gowhere import config

EARTH_RADIUS_M = 6_371_008.8  # IUGG mean radius


def haversine_m(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def walk_minutes(straight_line_m, detour=config.DETOUR_FACTOR,
                 speed=config.WALK_SPEED_M_PER_MIN):
    """Walking time model (DECISIONS.md section 4): distance x detour / 80 m per minute."""
    return straight_line_m * detour / speed


def nearest(lat, lon, points):
    """(point, distance_m) of the point closest to (lat, lon) by Haversine.

    Linear scan: ~600 exits x ~11k blocks is a few seconds and needs no index to trust.
    """
    best, best_d = None, math.inf
    for p in points:
        d = haversine_m(lat, lon, p["lat"], p["lon"])
        if d < best_d:
            best, best_d = p, d
    return best, best_d


class PlanningAreaIndex:
    """Point-in-polygon lookup over planning-area geometries (GeoJSON, lon/lat order)."""

    def __init__(self, areas):
        """areas: iterable of {"name", "geometry"} as returned by raw.load_planning_areas."""
        self.names = [a["name"] for a in areas]
        self.geoms = [shape(a["geometry"]) for a in areas]
        self.tree = STRtree(self.geoms)

    def area_of(self, lat, lon):
        """Name of the area containing the point, or None. Boundary points count as inside."""
        pt = Point(lon, lat)
        hits = sorted(self.tree.query(pt, predicate="intersects"))
        return self.names[hits[0]] if hits else None
