"""Everything a scoring strategy may read at build time: raw datasets, reference files
and cached geocodes. Offline; loaded lazily and cached per build."""
from gowhere import config
from gowhere.etl import raw, reference
from gowhere.etl.geocode import load_postal_geocodes


class RawSources:
    def __init__(self, raw_dir=None, ref_dir=None):
        self.raw_dir, self.ref_dir = raw_dir, ref_dir
        self._cache = {}

    def _get(self, key, loader):
        if key not in self._cache:
            self._cache[key] = loader()
        return self._cache[key]

    def mrt_exits(self):
        return self._get("mrt_exits", lambda: raw.load_mrt_exits(self.raw_dir))

    def mrt_exits_as_of(self):
        return self._get("mrt_exits_as_of", lambda: raw.mrt_exits_as_of(self.raw_dir))

    def bus_stops(self):
        """Qualifying Bus Stops (at least config.QUALIFYING_BUS_SERVICES services) inside
        Singapore: [{code, name, lat, lon, services}]. DataMall's list includes four
        stops in Johor Bahru (the checkpoint, Larkin, JB Sentral); points outside every
        planning area are dropped, as for the OpenStreetMap amenities. [] when the bus
        data was never fetched (it needs LTA_DATAMALL_KEY): the factor is then rail-only."""
        def load():
            if not raw.has_bus_data(self.raw_dir):
                self._cache["bus_meta"] = {}
                return []
            from gowhere.etl.geo import PlanningAreaIndex
            index = PlanningAreaIndex(raw.load_planning_areas(self.raw_dir))
            services = raw.load_bus_services(self.raw_dir)
            stops = raw.load_bus_stops(self.raw_dir)
            inside = [st for st in stops if index.area_of(st["lat"], st["lon"])]
            qualifying = [{**st, "services": len(services.get(st["code"], ()))} for st in inside
                          if len(services.get(st["code"], ())) >= config.QUALIFYING_BUS_SERVICES]
            self._cache["bus_meta"] = {
                "bus_stops_total": str(len(stops)),
                "bus_stops_outside_singapore": str(len(stops) - len(inside)),
                "bus_stops_qualifying": str(len(qualifying)),
                "qualifying_bus_services": str(config.QUALIFYING_BUS_SERVICES),
                "bus_data_as_of": raw.bus_data_as_of(self.raw_dir)}
            return qualifying
        return self._get("bus_stops", load)

    def bus_meta(self):
        self.bus_stops()
        return self._cache["bus_meta"]

    def parks(self):
        return self._get("parks", lambda: raw.load_parks(self.raw_dir))

    def park_connectors(self):
        return self._get("park_connectors", lambda: raw.load_park_connectors(self.raw_dir))

    def resale(self):
        """(window [first, last month], [transaction]) of HDB resale transactions."""
        return self._get("resale", lambda: raw.load_resale(self.raw_dir))

    def amenities(self):
        """{amenity type: [{name, lat, lon}]} for the six Amenities types.

        OSM points outside every planning area (Johor Bahru falls inside the download's
        bounding box) are dropped. Supermarkets are placed by postal code; licences at a
        postal code OneMap cannot find are left out and counted in amenities_meta().
        """
        def load():
            from gowhere.etl.geo import PlanningAreaIndex
            index = PlanningAreaIndex(raw.load_planning_areas(self.raw_dir))
            osm = {kind: [p for p in points if index.area_of(p["lat"], p["lon"])]
                   for kind, points in raw.load_osm_amenities(self.raw_dir).items()}
            licences = {(s["name"], s["postal_code"]) for s in raw.load_supermarket_licences(self.raw_dir)}
            located = load_postal_geocodes(sorted({pc for _, pc in licences}))
            supermarkets = [{"name": n, **located[pc]} for n, pc in sorted(licences) if located.get(pc)]
            self._cache["amenities_meta"] = {
                "supermarket_licences": len(licences),
                "supermarkets_unlocated": len(licences) - len(supermarkets)}
            return {"supermarket": supermarkets,
                    "hawker_centre": raw.load_hawker_centres(self.raw_dir),
                    "library": raw.load_libraries(self.raw_dir), **osm}
        return self._get("amenities", load)

    def amenities_meta(self):
        self.amenities()
        return self._cache["amenities_meta"]

    def amenities_as_of(self):
        return self._get("amenities_as_of", lambda: {
            "supermarket": "2024-06-06",   # data.gov.sg listing date; records carry no date
            "hawker_centre": raw.hawker_centres_as_of(self.raw_dir),
            "library": raw.libraries_as_of(self.raw_dir),
            "osm": raw.osm_as_of(self.raw_dir)})

    def polyclinics(self):
        """Reference-list polyclinics placed by their postal code's OneMap geocode."""
        def load():
            clinics = reference.load_polyclinic_list(self.ref_dir)
            located = load_postal_geocodes([c["postal_code"] for c in clinics])
            missing = [c["name"] for c in clinics if located.get(c["postal_code"]) is None]
            if missing:
                raise ValueError(f"polyclinic postal codes not geocoded: {missing}; "
                                 f"run python -m gowhere.etl.geocode --postal-codes")
            return [{"name": c["name"], **located[c["postal_code"]]} for c in clinics]
        return self._get("polyclinics", load)

    def facilities(self):
        """{facility type: [{name, lat, lon}]}"""
        return self._get("facilities", lambda: {
            "gp": raw.load_gp_clinics(self.raw_dir),
            "polyclinic": self.polyclinics(),
            "hospital": raw.load_hospitals(reference.load_hospital_classification(self.ref_dir),
                                           self.raw_dir)})

    def facilities_as_of(self):
        """{facility type: date the underlying list was last updated or compiled}"""
        return self._get("facilities_as_of", lambda: {
            "gp": raw.chas_clinics_as_of(self.raw_dir),
            "polyclinic": config.REFERENCE_CLASSIFIED_ON,
            "hospital": config.REFERENCE_CLASSIFIED_ON})
