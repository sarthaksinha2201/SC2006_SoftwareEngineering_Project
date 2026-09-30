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


def load_hospitals(classification, raw_dir=None):
    """Hospitals from the OneMap moh_hospitals theme that the classification counts.

    Every theme hospital must appear in the classification, so a newly licensed hospital
    stops the build until someone classifies it, rather than being silently included.
    """
    from gowhere.etl.reference import hospital_counts
    hospitals = []
    for item in _read(config.RAW_HOSPITALS, raw_dir)["SrchResults"][1:]:
        name = item["NAME"].strip()
        if name not in classification:
            raise ValueError(f"hospital {name!r} is not in data/reference/hospitals.csv; classify it")
        if not hospital_counts(classification[name]):
            continue
        lat, lon = (float(v) for v in item["LatLng"].split(","))
        hospitals.append({"name": name, "lat": lat, "lon": lon})
    return hospitals


def hospitals_as_of(raw_dir=None):
    return _read(config.RAW_HOSPITALS, raw_dir)["SrchResults"][0]["DateTime"][:10]


def parse_remaining_lease(text):
    """'61 years 04 months' -> 736 months. Also accepts '61 years'."""
    m = re.fullmatch(r"\s*(\d+)\s+years?(?:\s+(\d+)\s+months?)?\s*", text)
    if not m:
        raise ValueError(f"unrecognised remaining_lease {text!r}")
    return int(m.group(1)) * 12 + int(m.group(2) or 0)


def load_resale(raw_dir=None):
    """(window [first month, last month], [transaction]) from the resale download.

    Every month in the window must be present, so a partial download cannot pass as a
    quiet month.
    """
    manifest = json.loads(((raw_dir or config.RAW_DIR) / "_manifest.json").read_text())
    start, end = manifest[config.RAW_RESALE]["window"]
    pages = _read(config.RAW_RESALE, raw_dir)
    # Each month was downloaded with its own filter, so every page reports that month's
    # total: the records held for a month must add up to it.
    expected_count, held = {}, {}
    for page in pages:
        for rec in page["result"]["records"]:
            expected_count[rec["month"]] = page["result"]["total"]
            held[rec["month"]] = held.get(rec["month"], 0) + 1
    short = {m: (held[m], n) for m, n in expected_count.items() if held[m] != n}
    if short:
        raise ValueError(f"resale download incomplete (held, expected): {short}")
    transactions = []
    for rec in _datastore_records(pages):
        if not start <= rec["month"] <= end:
            continue
        transactions.append({
            "month": rec["month"], "flat_type": rec["flat_type"].strip().upper(),
            "blk_no": rec["block"].strip(), "street": rec["street_name"].strip(),
            "resale_price": int(float(rec["resale_price"])),
            "remaining_lease_months": parse_remaining_lease(rec["remaining_lease"]),
        })
    months = {t["month"] for t in transactions}
    y, m = int(start[:4]), int(start[5:])
    expected = set()
    while f"{y:04d}-{m:02d}" <= end:
        expected.add(f"{y:04d}-{m:02d}")
        y, m = (y, m + 1) if m < 12 else (y + 1, 1)
    if months != expected:
        raise ValueError(f"resale data missing months: {sorted(expected - months)}")
    return [start, end], transactions


def _geojson_attributes(properties):
    """Attributes of a data.gov.sg feature: plain properties, or KML's HTML Description."""
    if "Description" in properties:
        return _kml_attributes(properties["Description"])
    return properties


def load_hawker_centres(raw_dir=None):
    """NEA hawker centres that are open (anything but 'Under Construction')."""
    centres = []
    for f in _read(config.RAW_HAWKER_CENTRES, raw_dir)["features"]:
        attrs = _geojson_attributes(f["properties"])
        if attrs.get("STATUS", "").strip().lower() == "under construction":
            continue
        lon, lat = f["geometry"]["coordinates"][:2]
        centres.append({"name": attrs["NAME"].strip(), "lat": float(lat), "lon": float(lon)})
    return centres


def hawker_centres_as_of(raw_dir=None):
    return _fmel_date(_geojson_attributes(f["properties"]).get("FMEL_UPD_D")
                      for f in _read(config.RAW_HAWKER_CENTRES, raw_dir)["features"])


def load_libraries(raw_dir=None):
    """NLB public libraries from the OneMap theme."""
    libraries = []
    for item in _read(config.RAW_LIBRARIES, raw_dir)["SrchResults"][1:]:
        lat, lon = (float(v) for v in item["LatLng"].split(","))
        libraries.append({"name": item["NAME"].strip(), "lat": lat, "lon": lon})
    return libraries


def libraries_as_of(raw_dir=None):
    return _read(config.RAW_LIBRARIES, raw_dir)["SrchResults"][0]["DateTime"][:10]


def load_supermarket_licences(raw_dir=None):
    """SFA supermarket licences: [{name, postal_code}]. Located later by postal code."""
    return [{"name": r["licensee_name"].strip(), "postal_code": r["postal_code"].strip().zfill(6)}
            for r in _datastore_records(_read(config.RAW_SUPERMARKETS, raw_dir))]


def load_osm_amenities(raw_dir=None):
    """{amenity type: [{name, lat, lon}]} from the Overpass download, by config.OSM_AMENITY_TAGS."""
    tag_of = {}
    for kind, selector in config.OSM_AMENITY_TAGS.items():
        key, value = re.fullmatch(r'\["(.+)"="(.+)"\]', selector).groups()
        tag_of[(key, value)] = kind
    out = {kind: [] for kind in config.OSM_AMENITY_TAGS}
    payload = _read(config.RAW_OSM_AMENITIES, raw_dir)
    for e in payload["elements"]:
        tags = e.get("tags", {})
        kind = next((k for (key, value), k in tag_of.items() if tags.get(key) == value), None)
        point = e if "lat" in e else e.get("center")
        if kind is None or not point:
            continue
        out[kind].append({"name": tags.get("name", f"unnamed {kind}"),
                          "lat": float(point["lat"]), "lon": float(point["lon"])})
    return out


def osm_as_of(raw_dir=None):
    return _read(config.RAW_OSM_AMENITIES, raw_dir)["osm3s"]["timestamp_osm_base"][:10]
