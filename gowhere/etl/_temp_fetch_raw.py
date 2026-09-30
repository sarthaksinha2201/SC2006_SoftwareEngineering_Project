"""TEMPORARY stand-in for S1 (gowhere.etl.fetch_raw, owned by Sarthak).

Fetches only the three datasets the Public Transport pipeline needs, following the S1 output
contract so it can be deleted without touching anything downstream:

    data/raw/<dataset_name>.json   exactly what the API returned
    data/raw/_manifest.json        per dataset: source id/url, fetch timestamp, record count

Delete this module once S1 lands.

    python -m gowhere.etl._temp_fetch_raw [--force]
"""
import argparse
import json
from datetime import datetime, timezone

from gowhere import config
from gowhere.adapters.datagov import DataGovAdapter

HDB_PROPERTY_ID = "d_17f5382f26140b1fdae0ba2ef6239d2f"
MRT_EXITS_ID = "d_b39d3a0871985372d7e1637193335da5"
PLANNING_AREAS_ID = "d_4765db0e87b9c86336792efe8a1f7a66"  # Master Plan 2019 Planning Area Boundary (No Sea)

DATASETS = {
    # name: (dataset id, kind)
    config.RAW_HDB_PROPERTY: (HDB_PROPERTY_ID, "datastore"),
    config.RAW_MRT_EXITS: (MRT_EXITS_ID, "file"),
    config.RAW_PLANNING_AREAS: (PLANNING_AREAS_ID, "file"),
}


def record_count(payload, kind):
    if kind == "datastore":
        # A paginated dataset is stored as the list of page responses, unmodified.
        return sum(len(p["result"]["records"]) for p in payload)
    return len(payload.get("features", []))


def fetch(names=None, force=False, adapter=None, raw_dir=None):
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
        payload = (adapter.datastore_pages(dataset_id) if kind == "datastore"
                   else adapter.download_file(dataset_id))
        out.write_text(json.dumps(payload))
        manifest[name] = {
            "source_id": dataset_id,
            "source_url": f"https://data.gov.sg/datasets/{dataset_id}/view",
            "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "record_count": record_count(payload, kind),
        }
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
