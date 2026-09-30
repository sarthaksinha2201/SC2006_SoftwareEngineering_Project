"""Build data/snapshot.db from data/raw/ and the geocode cache. Makes no network calls.

The snapshot is written to a temporary file and only replaces the active snapshot once
validation passes, so a failed build leaves the previous snapshot in place.

    python -m gowhere.etl.build_snapshot [--min-geocode-coverage 0.98]
"""
import argparse
import csv
import json
import os
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone

from gowhere import config
from gowhere.etl.geo import PlanningAreaIndex
from gowhere.etl.geocode import load_geocodes
from gowhere.etl.raw import load_hdb_residential, load_mrt_exits, load_planning_areas
from gowhere.etl.spatial import enrich_blocks
from gowhere.scoring.public_transport import area_metrics, public_transport_scores

SCHEMA_VERSION = "2"   # 2: transport -> public_transport, planning_area.small_sample
UNPLACED_LOG = config.LOG_DIR / "unplaced_blocks.csv"

SCHEMA = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE planning_area (
    name TEXT PRIMARY KEY, region TEXT NOT NULL,
    in_scope INTEGER NOT NULL,            -- 1 if it contains >= 1 HDB residential block
    n_blocks INTEGER NOT NULL, n_flats INTEGER NOT NULL,
    small_sample INTEGER NOT NULL,        -- 1 if in scope with < meta.small_area_blocks blocks
    geometry_geojson TEXT NOT NULL);
CREATE TABLE mrt_exit (station TEXT NOT NULL, exit_code TEXT NOT NULL,
    lat REAL NOT NULL, lon REAL NOT NULL);
CREATE TABLE hdb_block (
    id INTEGER PRIMARY KEY, blk_no TEXT NOT NULL, street TEXT NOT NULL, postal TEXT,
    lat REAL NOT NULL, lon REAL NOT NULL,
    planning_area TEXT NOT NULL REFERENCES planning_area(name),
    total_dwelling_units INTEGER NOT NULL,
    nearest_station TEXT NOT NULL, nearest_exit_code TEXT NOT NULL,
    exit_distance_m REAL NOT NULL,        -- straight line (Haversine)
    walk_min REAL NOT NULL,               -- exit_distance_m x detour / walk speed
    UNIQUE (blk_no, street));
CREATE INDEX hdb_block_area ON hdb_block(planning_area);
CREATE TABLE public_transport_area (
    planning_area TEXT PRIMARY KEY REFERENCES planning_area(name),
    n_blocks INTEGER NOT NULL, n_flats INTEGER NOT NULL,
    pct_within_10 REAL NOT NULL, median_walk_min REAL NOT NULL, p90_walk_min REAL NOT NULL,
    pr_pct_within_10 REAL NOT NULL, pr_median_walk REAL NOT NULL,
    score REAL NOT NULL);                 -- 0-10 category score
"""


class ValidationError(Exception):
    pass


def compute(blocks, geocodes, areas, exits, detour=config.DETOUR_FACTOR):
    """Everything the snapshot holds, as plain data. No I/O, so it is testable directly."""
    placed, unplaced = enrich_blocks(blocks, geocodes, PlanningAreaIndex(areas), exits, detour)
    by_area = defaultdict(list)
    for b in placed:
        by_area[b["planning_area"]].append(b)
    metrics = {a: area_metrics([b["walk_min"] for b in bs], [b["total_dwelling_units"] for b in bs])
               for a, bs in by_area.items()}
    scores = public_transport_scores(metrics)
    return {"placed": placed, "unplaced": unplaced, "metrics": metrics, "scores": scores}


def validate(result, n_residential, min_geocode_coverage):
    coverage = len(result["placed"]) / n_residential if n_residential else 0
    if coverage < min_geocode_coverage:
        raise ValidationError(f"only {coverage:.1%} of residential blocks placed "
                              f"(need {min_geocode_coverage:.0%}); see {UNPLACED_LOG}")
    if not result["scores"]:
        raise ValidationError("no in-scope planning areas")
    for area, s in result["scores"].items():
        if not 0 <= s["score"] <= 10:
            raise ValidationError(f"{area}: score {s['score']} outside 0-10")
    for area, m in result["metrics"].items():
        if m["n_flats"] <= 0:
            raise ValidationError(f"{area}: no flats")
    return coverage


def is_small_sample(n_blocks, threshold=config.SMALL_AREA_BLOCKS):
    """True for an in-scope area whose scores rest on too few blocks to be stable."""
    return 0 < n_blocks < threshold


def write_snapshot(path, result, areas, exits, meta):
    if path.exists():
        path.unlink()
    db = sqlite3.connect(path)
    db.executescript(SCHEMA)
    db.executemany("INSERT INTO meta VALUES (?, ?)", sorted(meta.items()))
    for a in areas:
        m = result["metrics"].get(a["name"])
        n_blocks = m["n_blocks"] if m else 0
        db.execute("INSERT INTO planning_area VALUES (?, ?, ?, ?, ?, ?, ?)",
                   (a["name"], a["region"], int(m is not None), n_blocks,
                    m["n_flats"] if m else 0, int(is_small_sample(n_blocks)),
                    json.dumps(a["geometry"])))
    db.executemany("INSERT INTO mrt_exit VALUES (?, ?, ?, ?)",
                   [(e["station"], e["exit_code"], e["lat"], e["lon"]) for e in exits])
    db.executemany(
        "INSERT INTO hdb_block (blk_no, street, postal, lat, lon, planning_area, "
        "total_dwelling_units, nearest_station, nearest_exit_code, exit_distance_m, walk_min) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [(b["blk_no"], b["street"], b["postal"], b["lat"], b["lon"], b["planning_area"],
          b["total_dwelling_units"], b["nearest_station"], b["nearest_exit_code"],
          b["exit_distance_m"], b["walk_min"]) for b in result["placed"]])
    for area, m in result["metrics"].items():
        s = result["scores"][area]
        db.execute("INSERT INTO public_transport_area VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                   (area, m["n_blocks"], m["n_flats"], m["pct_within_10"], m["median_walk_min"],
                    m["p90_walk_min"], s["pr_pct_within_10"], s["pr_median_walk"], s["score"]))
    db.commit()
    db.close()


def write_unplaced_log(unplaced, path=UNPLACED_LOG):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["blk_no", "street", "total_dwelling_units", "reason", "detail"])
        for b in unplaced:
            w.writerow([b["blk_no"], b["street"], b["total_dwelling_units"], b["reason"], b["detail"]])


def load_inputs():
    """(blocks, geocodes, areas, exits) from data/raw and the geocode cache. Offline."""
    blocks = load_hdb_residential()
    return blocks, load_geocodes(blocks=blocks), load_planning_areas(), load_mrt_exits()


def build(snapshot_path=config.SNAPSHOT_PATH, min_geocode_coverage=0.98,
          detour=config.DETOUR_FACTOR):
    blocks, geocodes, areas, exits = load_inputs()
    result = compute(blocks, geocodes, areas, exits, detour)
    write_unplaced_log(result["unplaced"])
    coverage = validate(result, len(blocks), min_geocode_coverage)

    manifest_path = config.RAW_DIR / "_manifest.json"
    meta = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "schema_version": SCHEMA_VERSION,
        "detour_factor": str(detour),
        "detour_factor_calibrated_on": config.DETOUR_FACTOR_CALIBRATED_ON,
        "detour_factor_source": config.DETOUR_FACTOR_SOURCE,
        "walk_speed_m_per_min": str(config.WALK_SPEED_M_PER_MIN),
        "walk_threshold_min": str(config.WALK_THRESHOLD_MIN),
        "small_area_blocks": str(config.SMALL_AREA_BLOCKS),
        "residential_blocks": str(len(blocks)),
        "placed_blocks": str(len(result["placed"])),
        "geocode_coverage": f"{coverage:.4f}",
        # MRT and LRT exits are one set: "nearest exit" means nearest MRT or LRT exit.
        "rail_exits": str(len(exits)),
        "rail_stations": str(len({e["station"] for e in exits})),
        "lrt_stations": str(len({e["station"] for e in exits if "LRT" in e["station"]})),
        "raw_manifest": manifest_path.read_text() if manifest_path.exists() else "{}",
    }
    tmp = snapshot_path.with_suffix(".db.tmp")
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    write_snapshot(tmp, result, areas, exits, meta)
    os.replace(tmp, snapshot_path)
    return result, meta


def main():
    parser = argparse.ArgumentParser(description="Build data/snapshot.db (offline)")
    parser.add_argument("--min-geocode-coverage", type=float, default=0.98)
    args = parser.parse_args()
    try:
        result, meta = build(min_geocode_coverage=args.min_geocode_coverage)
    except ValidationError as e:
        raise SystemExit(f"validation failed, previous snapshot kept: {e}")
    print(f"snapshot written: {meta['placed_blocks']}/{meta['residential_blocks']} blocks placed, "
          f"{len(result['scores'])} in-scope areas, {len(result['unplaced'])} unplaced "
          f"(logged to {UNPLACED_LOG})")
    for area, s in sorted(result["scores"].items(), key=lambda kv: -kv[1]["score"]):
        m = result["metrics"][area]
        print(f"  {area:<24} score {s['score']:4.1f}  within10 {m['pct_within_10']:5.1f}%  "
              f"median {m['median_walk_min']:4.1f}  p90 {m['p90_walk_min']:4.1f}  "
              f"blocks {m['n_blocks']}")


if __name__ == "__main__":
    main()
