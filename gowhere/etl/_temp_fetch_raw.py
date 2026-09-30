"""TEMPORARY stand-in for S1 (gowhere.etl.fetch_raw, owned by Sarthak).

Fetches only the datasets the Public Transport, Greenery and Healthcare factors need, following the S1 output
contract so it can be deleted without touching anything downstream:

    data/raw/<dataset_name>.json   exactly what the API returned
    data/raw/_manifest.json        per dataset: source id/url, fetch timestamp, record count

Delete this module once S1 lands.

    python -m gowhere.etl._temp_fetch_raw [--force]
"""
import argparse
import json
from datetime import date, datetime, timezone

from gowhere import config
from gowhere.adapters.datagov import DataGovAdapter
from gowhere.adapters.onemap import OneMapAdapter
from gowhere.adapters.overpass import OverpassAdapter

HDB_PROPERTY_ID = "d_17f5382f26140b1fdae0ba2ef6239d2f"
MRT_EXITS_ID = "d_b39d3a0871985372d7e1637193335da5"
PLANNING_AREAS_ID = "d_4765db0e87b9c86336792efe8a1f7a66"  # Master Plan 2019 Planning Area Boundary (No Sea)
PARKS_ID = "d_77d7ec97be83d44f61b85454f844382f"            # NParks Parks and Nature Reserves (polygons)
PARK_CONNECTORS_ID = "d_a69ef89737379f231d2ae93fd1c5707f"  # NParks Park Connector Loop (built network)
CHAS_CLINICS_ID = "d_548c33ea2d99e29ec63a7cc9edcccedc"     # MOH CHAS Clinics
HOSPITALS_THEME = "moh_hospitals"   # no data.gov.sg dataset; MOH publishes it as a OneMap theme
RESALE_ID = "d_8b84c4ee58e3cfc0ece0d773c8ca6abc"            # resale prices, registration date, 2017+
HAWKER_CENTRES_ID = "d_4a086da0a5553be1d89383cd90d07ecd"   # NEA Hawker Centres (GEOJSON)
LIBRARIES_THEME = "libraries"   # NLB via OneMap: updated Aug 2026; data.gov.sg's copy dates from 2019
SUPERMARKETS_ID = "d_11edd0117280c5776651d7891114c88c"     # SFA List of Supermarket Licences
OSM_AMENITIES = "overpass"      # malls, gyms, cafes: config.OSM_AMENITY_TAGS

DATASETS = {
    # name: (dataset id, kind)
    config.RAW_HDB_PROPERTY: (HDB_PROPERTY_ID, "datastore"),
    config.RAW_MRT_EXITS: (MRT_EXITS_ID, "file"),
    config.RAW_PLANNING_AREAS: (PLANNING_AREAS_ID, "file"),
    config.RAW_PARKS: (PARKS_ID, "file"),
    config.RAW_PARK_CONNECTORS: (PARK_CONNECTORS_ID, "file"),
    config.RAW_CHAS_CLINICS: (CHAS_CLINICS_ID, "file"),
    config.RAW_HOSPITALS: (HOSPITALS_THEME, "onemap_theme"),
    config.RAW_RESALE: (RESALE_ID, "datastore_window"),
    config.RAW_HAWKER_CENTRES: (HAWKER_CENTRES_ID, "file"),
    config.RAW_LIBRARIES: (LIBRARIES_THEME, "onemap_theme"),
    config.RAW_SUPERMARKETS: (SUPERMARKETS_ID, "datastore"),
    config.RAW_OSM_AMENITIES: (OSM_AMENITIES, "overpass"),
}


def window_months(today, n=config.RESALE_WINDOW_MONTHS):
    """The n complete calendar months before today's month, oldest first, as 'YYYY-MM'."""
    months, y, m = [], today.year, today.month
    for _ in range(n):
        y, m = (y, m - 1) if m > 1 else (y - 1, 12)
        months.append(f"{y:04d}-{m:02d}")
    return months[::-1]


def record_count(payload, kind):
    if kind in ("datastore", "datastore_window"):
        # A paginated dataset is stored as the list of page responses, unmodified.
        return sum(len(p["result"]["records"]) for p in payload)
    if kind == "onemap_theme":
        return len(payload["SrchResults"]) - 1   # first entry is the theme's own metadata
    if kind == "overpass":
        return len(payload["elements"])
    return len(payload.get("features", []))


def source_url(dataset_id, kind):
    if kind == "onemap_theme":
        return f"https://www.onemap.gov.sg/api/public/themesvc/retrieveTheme?queryName={dataset_id}"
    if kind == "overpass":
        return "https://overpass-api.de/api/interpreter"
    return f"https://data.gov.sg/datasets/{dataset_id}/view"


def fetch(names=None, force=False, adapter=None, onemap=None, raw_dir=None, today=None):
    adapter = adapter or DataGovAdapter()
    raw_dir = raw_dir or config.RAW_DIR
    raw_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = raw_dir / "_manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}

    for name in names or DATASETS:
        dataset_id, kind = DATASETS[name]
        out = raw_dir / f"{name}.json"
        if out.exists() and name in manifest and not force:
            print(f"cached   {name} ({manifest[name]['record_count']} records)")
            continue
        window = None
        if kind == "datastore":
            payload = adapter.datastore_pages(dataset_id)
        elif kind == "datastore_window":
            # The one filter S1 allows on download: the resale 12-month window.
            window = window_months(today or date.today())
            payload = [page for month in window
                       for page in adapter.datastore_pages(dataset_id, filters={"month": month})]
        elif kind == "overpass":
            payload = OverpassAdapter().amenities(list(config.OSM_AMENITY_TAGS.values()))
        elif kind == "onemap_theme":
            if onemap is None:
                config.load_dotenv()
                onemap = OneMapAdapter()
            payload = onemap.theme(dataset_id)
        else:
            payload = adapter.download_file(dataset_id)
        out.write_text(json.dumps(payload))
        manifest[name] = {
            "source_id": dataset_id,
            "source_url": source_url(dataset_id, kind),
            "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "record_count": record_count(payload, kind),
        }
        if window:
            manifest[name]["window"] = [window[0], window[-1]]
        manifest_path.write_text(json.dumps(manifest, indent=2))
        print(f"fetched  {name} ({manifest[name]['record_count']} records)")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--force", action="store_true", help="re-download cached datasets")
    args = parser.parse_args()
    fetch(force=args.force)


if __name__ == "__main__":
    main()
