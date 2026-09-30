"""Pure geometry: Haversine distance, the walking model, nearest point, point-in-polygon."""
import math

from shapely import STRtree
from shapely.geometry import Point, shape
from shapely.ops import transform

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


class LocalProjection:
    """Lon/lat -> metres on a flat plane centred on Singapore (equirectangular).

    Across Singapore's 0.3 degrees of latitude the scale error is under 0.01%, far
    below geocoding error, so distances to polygons and lines can be measured in metres
    with shapely without a projection library.
    """

    def __init__(self, lat0=1.35, lon0=103.82):
        self.lat0, self.lon0 = lat0, lon0
        self.kx = math.radians(1) * EARTH_RADIUS_M * math.cos(math.radians(lat0))
        self.ky = math.radians(1) * EARTH_RADIUS_M

    def xy(self, lat, lon):
        return ((lon - self.lon0) * self.kx, (lat - self.lat0) * self.ky)

    def geometry(self, geojson):
        """A GeoJSON geometry (lon/lat) as a shapely geometry in metres."""
        return transform(lambda lon, lat, z=None: ((lon - self.lon0) * self.kx,
                                                   (lat - self.lat0) * self.ky),
                         shape(geojson))


class NearestIndex:
    """Distance in metres from a point to the nearest of many features (points, lines,
    polygons). A point inside a polygon is at distance 0."""

    def __init__(self, features, projection=None):
        """features: [{"name", and "geometry" (GeoJSON) or "lat"/"lon"}]."""
        self.proj = projection or LocalProjection()
        self.names = [f["name"] for f in features]
        self.geoms = [self.proj.geometry(f["geometry"]) if "geometry" in f
                      else Point(self.proj.xy(f["lat"], f["lon"])) for f in features]
        self.tree = STRtree(self.geoms)

    def nearest(self, lat, lon):
        """(name, distance_m) of the nearest feature."""
        idx, dist = self.tree.query_nearest(Point(self.proj.xy(lat, lon)), return_distance=True)
        return self.names[int(idx[0])], float(dist[0])
