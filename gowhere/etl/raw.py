"""Readers for data/raw/. This is where cleaning starts: raw files are never modified."""
import json

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
