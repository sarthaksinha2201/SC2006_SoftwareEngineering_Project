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

    def parks(self):
        return self._get("parks", lambda: raw.load_parks(self.raw_dir))

    def park_connectors(self):
        return self._get("park_connectors", lambda: raw.load_park_connectors(self.raw_dir))

    def polyclinics(self):
        """Reference-list polyclinics placed by their postal code's OneMap geocode."""
        def load():
            clinics = reference.load_polyclinic_list(self.ref_dir)
            located = load_postal_geocodes([c["postal_code"] for c in clinics])
            missing = [c["name"] for c in clinics if located.get(c["postal_code"]) is None]
            if missing:
                raise ValueError(f"polyclinic postal codes not geocoded: {missing}; "
                                 f"run python -m gowhere.etl.geocode --reference")
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
