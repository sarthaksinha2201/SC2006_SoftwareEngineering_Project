"""Readers for data/raw/. This is where cleaning starts: raw files are never modified."""
import json
import re

from gowhere import config


def _read(name, raw_dir=None):
    return json.loads(((raw_dir or config.RAW_DIR) / f"{name}.json").read_text())


def _datastore_records(payload):
    """Records from a datastore dataset stored as one response or a list of page responses."""
    pages = payload if isinstance(payload, list) else [payload]
    return [rec for page in pages for rec in page["result"]["records"]]


def load_hdb_residential(raw_dir=None):
    """HDB blocks with residential = 'Y', in dataset order, with the fields the ETL needs."""
    blocks = []
    for rec in _datastore_records(_read(config.RAW_HDB_PROPERTY, raw_dir)):
        if rec["residential"].strip().upper() != "Y":
            continue
        blocks.append({
            "blk_no": rec["blk_no"].strip(),
            "street": rec["street"].strip(),
            "total_dwelling_units": int(rec["total_dwelling_units"]),
            "year_completed": rec.get("year_completed"),
        })
    return blocks


def load_mrt_exits(raw_dir=None):
    exits = []
    for feat in _read(config.RAW_MRT_EXITS, raw_dir)["features"]:
        lon, lat = feat["geometry"]["coordinates"][:2]
        props = feat["properties"]
        exits.append({"station": props["STATION_NA"].strip(),
                      "exit_code": props["EXIT_CODE"].strip(),
                      "lat": float(lat), "lon": float(lon)})
    return exits


def load_planning_areas(raw_dir=None):
    """[{name, region, geometry (GeoJSON dict)}] for every planning area."""
    return [{"name": feat["properties"]["PLN_AREA_N"].strip().upper(),
             "region": feat["properties"]["REGION_N"].strip().upper(),
             "geometry": feat["geometry"]}
            for feat in _read(config.RAW_PLANNING_AREAS, raw_dir)["features"]]


def _fmel_date(values):
    """Latest FMEL_UPD_D (e.g. '20251202172807') as an ISO date: when the layer last changed."""
    latest = max(v for v in values if v)
    return f"{latest[:4]}-{latest[4:6]}-{latest[6:8]}"


def mrt_exits_as_of(raw_dir=None):
    return _fmel_date(f["properties"].get("FMEL_UPD_D")
                      for f in _read(config.RAW_MRT_EXITS, raw_dir)["features"])


def load_parks(raw_dir=None):
    """Park and nature-reserve boundaries: [{name, geometry}]."""
    return [{"name": f["properties"]["NAME"].strip(), "geometry": f["geometry"]}
            for f in _read(config.RAW_PARKS, raw_dir)["features"]]


def load_park_connectors(raw_dir=None):
    """Built park connector segments: [{name, geometry}]."""
    return [{"name": (f["properties"].get("PCN_LOOP") or f["properties"].get("PARK") or "").strip(),
             "geometry": f["geometry"]}
            for f in _read(config.RAW_PARK_CONNECTORS, raw_dir)["features"]]


def _kml_attributes(description):
    """CHAS stores its attributes as an HTML table inside the KML Description field."""
    return dict(re.findall(r"<th>(\w+)</th>\s*<td>(.*?)</td>", description))


def load_gp_clinics(raw_dir=None):
    """CHAS medical clinics (LICENCE_TYPE MC); dental clinics (MD) are left out."""
    clinics = []
    for f in _read(config.RAW_CHAS_CLINICS, raw_dir)["features"]:
        attrs = _kml_attributes(f["properties"]["Description"])
        if attrs.get("LICENCE_TYPE") != "MC":
            continue
        lon, lat = f["geometry"]["coordinates"][:2]
        clinics.append({"name": attrs["HCI_NAME"].strip(), "lat": float(lat), "lon": float(lon)})
    return clinics


def chas_clinics_as_of(raw_dir=None):
    return _fmel_date(_kml_attributes(f["properties"]["Description"]).get("FMEL_UPD_D")
                      for f in _read(config.RAW_CHAS_CLINICS, raw_dir)["features"])


def load_hospitals(raw_dir=None, exclude=None):
    """MOH-licensed hospitals from the OneMap theme, minus config.HOSPITAL_EXCLUDE."""
    exclude = {n.upper() for n in (config.HOSPITAL_EXCLUDE if exclude is None else exclude)}
    hospitals = []
    for item in _read(config.RAW_HOSPITALS, raw_dir)["SrchResults"][1:]:
        if item["NAME"].strip().upper() in exclude:
            continue
        lat, lon = (float(v) for v in item["LatLng"].split(","))
        hospitals.append({"name": item["NAME"].strip(), "lat": lat, "lon": lon})
    return hospitals


def hospitals_as_of(raw_dir=None):
    return _read(config.RAW_HOSPITALS, raw_dir)["SrchResults"][0]["DateTime"][:10]


class RawSources:
    """Lazy, cached access to the raw datasets a scoring strategy may need."""

    def __init__(self, raw_dir=None):
        self.raw_dir = raw_dir
        self._cache = {}

    def _get(self, key, loader):
        if key not in self._cache:
            self._cache[key] = loader(self.raw_dir)
        return self._cache[key]

    def mrt_exits(self):
        return self._get("mrt_exits", load_mrt_exits)

    def mrt_exits_as_of(self):
        return self._get("mrt_exits_as_of", mrt_exits_as_of)

    def parks(self):
        return self._get("parks", load_parks)

    def park_connectors(self):
        return self._get("park_connectors", load_park_connectors)

    def facilities(self):
        """{facility type: [{name, lat, lon}]} for every type with a source."""
        return self._get("facilities", lambda d: {"gp": load_gp_clinics(d),
                                                  "hospital": load_hospitals(d)})

    def facilities_as_of(self):
        return self._get("facilities_as_of", lambda d: {"gp": chas_clinics_as_of(d),
                                                        "hospital": hospitals_as_of(d)})
